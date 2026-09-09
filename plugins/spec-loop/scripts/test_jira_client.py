#!/usr/bin/env python3
"""Tests for the read-only Jira Cloud issue reader (stdlib unittest).

Covers issue-key and base-URL validation (allow-list + argument/URL-injection
defence), credential resolution and its fail-closed message, the ADF -> text
renderer, issue and paginated-comment resolution against a mocked urlopen, the
normalized-record contract, that the API token / account email / composed
base64(email:token) never leak into an error, stdout or stderr, and the
READ-ONLY guarantee (every urllib Request is a GET; the module spawns no
subprocess).

`scripts/validate_marketplace.py` does NOT lint scripts/*.py, so this is the
sole automated guard on the client. Standard library only. No live network.

Usage:
    python3 -m unittest test_jira_client
"""

import base64
import inspect
import json
import shutil
import sys
import tempfile
import unittest
import urllib.error
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jira_client as jc  # noqa: E402


class TestIssueKeyValidation(unittest.TestCase):
    def test_a_well_formed_key_is_returned_unchanged(self):
        self.assertEqual(jc.validate_issue_key("ABC-123"), "ABC-123")

    def test_a_single_letter_project_with_digits_is_accepted(self):
        self.assertEqual(jc.validate_issue_key("A1B2-7"), "A1B2-7")

    def test_lowercase_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_issue_key("abc-123")

    def test_a_path_traversal_attempt_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_issue_key("../../etc/passwd")

    def test_a_leading_dash_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_issue_key("-ABC-1")

    def test_an_embedded_slash_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_issue_key("ABC-1/comment")

    def test_an_empty_key_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_issue_key("")

    def test_a_trailing_newline_is_rejected(self):
        # re.match with a bare '$' anchor accepts one trailing newline;
        # fullmatch is required to reject it.
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_issue_key("ABC-123\n")

    def test_an_embedded_newline_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_issue_key("ABC-123\nrm -rf /")

    def test_the_rejection_message_names_the_expected_pattern(self):
        with self.assertRaises(jc.JiraUsageError) as ctx:
            jc.validate_issue_key("nope")
        self.assertIn("A-1", str(ctx.exception))


class TestBaseUrlValidation(unittest.TestCase):
    def test_an_allowed_https_host_returns_the_bare_origin(self):
        self.assertEqual(
            jc.validate_base_url("https://acme.atlassian.net/"),
            "https://acme.atlassian.net")

    def test_a_path_on_the_base_url_is_discarded(self):
        self.assertEqual(
            jc.validate_base_url("https://acme.atlassian.net/jira/software"),
            "https://acme.atlassian.net")

    def test_the_jira_com_suffix_is_allowed(self):
        self.assertEqual(
            jc.validate_base_url("https://acme.jira.com"),
            "https://acme.jira.com")

    def test_http_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_base_url("http://acme.atlassian.net")

    def test_an_unlisted_host_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_base_url("https://evil.example.com")

    def test_a_lookalike_suffix_host_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_base_url("https://evil-atlassian.net")

    def test_a_subdomain_of_an_attacker_domain_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_base_url("https://acme.atlassian.net.evil.com")

    def test_userinfo_smuggling_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_base_url("https://acme.atlassian.net@evil.com/")

    def test_an_empty_base_url_is_rejected(self):
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_base_url("")

    def test_the_host_allow_list_regex_rejects_a_trailing_newline(self):
        # re.match with a bare '$' anchor accepts one trailing newline;
        # fullmatch is required to reject it. urlsplit() itself strips
        # embedded whitespace/control characters from a URL before
        # ALLOWED_HOST_RE ever sees the hostname, so this is asserted
        # directly against the regex rather than through validate_base_url.
        self.assertIsNone(jc.ALLOWED_HOST_RE.fullmatch("acme.atlassian.net\n"))

    def test_a_malformed_port_raises_jira_usage_error_not_value_error(self):
        # parts.port is computed lazily by urllib.parse and raises a bare
        # ValueError for a non-numeric port; that must land on the
        # fail-closed JiraUsageError, never an uncaught traceback.
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_base_url("https://acme.atlassian.net:8080x")

    def test_an_unclosed_ipv6_bracket_raises_jira_usage_error_not_value_error(self):
        # urlsplit itself raises ValueError("Invalid IPv6 URL") for this input.
        with self.assertRaises(jc.JiraUsageError):
            jc.validate_base_url("https://[::1")

    def test_a_password_embedded_in_the_base_url_is_absent_from_the_message(self):
        with self.assertRaises(jc.JiraUsageError) as ctx:
            jc.validate_base_url(
                "https://fred@example.com:SUPERSECRETTOKEN@acme.atlassian.net")
        self.assertNotIn("SUPERSECRETTOKEN", str(ctx.exception))
        self.assertNotIn("fred@example.com", str(ctx.exception))


class TestCredentials(unittest.TestCase):
    ENV = {
        "JIRA_BASE_URL": "https://acme.atlassian.net",
        "JIRA_EMAIL": "fred@example.com",
        "JIRA_API_TOKEN": "s3cr3t-api-token",
    }

    def test_all_three_present_returns_the_validated_triple(self):
        with mock.patch.dict(jc.os.environ, self.ENV, clear=True):
            self.assertEqual(
                jc.credentials(),
                ("https://acme.atlassian.net", "fred@example.com", "s3cr3t-api-token"))

    def test_a_trailing_slash_base_url_is_normalized(self):
        env = dict(self.ENV, JIRA_BASE_URL="https://acme.atlassian.net/")
        with mock.patch.dict(jc.os.environ, env, clear=True):
            self.assertEqual(jc.credentials()[0], "https://acme.atlassian.net")

    def test_each_missing_variable_is_named_in_the_message(self):
        for missing in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
            env = {k: v for k, v in self.ENV.items() if k != missing}
            with self.subTest(missing=missing), \
                 mock.patch.dict(jc.os.environ, env, clear=True), \
                 self.assertRaises(jc.JiraUsageError) as ctx:
                jc.credentials()
            self.assertIn(missing, str(ctx.exception))

    def test_all_three_missing_names_all_three(self):
        with mock.patch.dict(jc.os.environ, {}, clear=True):
            with self.assertRaises(jc.JiraUsageError) as ctx:
                jc.credentials()
        for name in self.ENV:
            self.assertIn(name, str(ctx.exception))

    def test_an_empty_value_counts_as_unset(self):
        env = dict(self.ENV, JIRA_API_TOKEN="")
        with mock.patch.dict(jc.os.environ, env, clear=True):
            with self.assertRaises(jc.JiraUsageError):
                jc.credentials()

    def test_the_message_says_how_to_fix_it(self):
        with mock.patch.dict(jc.os.environ, {}, clear=True):
            with self.assertRaises(jc.JiraUsageError) as ctx:
                jc.credentials()
        self.assertIn("id.atlassian.com", str(ctx.exception))


class TestAuthHeader(unittest.TestCase):
    def test_scheme_is_basic_over_base64_of_email_colon_token(self):
        header = jc._auth_header("fred@example.com", "tok")
        expected = base64.b64encode(b"fred@example.com:tok").decode("ascii")
        self.assertEqual(header, "Basic " + expected)

    def test_it_is_not_bearer(self):
        self.assertNotIn("Bearer", jc._auth_header("a@b.c", "tok"))

    def test_non_ascii_credentials_encode_as_utf8(self):
        header = jc._auth_header("frédé@example.com", "tok")
        expected = base64.b64encode("frédé@example.com:tok".encode("utf-8")).decode("ascii")
        self.assertEqual(header, "Basic " + expected)


class TestHttpGetIsReadOnly(unittest.TestCase):
    def _fake_opener(self, payload=b"{}"):
        resp = mock.MagicMock()
        resp.read.return_value = payload
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        opener = mock.MagicMock()
        opener.open.return_value = resp
        return opener

    def test_the_request_method_is_get(self):
        opener = self._fake_opener()
        with mock.patch.object(jc, "_OPENER", opener):
            jc._http_get(
                "https://acme.atlassian.net/rest/api/3/field",
                "fred@example.com", "tok")
        req = opener.open.call_args.args[0]
        self.assertEqual(req.get_method(), "GET")

    def test_the_request_carries_no_body(self):
        opener = self._fake_opener()
        with mock.patch.object(jc, "_OPENER", opener):
            jc._http_get(
                "https://acme.atlassian.net/rest/api/3/field",
                "fred@example.com", "tok")
        self.assertIsNone(opener.open.call_args.args[0].data)

    def test_the_authorization_header_is_basic(self):
        opener = self._fake_opener()
        with mock.patch.object(jc, "_OPENER", opener):
            jc._http_get(
                "https://acme.atlassian.net/rest/api/3/field",
                "fred@example.com", "tok")
        req = opener.open.call_args.args[0]
        self.assertTrue(req.get_header("Authorization").startswith("Basic "))

    def _http_error(self, url, code, reason):
        """A closed-on-teardown HTTPError. HTTPError owns an internal file
        object; closing it avoids a ResourceWarning at GC time (mirrors
        test_pr_resolver.py's helper of the same name)."""
        err = urllib.error.HTTPError(url, code, reason, {}, None)
        self.addCleanup(err.close)
        return err

    def test_an_http_error_becomes_an_actionable_jira_error(self):
        err = self._http_error("https://acme.atlassian.net/x", 404, "Not Found")
        opener = mock.MagicMock()
        opener.open.side_effect = err
        with mock.patch.object(jc, "_OPENER", opener):
            with self.assertRaises(jc.JiraError) as ctx:
                jc._http_get("https://acme.atlassian.net/x", "fred@example.com", "tok")
        self.assertIn("404", str(ctx.exception))

    def test_a_network_error_becomes_a_jira_error(self):
        opener = mock.MagicMock()
        opener.open.side_effect = urllib.error.URLError("connection refused")
        with mock.patch.object(jc, "_OPENER", opener):
            with self.assertRaises(jc.JiraError):
                jc._http_get("https://acme.atlassian.net/x", "fred@example.com", "tok")


class TestHttpPostIsTheOnlyWriter(unittest.TestCase):
    """The plugin's FIRST mutating external call. It is a separate
    function from _http_get on purpose: the read lane's
    never-a-mutating-verb guarantee must survive unchanged."""

    URL = "https://acme.atlassian.net/rest/api/3/issue/ABC-1/comment"

    def _fake_opener(self, payload=b'{"id": "10001"}'):
        resp = mock.MagicMock()
        resp.read.return_value = payload
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        opener = mock.MagicMock()
        opener.open.return_value = resp
        return opener

    def _post(self, opener, payload=None):
        with mock.patch.object(jc, "_OPENER", opener):
            return jc._http_post(
                self.URL, "fred@example.com", "tok",
                payload if payload is not None else {"body": {"type": "doc"}})

    def test_the_request_method_is_post(self):
        opener = self._fake_opener()
        self._post(opener)
        self.assertEqual(opener.open.call_args.args[0].get_method(), "POST")

    def test_the_body_is_the_json_encoded_payload(self):
        opener = self._fake_opener()
        self._post(opener, {"body": {"type": "doc", "version": 1}})
        data = opener.open.call_args.args[0].data
        self.assertEqual(
            json.loads(data.decode("utf-8")),
            {"body": {"type": "doc", "version": 1}})

    def test_the_content_type_is_json(self):
        opener = self._fake_opener()
        self._post(opener)
        req = opener.open.call_args.args[0]
        self.assertEqual(req.get_header("Content-type"), "application/json")

    def test_the_authorization_header_is_basic(self):
        opener = self._fake_opener()
        self._post(opener)
        req = opener.open.call_args.args[0]
        self.assertTrue(req.get_header("Authorization").startswith("Basic "))

    def test_the_response_body_is_returned_raw(self):
        self.assertEqual(
            self._post(self._fake_opener(b'{"id": "7"}')), b'{"id": "7"}')

    def test_an_http_error_becomes_an_actionable_jira_error(self):
        err = urllib.error.HTTPError(self.URL, 403, "Forbidden", {}, None)
        self.addCleanup(err.close)
        opener = mock.MagicMock()
        opener.open.side_effect = err
        with self.assertRaises(jc.JiraError) as ctx:
            self._post(opener)
        self.assertIn("403", str(ctx.exception))

    def test_a_network_error_becomes_a_jira_error(self):
        opener = mock.MagicMock()
        opener.open.side_effect = urllib.error.URLError("connection refused")
        with self.assertRaises(jc.JiraError):
            self._post(opener)

    def test_a_redirect_is_never_followed_on_a_write(self):
        # _NoRedirect returns None for every 3xx, so urllib raises
        # instead of replaying the Authorization header (and the POST
        # body) to another origin.
        self.assertIsNone(jc._NoRedirect().redirect_request(
            mock.MagicMock(), mock.MagicMock(), 302, "Found", {},
            "https://evil.example.com/"))
        self.assertTrue(
            any(isinstance(h, jc._NoRedirect) for h in jc._OPENER.handlers))


class TestRedirectsAreRefused(unittest.TestCase):
    def test_the_redirect_handler_returns_none(self):
        handler = jc._NoRedirect()
        self.assertIsNone(handler.redirect_request(
            mock.MagicMock(), mock.MagicMock(), 302, "Found", {},
            "https://evil.example.com/"))

    def test_the_module_opener_installs_the_no_redirect_handler(self):
        installed = any(
            isinstance(h, jc._NoRedirect) for h in jc._OPENER.handlers)
        self.assertTrue(installed)


class TestParseJson(unittest.TestCase):
    def test_valid_json_round_trips(self):
        self.assertEqual(jc._parse_json('{"a": 1}', "issue"), {"a": 1})

    def test_malformed_json_raises_an_actionable_jira_error(self):
        with self.assertRaises(jc.JiraError) as ctx:
            jc._parse_json("not json", "issue")
        self.assertIn("issue", str(ctx.exception))


class TestSecretsNeverLeak(unittest.TestCase):
    """Mirrors and extends test_pr_resolver.py::TestTokenNeverLeaks: the raw
    token, the account email, AND the composed base64(email:token) must each be
    absent from the exception text, stdout and stderr."""

    TOKEN = "s3cr3t-api-token-value"
    EMAIL = "fred@example.com"
    ENV = {
        "JIRA_BASE_URL": "https://acme.atlassian.net",
        "JIRA_EMAIL": EMAIL,
        "JIRA_API_TOKEN": TOKEN,
    }

    @property
    def COMPOSED(self):
        return base64.b64encode(f"{self.EMAIL}:{self.TOKEN}".encode("utf-8")).decode("ascii")

    def _assert_clean(self, text):
        self.assertNotIn(self.TOKEN, text)
        self.assertNotIn(self.EMAIL, text)
        self.assertNotIn(self.COMPOSED, text)

    def _http_error(self, url, code, reason):
        """A closed-on-teardown HTTPError. HTTPError owns an internal file
        object; closing it avoids a ResourceWarning at GC time (mirrors
        test_pr_resolver.py's helper of the same name)."""
        err = urllib.error.HTTPError(url, code, reason, {}, None)
        self.addCleanup(err.close)
        return err

    def test_secrets_absent_from_an_http_error_message(self):
        err = self._http_error(
            "https://acme.atlassian.net/rest/api/3/issue/ABC-1", 401,
            "Unauthorized")
        opener = mock.MagicMock()
        opener.open.side_effect = err
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(jc, "_OPENER", opener))
            ctx = stack.enter_context(self.assertRaises(jc.JiraError))
            jc._http_get(
                "https://acme.atlassian.net/rest/api/3/issue/ABC-1",
                self.EMAIL, self.TOKEN)
        self._assert_clean(str(ctx.exception))

    def test_secrets_absent_from_a_network_error_message(self):
        opener = mock.MagicMock()
        opener.open.side_effect = urllib.error.URLError("connection refused")
        with mock.patch.object(jc, "_OPENER", opener):
            with self.assertRaises(jc.JiraError) as ctx:
                jc._http_get("https://acme.atlassian.net/x", self.EMAIL, self.TOKEN)
        self._assert_clean(str(ctx.exception))

    def test_a_password_embedded_in_the_base_url_never_leaks(self):
        raw = f"https://{self.EMAIL}:{self.TOKEN}@acme.atlassian.net"
        with self.assertRaises(jc.JiraUsageError) as ctx:
            jc.validate_base_url(raw)
        self._assert_clean(str(ctx.exception))

    def test_secrets_absent_from_a_post_http_error_message(self):
        err = self._http_error(
            "https://acme.atlassian.net/rest/api/3/issue/ABC-1/comment",
            401, "Unauthorized")
        opener = mock.MagicMock()
        opener.open.side_effect = err
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(jc, "_OPENER", opener))
            ctx = stack.enter_context(self.assertRaises(jc.JiraError))
            jc._http_post(
                "https://acme.atlassian.net/rest/api/3/issue/ABC-1/comment",
                self.EMAIL, self.TOKEN, {"body": {"type": "doc"}})
        self._assert_clean(str(ctx.exception))

    def test_secrets_absent_from_a_post_network_error_message(self):
        opener = mock.MagicMock()
        opener.open.side_effect = urllib.error.URLError("connection refused")
        url = "https://acme.atlassian.net/x"
        payload = {"body": {"type": "doc"}}
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(jc, "_OPENER", opener))
            ctx = stack.enter_context(self.assertRaises(jc.JiraError))
            jc._http_post(url, self.EMAIL, self.TOKEN, payload)
        self._assert_clean(str(ctx.exception))

    def test_secrets_absent_from_a_failed_post_in_the_comment_lane(self):
        err = self._http_error(
            "https://acme.atlassian.net/rest/api/3/issue/ABC-1/comment",
            401, "Unauthorized")
        opener = mock.MagicMock()
        resp = mock.MagicMock()
        resp.read.return_value = comment_page(0, 0, [])
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        opener.open.side_effect = [resp, err]
        entries = [entry()]
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.dict(jc.os.environ, self.ENV, clear=True))
            stack.enter_context(mock.patch.object(jc, "_OPENER", opener))
            ctx = stack.enter_context(self.assertRaises(jc.JiraError))
            jc.run_comment_lane("ABC-1", entries, True)
        self._assert_clean(str(ctx.exception))


def adf(*content):
    """Wrap block nodes in a minimal ADF document (hand-built fixture helper)."""
    return {"type": "doc", "version": 1, "content": list(content)}


def para(text):
    """A single-text-node ADF paragraph."""
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def heading(level, text):
    """An ADF heading of the given level."""
    return {"type": "heading", "attrs": {"level": level},
            "content": [{"type": "text", "text": text}]}


def bullets(*items):
    """An ADF bulletList of single-paragraph list items."""
    return {"type": "bulletList",
            "content": [{"type": "listItem", "content": [para(t)]} for t in items]}


class TestAdfToText(unittest.TestCase):
    def test_none_renders_as_empty(self):
        self.assertEqual(jc.adf_to_text(None), "")

    def test_a_plain_string_passes_through(self):
        self.assertEqual(jc.adf_to_text("already text"), "already text")

    def test_a_single_paragraph(self):
        self.assertEqual(jc.adf_to_text(adf(para("hello world"))), "hello world")

    def test_two_paragraphs_are_blank_line_separated(self):
        self.assertEqual(jc.adf_to_text(adf(para("one"), para("two"))), "one\n\ntwo")

    def test_a_heading_renders_with_hash_markers(self):
        rendered = jc.adf_to_text(adf(heading(2, "Acceptance Criteria")))
        self.assertEqual(rendered, "## Acceptance Criteria")

    def test_bullets_render_as_dash_lines(self):
        self.assertEqual(jc.adf_to_text(adf(bullets("a", "b"))), "- a\n- b")

    def test_ordered_list_items_are_numbered(self):
        items = [{"type": "listItem", "content": [para("a")]},
                 {"type": "listItem", "content": [para("b")]}]
        node = {"type": "orderedList", "content": items}
        self.assertEqual(jc.adf_to_text(adf(node)), "1. a\n2. b")

    def test_a_hard_break_becomes_a_newline(self):
        node = {"type": "paragraph", "content": [
            {"type": "text", "text": "a"},
            {"type": "hardBreak"},
            {"type": "text", "text": "b"}]}
        self.assertEqual(jc.adf_to_text(adf(node)), "a\nb")

    def test_a_code_block_is_fenced(self):
        node = {"type": "codeBlock", "attrs": {"language": "python"},
                "content": [{"type": "text", "text": "x = 1"}]}
        self.assertEqual(jc.adf_to_text(adf(node)), "```\nx = 1\n```")

    def test_a_mention_renders_with_an_at_sign(self):
        node = {"type": "paragraph", "content": [
            {"type": "mention", "attrs": {"text": "@Mia", "id": "5b1"}}]}
        self.assertEqual(jc.adf_to_text(adf(node)), "@Mia")

    def test_an_inline_card_renders_its_url(self):
        node = {"type": "paragraph", "content": [
            {"type": "inlineCard", "attrs": {"url": "https://example.com/x"}}]}
        self.assertEqual(jc.adf_to_text(adf(node)), "https://example.com/x")

    def test_an_unknown_node_type_still_renders_its_children(self):
        node = {"type": "someFutureNode", "content": [
            {"type": "text", "text": "kept"}]}
        self.assertEqual(jc.adf_to_text(adf(node)), "kept")

    def test_an_empty_document_renders_as_empty(self):
        self.assertEqual(jc.adf_to_text(adf()), "")

    def test_a_deeply_nested_structure_does_not_recurse_forever(self):
        node = para("x")
        for _ in range(30):
            node = {"type": "blockquote", "content": [node]}
        self.assertIn("x", jc.adf_to_text(adf(node)))


class TestTextToAdf(unittest.TestCase):
    """Verified against Atlassian's REST v3 addComment operation
    (fetched 2026-09-09): `body` is an ADF DOCUMENT OBJECT, never a
    plain string. Getting this wrong only fails against real Jira,
    which CI cannot catch, so the shape is pinned here."""

    def test_the_envelope_is_a_versioned_doc(self):
        doc = jc.text_to_adf("hello")
        self.assertEqual(doc["type"], "doc")
        self.assertEqual(doc["version"], 1)

    def test_one_paragraph_per_line(self):
        doc = jc.text_to_adf("one\ntwo")
        self.assertEqual(len(doc["content"]), 2)
        self.assertEqual(
            doc["content"][0],
            {"type": "paragraph",
             "content": [{"type": "text", "text": "one"}]})

    def test_a_blank_line_is_a_paragraph_with_no_content_key(self):
        # An ADF text node with an empty `text` string is invalid and
        # Jira rejects the whole document, so a blank line must not be
        # represented as an empty text node.
        doc = jc.text_to_adf("a\n\nb")
        self.assertEqual(doc["content"][1], {"type": "paragraph"})

    def test_no_text_node_is_ever_empty(self):
        doc = jc.text_to_adf("a\n\n\nb")
        for block in doc["content"]:
            for node in block.get("content") or []:
                self.assertTrue(node["text"])

    def test_empty_text_yields_a_single_empty_paragraph(self):
        self.assertEqual(
            jc.text_to_adf(""), {"type": "doc", "version": 1,
                                 "content": [{"type": "paragraph"}]})

    def test_none_is_treated_as_empty(self):
        self.assertEqual(len(jc.text_to_adf(None)["content"]), 1)

    def test_the_document_is_json_serializable(self):
        json.dumps(jc.text_to_adf("a\nb"))

    def test_markup_characters_are_carried_verbatim(self):
        doc = jc.text_to_adf("[spec-loop-intake:decision:abc123abc123]")
        self.assertEqual(
            doc["content"][0]["content"][0]["text"],
            "[spec-loop-intake:decision:abc123abc123]")

    def test_a_body_round_trips_back_through_the_reader(self):
        body = "heading [spec-loop-intake:decision:0123456789ab]\nline two"
        self.assertIn(
            "[spec-loop-intake:decision:0123456789ab]",
            jc.adf_to_text(jc.text_to_adf(body)))


def issue_bean(**fields):
    """A minimal Jira IssueBean fixture; kwargs override the `fields` object."""
    base = {"summary": "Add a widget",
            "description": adf(para("Some background.")),
            "status": {"name": "In Progress"},
            "issuetype": {"name": "Story"}}
    base.update(fields)
    return {"key": "ABC-123", "id": "10001", "fields": base}


class TestIssueUrl(unittest.TestCase):
    def test_the_key_is_appended_to_the_v3_issue_path(self):
        self.assertEqual(
            jc._issue_url("https://acme.atlassian.net", "ABC-123"),
            "https://acme.atlassian.net/rest/api/3/issue/ABC-123")

    def test_the_key_is_percent_encoded(self):
        self.assertEqual(
            jc._issue_url("https://acme.atlassian.net", "A B"),
            "https://acme.atlassian.net/rest/api/3/issue/A%20B")


class TestFindAcFieldId(unittest.TestCase):
    CATALOGUE = json.dumps([
        {"id": "summary", "name": "Summary", "custom": False},
        {"id": "customfield_10039", "name": "Acceptance Criteria", "custom": True},
    ]).encode("utf-8")

    def test_it_finds_the_field_by_display_name(self):
        with mock.patch.object(jc, "_http_get", return_value=self.CATALOGUE):
            self.assertEqual(
                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"),
                "customfield_10039")

    def test_the_name_match_is_case_insensitive(self):
        payload = json.dumps(
            [{"id": "customfield_1", "name": "ACCEPTANCE criteria"}]).encode("utf-8")
        with mock.patch.object(jc, "_http_get", return_value=payload):
            self.assertEqual(
                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"),
                "customfield_1")

    def test_an_absent_field_returns_none(self):
        payload = json.dumps([{"id": "summary", "name": "Summary"}]).encode("utf-8")
        with mock.patch.object(jc, "_http_get", return_value=payload):
            self.assertIsNone(
                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"))

    def test_a_403_on_the_catalogue_degrades_to_none_rather_than_failing(self):
        forbidden = jc.JiraError("HTTP 403")
        with mock.patch.object(jc, "_http_get", side_effect=forbidden):
            self.assertIsNone(
                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"))

    def test_a_non_list_catalogue_degrades_to_none(self):
        with mock.patch.object(jc, "_http_get", return_value=b'{"oops": 1}'):
            self.assertIsNone(
                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"))

    def test_a_catalogue_entry_that_is_not_an_object_is_skipped(self):
        payload = json.dumps(
            ["junk", {"id": "customfield_2", "name": "Acceptance Criteria"}]
        ).encode("utf-8")
        with mock.patch.object(jc, "_http_get", return_value=payload):
            self.assertEqual(
                jc.find_ac_field_id("https://acme.atlassian.net", "e", "t"),
                "customfield_2")


class TestFetchIssue(unittest.TestCase):
    def test_it_requests_the_default_field_set(self):
        payload = json.dumps(issue_bean()).encode("utf-8")
        with mock.patch.object(jc, "_http_get", return_value=payload) as get:
            jc.fetch_issue("https://acme.atlassian.net", ("e", "t"), "ABC-123", None)
        url = get.call_args.args[0]
        self.assertIn("fields=summary%2Cdescription%2Cstatus%2Cissuetype", url)

    def test_the_ac_field_id_is_appended_to_the_field_set(self):
        payload = json.dumps(issue_bean()).encode("utf-8")
        with mock.patch.object(jc, "_http_get", return_value=payload) as get:
            jc.fetch_issue(
                "https://acme.atlassian.net", ("e", "t"), "ABC-123",
                "customfield_10039")
        self.assertIn("customfield_10039", get.call_args.args[0])

    def test_an_invalid_key_is_rejected_before_any_request(self):
        with mock.patch.object(jc, "_http_get") as get:
            with self.assertRaises(jc.JiraUsageError):
                jc.fetch_issue("https://acme.atlassian.net", ("e", "t"), "../x", None)
        get.assert_not_called()

    def test_a_malformed_payload_raises(self):
        with mock.patch.object(jc, "_http_get", return_value=b"nope"):
            with self.assertRaises(jc.JiraError):
                jc.fetch_issue("https://acme.atlassian.net", ("e", "t"), "ABC-1", None)


class TestAcceptanceCriteria(unittest.TestCase):
    DESC = ("Some background.\n\n"
            "## Acceptance Criteria\n\n"
            "- one\n- two\n\n"
            "## Notes\n\nignore me")

    def test_the_description_section_is_extracted(self):
        self.assertEqual(
            jc.acceptance_criteria_from_description(self.DESC), "- one\n- two")

    def test_the_heading_match_is_case_insensitive_and_colon_tolerant(self):
        text = "### acceptance criteria:\n\n- x"
        self.assertEqual(jc.acceptance_criteria_from_description(text), "- x")

    def test_an_absent_section_yields_empty(self):
        self.assertEqual(
            jc.acceptance_criteria_from_description("just prose"), "")

    def test_a_trailing_section_runs_to_the_end_of_the_text(self):
        text = "## Acceptance Criteria\n\n- last"
        self.assertEqual(jc.acceptance_criteria_from_description(text), "- last")

    def test_the_custom_field_wins_over_the_description(self):
        issue = issue_bean(customfield_10039=adf(para("from the field")))
        text, source = jc.resolve_acceptance_criteria(
            issue, "customfield_10039", self.DESC)
        self.assertEqual(text, "from the field")
        self.assertEqual(source, "field")

    def test_a_plain_string_custom_field_is_accepted(self):
        issue = issue_bean(customfield_10039="plain AC text")
        text, source = jc.resolve_acceptance_criteria(issue, "customfield_10039", "")
        self.assertEqual((text, source), ("plain AC text", "field"))

    def test_an_empty_custom_field_falls_back_to_the_description(self):
        issue = issue_bean(customfield_10039=None)
        text, source = jc.resolve_acceptance_criteria(
            issue, "customfield_10039", self.DESC)
        self.assertEqual((text, source), ("- one\n- two", "description"))

    def test_an_unrenderable_field_shape_falls_back_to_the_description(self):
        issue = issue_bean(customfield_10039=[{"value": "multi-select"}])
        text, source = jc.resolve_acceptance_criteria(
            issue, "customfield_10039", self.DESC)
        self.assertEqual((text, source), ("- one\n- two", "description"))

    def test_no_field_and_no_section_yields_empty_and_no_source(self):
        text, source = jc.resolve_acceptance_criteria(issue_bean(), None, "prose")
        self.assertEqual((text, source), ("", ""))


def raw_comment(cid, text, author="Mia Krystof"):
    """A minimal Jira comment fixture in REST v3 shape (ADF body)."""
    return {"id": str(cid),
            "author": {"displayName": author, "accountId": "5b10a284"},
            "body": adf(para(text)),
            "created": "2021-01-17T12:34:00.000+0000",
            "updated": "2021-01-18T23:45:00.000+0000"}


def comment_page(start, total, comments, max_results=100):
    """A PageOfComments payload -- note the key is `comments`, not `values`."""
    payload = {"startAt": start, "maxResults": max_results,
               "total": total, "comments": comments}
    return json.dumps(payload).encode("utf-8")


class TestFetchComments(unittest.TestCase):
    def test_a_single_page_is_normalized(self):
        page = comment_page(0, 1, [raw_comment(10000, "hello")])
        with mock.patch.object(jc, "_http_get", return_value=page):
            got = jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
        self.assertEqual(got, [{
            "id": "10000", "author": "Mia Krystof",
            "created": "2021-01-17T12:34:00.000+0000",
            "updated": "2021-01-18T23:45:00.000+0000",
            "body": "hello"}])

    def test_every_page_is_followed_until_total_is_reached(self):
        pages = [
            comment_page(0, 3, [raw_comment(1, "a"), raw_comment(2, "b")]),
            comment_page(2, 3, [raw_comment(3, "c")]),
        ]
        with mock.patch.object(jc, "_http_get", side_effect=pages) as get:
            got = jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
        self.assertEqual([c["id"] for c in got], ["1", "2", "3"])
        self.assertEqual(get.call_count, 2)

    def test_the_first_request_asks_for_the_configured_page_size(self):
        page = comment_page(0, 0, [])
        with mock.patch.object(jc, "_http_get", return_value=page) as get:
            jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
        url = get.call_args.args[0]
        self.assertIn("/rest/api/3/issue/ABC-1/comment?", url)
        self.assertIn("startAt=0", url)
        self.assertIn("maxResults=%d" % jc.COMMENT_PAGE_SIZE, url)

    def test_the_second_request_advances_start_at(self):
        pages = [comment_page(0, 3, [raw_comment(1, "a"), raw_comment(2, "b")]),
                 comment_page(2, 3, [raw_comment(3, "c")])]
        with mock.patch.object(jc, "_http_get", side_effect=pages) as get:
            jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
        self.assertIn("startAt=2", get.call_args_list[1].args[0])

    def test_no_comments_yields_an_empty_list(self):
        with mock.patch.object(jc, "_http_get", return_value=comment_page(0, 0, [])):
            self.assertEqual(
                jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1"), [])

    def test_an_empty_page_short_circuits_a_lying_total(self):
        pages = [comment_page(0, 999, [raw_comment(1, "a")]),
                 comment_page(1, 999, [])]
        with mock.patch.object(jc, "_http_get", side_effect=pages) as get:
            got = jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
        self.assertEqual(len(got), 1)
        self.assertEqual(get.call_count, 2)

    def test_a_runaway_server_is_capped_by_max_pages(self):
        endless = comment_page(0, 10 ** 9, [raw_comment(1, "a")])
        with mock.patch.object(jc, "_http_get", return_value=endless) as get:
            with self.assertRaises(jc.JiraError) as ctx:
                jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
        self.assertEqual(get.call_count, jc.MAX_COMMENT_PAGES)
        self.assertIn("pages", str(ctx.exception))

    def test_a_missing_author_object_renders_as_empty(self):
        c = raw_comment(1, "a")
        del c["author"]
        with mock.patch.object(jc, "_http_get", return_value=comment_page(0, 1, [c])):
            got = jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
        self.assertEqual(got[0]["author"], "")

    def test_a_page_missing_the_comments_key_raises(self):
        body = {"startAt": 0, "maxResults": 100, "total": 1, "values": []}
        payload = json.dumps(body).encode("utf-8")
        with mock.patch.object(jc, "_http_get", return_value=payload):
            with self.assertRaises(jc.JiraError):
                jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")

    def test_a_page_missing_total_raises_rather_than_truncating(self):
        # int(page.get("total") or 0) used to collapse a missing `total` to
        # 0, making a single non-empty page look complete and silently
        # truncating the sweep -- this must fail closed instead.
        body = {"startAt": 0, "maxResults": 100,
                "comments": [raw_comment(1, "a")]}
        payload = json.dumps(body).encode("utf-8")
        with mock.patch.object(jc, "_http_get", return_value=payload) as get:
            with self.assertRaises(jc.JiraError):
                jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")
        self.assertEqual(get.call_count, 1)

    def test_a_non_numeric_total_raises_a_jira_error(self):
        body = {"startAt": 0, "maxResults": 100, "total": "not-a-number",
                "comments": [raw_comment(1, "a")]}
        payload = json.dumps(body).encode("utf-8")
        with mock.patch.object(jc, "_http_get", return_value=payload):
            with self.assertRaises(jc.JiraError):
                jc.fetch_comments("https://acme.atlassian.net", "e", "t", "ABC-1")

    def test_an_invalid_key_is_rejected_before_any_request(self):
        with mock.patch.object(jc, "_http_get") as get:
            with self.assertRaises(jc.JiraUsageError):
                jc.fetch_comments("https://acme.atlassian.net", "e", "t", "x/y")
        get.assert_not_called()


MARKER = "[spec-loop-intake:decision:0123456789ab]"


def entry(kind="decision", marker=MARKER, body=None):
    """One comment entry in the shape jira_intake.build_comment_bodies
    prints: the marker always lives inside the body."""
    return {"kind": kind, "marker": marker,
            "body": body if body is not None else
            "spec-loop intake - decision %s\nRecorded X.\n\npayload" % marker}


class TestCommentEntryValidation(unittest.TestCase):
    def test_a_well_formed_entry_has_no_errors(self):
        self.assertEqual(jc.validate_comment_entries([entry()]), [])

    def test_an_empty_list_is_refused(self):
        self.assertNotEqual(jc.validate_comment_entries([]), [])

    def test_a_non_list_is_refused(self):
        self.assertNotEqual(jc.validate_comment_entries({"a": 1}), [])

    def test_a_non_object_entry_is_refused(self):
        errors = jc.validate_comment_entries(["nope"])
        self.assertIn("comments[0]", errors[0])

    def test_a_missing_body_is_refused(self):
        bad = entry()
        del bad["body"]
        self.assertNotEqual(jc.validate_comment_entries([bad]), [])

    def test_a_marker_of_the_wrong_shape_is_refused(self):
        errors = jc.validate_comment_entries(
            [entry(marker="[not-a-marker]", body="[not-a-marker] x")])
        self.assertTrue(any("marker" in e for e in errors), errors)

    def test_a_marker_of_an_unknown_kind_is_refused(self):
        bad = "[spec-loop-intake:transition:0123456789ab]"
        self.assertNotEqual(
            jc.validate_comment_entries([entry(marker=bad, body=bad)]), [])

    def test_a_body_that_lost_its_marker_is_refused(self):
        errors = jc.validate_comment_entries(
            [entry(body="a body with no marker in it")])
        self.assertTrue(any("marker" in e for e in errors), errors)

    def test_a_real_intake_body_validates(self):
        # Proves the shape contract with the module that produces it.
        import jira_intake as intake
        built = intake.build_comment_bodies(
            {"key": "ABC-1",
             "web_url": "https://acme.atlassian.net/browse/ABC-1",
             "summary": "s", "description": "d",
             "acceptance_criteria": "", "acceptance_criteria_source": "",
             "status": "Open", "issue_type": "Task", "comments": []},
            {"description": "d", "acceptance_criteria": ["a"],
             "risks": [], "gaps": [], "injection_findings": [],
             "answers": {}},
            "2026-09-09T00:00:00Z")
        self.assertEqual(jc.validate_comment_entries(built), [])


class TestPlanComments(unittest.TestCase):
    """The dedupe gate is the card's own comment list, read back over the
    network -- never a local file."""

    def test_an_empty_card_leaves_everything_pending(self):
        plan = jc.plan_comments([entry()], [])
        self.assertEqual(plan, [{"kind": "decision", "marker": MARKER,
                                 "already_posted": False}])

    def test_a_marker_already_on_the_card_is_already_posted(self):
        plan = jc.plan_comments([entry()], ["old", entry()["body"]])
        self.assertTrue(plan[0]["already_posted"])

    def test_a_marker_on_a_later_page_still_matches(self):
        plan = jc.plan_comments(
            [entry()], ["a", "b", "c", "noise " + MARKER + " noise"])
        self.assertTrue(plan[0]["already_posted"])

    def test_a_different_marker_does_not_match(self):
        other = "[spec-loop-intake:decision:ffffffffffff]"
        plan = jc.plan_comments([entry()], [other])
        self.assertFalse(plan[0]["already_posted"])

    def test_the_plan_preserves_input_order_and_length(self):
        second = entry(kind="open-question",
                       marker="[spec-loop-intake:open-question:aaaaaaaaaaaa]",
                       body="x [spec-loop-intake:open-question:aaaaaaaaaaaa]")
        plan = jc.plan_comments([entry(), second], [entry()["body"]])
        self.assertEqual([p["already_posted"] for p in plan], [True, False])
        self.assertEqual([p["kind"] for p in plan],
                         ["decision", "open-question"])


ENV = {"JIRA_BASE_URL": "https://acme.atlassian.net",
       "JIRA_EMAIL": "fred@example.com",
       "JIRA_API_TOKEN": "s3cr3t-api-token-value"}


def card_with(bodies):
    """One comment page whose comments carry `bodies`, as bytes."""
    return comment_page(
        0, len(bodies),
        [raw_comment(i + 1, text) for i, text in enumerate(bodies)])


class TestPostComment(unittest.TestCase):
    """The plugin's sole writer. Bounded to ADDING a comment."""

    SITE = "https://acme.atlassian.net"

    def _post(self, body, response=b'{"id": "10001"}'):
        """post_comment against a mocked transport: (mock, returned id)."""
        with mock.patch.object(
                jc, "_http_post", return_value=response) as post:
            created = jc.post_comment(
                self.SITE, ("e", "t"), "ABC-1", body)
        return post, created

    def test_the_url_is_the_issue_comment_collection(self):
        post, _ = self._post("body " + MARKER)
        self.assertEqual(
            post.call_args.args[0],
            self.SITE + "/rest/api/3/issue/ABC-1/comment")

    def test_the_payload_body_is_an_adf_document_not_a_string(self):
        post, _ = self._post("line one\nline two")
        payload = post.call_args.args[3]
        self.assertEqual(payload["body"]["type"], "doc")
        self.assertEqual(payload["body"]["version"], 1)

    def test_the_marker_rides_inside_the_posted_document(self):
        post, _ = self._post(MARKER + "\npayload")
        self.assertIn(MARKER, json.dumps(post.call_args.args[3]))

    def test_the_created_comment_id_is_returned(self):
        _, created = self._post("b")
        self.assertEqual(created, "10001")

    def test_a_response_without_an_id_is_refused(self):
        with self.assertRaises(jc.JiraError):
            self._post("b", b'{}')

    def test_a_non_object_response_is_refused(self):
        with self.assertRaises(jc.JiraError):
            self._post("b", b'[]')

    def test_an_invalid_key_is_rejected_before_any_request(self):
        with mock.patch.object(jc, "_http_post") as post:
            with self.assertRaises(jc.JiraUsageError):
                jc.post_comment(self.SITE, ("e", "t"), "x/y", "b")
        post.assert_not_called()


class TestRunCommentLane(unittest.TestCase):
    """(a) off by default, (b) dedupe against the card's own full comment
    list, (c) the marker is written by the POST itself, (e) fail closed
    with nothing partial."""

    def setUp(self):
        self.entries = [
            entry(),
            entry(kind="open-question",
                  marker="[spec-loop-intake:open-question:aaaaaaaaaaaa]",
                  body="q [spec-loop-intake:open-question:aaaaaaaaaaaa]")]

    def _run(self, existing, arm, post=None):
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.dict(jc.os.environ, ENV, clear=True))
            stack.enter_context(mock.patch.object(
                jc, "_http_get", return_value=card_with(existing)))
            poster = stack.enter_context(mock.patch.object(
                jc, "_http_post",
                **(post or {"return_value": b'{"id": "10001"}'})))
            payload = jc.run_comment_lane("ABC-1", self.entries, arm)
        return payload, poster

    def _statuses(self, payload):
        """The per-comment status of a lane payload, in request order."""
        return [result["status"] for result in payload["results"]]

    def test_the_default_path_issues_zero_posts(self):
        payload, poster = self._run([], arm=False)
        poster.assert_not_called()
        self.assertFalse(payload["armed"])
        self.assertEqual(payload["posted_count"], 0)
        self.assertEqual(
            self._statuses(payload), ["would-post", "would-post"])

    def test_arming_posts_every_pending_comment(self):
        payload, poster = self._run([], arm=True)
        self.assertEqual(poster.call_count, 2)
        self.assertEqual(payload["posted_count"], 2)
        self.assertEqual(self._statuses(payload), ["posted", "posted"])
        self.assertEqual(payload["results"][0]["comment_id"], "10001")

    def test_a_second_identical_run_issues_zero_posts(self):
        already = [e["body"] for e in self.entries]
        payload, poster = self._run(already, arm=True)
        poster.assert_not_called()
        self.assertEqual(payload["posted_count"], 0)
        self.assertEqual(payload["already_posted_count"], 2)
        self.assertEqual(
            self._statuses(payload), ["already-posted", "already-posted"])

    def test_a_partly_posted_card_only_posts_the_remainder(self):
        payload, poster = self._run([self.entries[0]["body"]], arm=True)
        self.assertEqual(poster.call_count, 1)
        self.assertEqual(
            self._statuses(payload), ["already-posted", "posted"])

    def test_an_invalid_entry_refuses_before_any_request(self):
        self.entries[1]["body"] = "a body with no marker"
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.dict(jc.os.environ, ENV, clear=True))
            get = stack.enter_context(mock.patch.object(jc, "_http_get"))
            post = stack.enter_context(mock.patch.object(jc, "_http_post"))
            with self.assertRaises(jc.JiraError):
                jc.run_comment_lane("ABC-1", self.entries, True)
        get.assert_not_called()
        post.assert_not_called()

    def test_a_failing_post_stops_the_sequence(self):
        refused = {"side_effect": jc.JiraError("HTTP 403")}
        with self.assertRaises(jc.JiraError):
            self._run([], arm=True, post=refused)

    def test_a_failing_post_never_reaches_the_next_comment(self):
        outcomes = [b'{"id": "1"}', jc.JiraError("HTTP 403")]
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.dict(jc.os.environ, ENV, clear=True))
            stack.enter_context(mock.patch.object(
                jc, "_http_get", return_value=card_with([])))
            poster = stack.enter_context(mock.patch.object(
                jc, "_http_post", side_effect=outcomes))
            with self.assertRaises(jc.JiraError):
                jc.run_comment_lane("ABC-1", self.entries, True)
        self.assertEqual(poster.call_count, 2)

    def test_a_truncated_comment_sweep_refuses_before_any_post(self):
        # fetch_comments' fail-closed `total` guard is what makes dedupe
        # trustworthy: a page with no numeric total must abort the lane.
        body = json.dumps(
            {"startAt": 0, "maxResults": 100,
             "comments": [raw_comment(1, "a")]}).encode("utf-8")
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.dict(jc.os.environ, ENV, clear=True))
            stack.enter_context(
                mock.patch.object(jc, "_http_get", return_value=body))
            post = stack.enter_context(mock.patch.object(jc, "_http_post"))
            with self.assertRaises(jc.JiraError):
                jc.run_comment_lane("ABC-1", self.entries, True)
        post.assert_not_called()

    def test_missing_credentials_refuse_before_any_request(self):
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.dict(jc.os.environ, {}, clear=True))
            get = stack.enter_context(mock.patch.object(jc, "_http_get"))
            post = stack.enter_context(mock.patch.object(jc, "_http_post"))
            with self.assertRaises(jc.JiraUsageError):
                jc.run_comment_lane("ABC-1", self.entries, True)
        get.assert_not_called()
        post.assert_not_called()


class TestNormalizedRecord(unittest.TestCase):
    VALUES = {"key": "ABC-123",
              "web_url": "https://acme.atlassian.net/browse/ABC-123",
              "summary": "Add a widget", "description": "Some background.",
              "acceptance_criteria": "- one", "acceptance_criteria_source": "field",
              "status": "In Progress", "issue_type": "Story", "comments": []}

    def test_the_record_has_exactly_the_contract_fields_in_order(self):
        self.assertEqual(list(jc._normalized(self.VALUES)), list(jc.RECORD_FIELDS))

    def test_an_empty_description_is_allowed(self):
        rec = jc._normalized(dict(self.VALUES, description=""))
        self.assertEqual(rec["description"], "")

    def test_an_empty_comment_list_is_allowed(self):
        self.assertEqual(jc._normalized(self.VALUES)["comments"], [])

    def test_each_required_field_being_empty_is_a_half_resolve(self):
        for field in jc.REQUIRED_FIELDS:
            with self.subTest(field=field), \
                 self.assertRaises(jc.JiraError) as ctx:
                jc._normalized(dict(self.VALUES, **{field: ""}))
            self.assertIn(field, str(ctx.exception))


class TestResolveIssue(unittest.TestCase):
    ENV = {"JIRA_BASE_URL": "https://acme.atlassian.net",
           "JIRA_EMAIL": "fred@example.com",
           "JIRA_API_TOKEN": "tok"}

    def _resolve(self, issue=None, comments=None, ac_field_id=None):
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.dict(jc.os.environ, self.ENV, clear=True))
            stack.enter_context(mock.patch.object(
                jc, "find_ac_field_id", return_value=ac_field_id))
            stack.enter_context(mock.patch.object(
                jc, "fetch_issue", return_value=issue if issue else issue_bean()))
            stack.enter_context(mock.patch.object(
                jc, "fetch_comments", return_value=comments or []))
            return jc.resolve_issue("ABC-123")

    def test_the_full_record_is_assembled(self):
        comment = {"id": "1", "author": "Mia", "created": "c",
                  "updated": "u", "body": "hi"}
        rec = self._resolve(comments=[comment])
        self.assertEqual(rec["key"], "ABC-123")
        self.assertEqual(rec["summary"], "Add a widget")
        self.assertEqual(rec["status"], "In Progress")
        self.assertEqual(rec["issue_type"], "Story")
        self.assertEqual(rec["description"], "Some background.")
        self.assertEqual(
            rec["web_url"], "https://acme.atlassian.net/browse/ABC-123")
        self.assertEqual(len(rec["comments"]), 1)

    def test_the_server_returned_key_wins_over_the_requested_one(self):
        rec = self._resolve(issue=dict(issue_bean(), key="MOVED-9"))
        self.assertEqual(rec["key"], "MOVED-9")
        self.assertEqual(
            rec["web_url"], "https://acme.atlassian.net/browse/MOVED-9")

    def test_a_missing_status_is_a_half_resolve(self):
        with self.assertRaises(jc.JiraError):
            self._resolve(issue=issue_bean(status={}))

    def test_missing_credentials_raise_a_usage_error_before_any_call(self):
        with mock.patch.dict(jc.os.environ, {}, clear=True), \
             mock.patch.object(jc, "fetch_issue") as fetch:
            with self.assertRaises(jc.JiraUsageError):
                jc.resolve_issue("ABC-123")
        fetch.assert_not_called()


class TestMain(unittest.TestCase):
    """The two refusal shapes match dag.py / run_state.py's established
    idiom: a contract failure (exit 1) prints JSON to STDOUT; a usage
    failure (exit 2) prints plain 'error: %s' text to STDERR."""

    RECORD = {"key": "ABC-123", "web_url": "https://acme.atlassian.net/browse/ABC-123",
              "summary": "s", "description": "", "acceptance_criteria": "",
              "acceptance_criteria_source": "", "status": "Open",
              "issue_type": "Task", "comments": []}

    def _run(self, argv, **patches):
        with ExitStack() as stack:
            so = stack.enter_context(mock.patch.object(jc.sys, "stdout"))
            se = stack.enter_context(mock.patch.object(jc.sys, "stderr"))
            stack.enter_context(mock.patch.object(jc, "resolve_issue", **patches))
            rc = jc.main(argv)
            out = "".join(c.args[0] for c in so.write.call_args_list if c.args)
            err = "".join(c.args[0] for c in se.write.call_args_list if c.args)
        return rc, out, err

    def test_success_prints_one_json_object_and_exits_zero(self):
        rc, out, _ = self._run(
            ["resolve", "--key", "ABC-123"], return_value=self.RECORD)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), self.RECORD)

    def test_a_usage_error_exits_two_as_plain_text_on_stderr(self):
        rc, out, err = self._run(
            ["resolve", "--key", "ABC-123"],
            side_effect=jc.JiraUsageError("no creds"))
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertEqual(err, "error: no creds\n")

    def test_a_contract_error_exits_one_as_json_on_stdout(self):
        rc, out, err = self._run(
            ["resolve", "--key", "ABC-123"],
            side_effect=jc.JiraError("HTTP 500"))
        self.assertEqual(rc, 1)
        self.assertEqual(err, "")
        self.assertEqual(json.loads(out), {"ok": False, "errors": ["HTTP 500"]})

    def test_secrets_never_reach_stdout_or_stderr(self):
        token, email = "s3cr3t-api-token-value", "fred@example.com"
        composed = base64.b64encode(
            f"{email}:{token}".encode("utf-8")).decode("ascii")
        env = {"JIRA_BASE_URL": "https://acme.atlassian.net",
               "JIRA_EMAIL": email, "JIRA_API_TOKEN": token}
        opener = mock.MagicMock()
        opener.open.side_effect = urllib.error.URLError("connection refused")
        with ExitStack() as stack:
            stack.enter_context(mock.patch.dict(jc.os.environ, env, clear=True))
            stack.enter_context(mock.patch.object(jc, "_OPENER", opener))
            so = stack.enter_context(mock.patch.object(jc.sys, "stdout"))
            se = stack.enter_context(mock.patch.object(jc.sys, "stderr"))
            rc = jc.main(["resolve", "--key", "ABC-123"])
            out = "".join(c.args[0] for c in so.write.call_args_list if c.args)
            err = "".join(c.args[0] for c in se.write.call_args_list if c.args)
        self.assertNotEqual(rc, 0)
        for secret in (token, email, composed):
            self.assertNotIn(secret, out)
            self.assertNotIn(secret, err)


class TestCommentCli(unittest.TestCase):
    """Posting is off by default at the CLI boundary too: --post is what
    arms the write."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.path = str(Path(self.dir) / "comments.json")

    def _write(self, payload):
        Path(self.path).write_text(
            json.dumps(payload), encoding="utf-8")

    def _run(self, argv, **patches):
        with ExitStack() as stack:
            so = stack.enter_context(mock.patch.object(jc.sys, "stdout"))
            se = stack.enter_context(mock.patch.object(jc.sys, "stderr"))
            lane = stack.enter_context(
                mock.patch.object(jc, "run_comment_lane", **patches))
            rc = jc.main(argv)
            out = "".join(c.args[0] for c in so.write.call_args_list if c.args)
            err = "".join(c.args[0] for c in se.write.call_args_list if c.args)
        return rc, out, err, lane

    PAYLOAD = {"ok": True, "issue_key": "ABC-1", "armed": False,
               "posted_count": 0, "already_posted_count": 0, "results": []}

    def test_without_the_flag_the_lane_is_not_armed(self):
        self._write([entry()])
        _, _, _, lane = self._run(
            ["comment", "--key", "ABC-1", "--comments", self.path],
            return_value=self.PAYLOAD)
        self.assertIs(lane.call_args.args[2], False)

    def test_the_post_flag_arms_the_lane(self):
        self._write([entry()])
        _, _, _, lane = self._run(
            ["comment", "--key", "ABC-1", "--comments", self.path, "--post"],
            return_value=self.PAYLOAD)
        self.assertIs(lane.call_args.args[2], True)

    def test_success_prints_one_json_object_and_exits_zero(self):
        self._write([entry()])
        rc, out, _, _ = self._run(
            ["comment", "--key", "ABC-1", "--comments", self.path],
            return_value=self.PAYLOAD)
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), self.PAYLOAD)

    def test_the_full_render_payload_object_is_accepted(self):
        self._write({"ok": True, "comments": [entry()]})
        _, _, _, lane = self._run(
            ["comment", "--key", "ABC-1", "--comments", self.path],
            return_value=self.PAYLOAD)
        self.assertEqual(lane.call_args.args[1], [entry()])

    def test_a_missing_comments_file_exits_two(self):
        rc, out, err, _ = self._run(
            ["comment", "--key", "ABC-1",
             "--comments", str(Path(self.dir) / "nope.json")],
            return_value=self.PAYLOAD)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("error:", err)

    def test_a_malformed_comments_file_exits_two(self):
        Path(self.path).write_text("not json", encoding="utf-8")
        rc, _, err, _ = self._run(
            ["comment", "--key", "ABC-1", "--comments", self.path],
            return_value=self.PAYLOAD)
        self.assertEqual(rc, 2)
        self.assertIn("error:", err)

    def test_a_contract_failure_exits_one_as_json_on_stdout(self):
        self._write([entry()])
        rc, out, err, _ = self._run(
            ["comment", "--key", "ABC-1", "--comments", self.path],
            side_effect=jc.JiraError("HTTP 403"))
        self.assertEqual(rc, 1)
        self.assertEqual(err, "")
        self.assertEqual(json.loads(out),
                         {"ok": False, "errors": ["HTTP 403"]})

    def test_there_is_no_credential_flag_anywhere(self):
        help_text = jc.build_parser().format_help()
        for banned in ("--token", "--email", "--password", "--api-token"):
            self.assertNotIn(banned, help_text)


class TestTheReadLaneStaysReadOnly(unittest.TestCase):
    """j3 adds ONE bounded writer. The read lane's guarantee is unchanged
    and is asserted against _http_get's OWN source rather than the whole
    file, so the new writer cannot silently loosen it."""

    SOURCE = (Path(__file__).resolve().parent / "jira_client.py").read_text()
    MUTATING_VERBS = ('"POST"', '"PUT"', '"PATCH"', '"DELETE"',
                      "'POST'", "'PUT'", "'PATCH'", "'DELETE'")

    def test_the_get_helper_names_no_mutating_verb(self):
        source = inspect.getsource(jc._http_get)
        for verb in self.MUTATING_VERBS:
            self.assertNotIn(verb, source, verb)

    def test_the_get_helper_sets_no_body_and_pins_get(self):
        source = inspect.getsource(jc._http_get)
        self.assertNotIn("data=", source)
        self.assertIn('method="GET"', source)

    def test_no_read_function_can_reach_the_writer(self):
        for fn in (jc.find_ac_field_id, jc.fetch_issue, jc.fetch_comments,
                   jc.resolve_issue):
            with self.subTest(fn=fn.__name__):
                self.assertNotIn("_http_post", inspect.getsource(fn))

    def test_the_module_never_imports_subprocess(self):
        self.assertNotIn("import subprocess", self.SOURCE)

    def test_the_module_never_calls_datetime_now(self):
        self.assertNotIn("datetime", self.SOURCE.replace("# ", ""))

    def test_the_only_mutating_verb_in_the_module_is_the_comment_post(self):
        for verb in ('"PUT"', '"PATCH"', '"DELETE"',
                     "'PUT'", "'PATCH'", "'DELETE'"):
            self.assertNotIn(verb, self.SOURCE, verb)
        self.assertEqual(self.SOURCE.count('method="POST"'), 1)

    def test_there_are_exactly_two_transports(self):
        self.assertEqual(self.SOURCE.count("urllib.request.Request("), 2)
        self.assertEqual(self.SOURCE.count("_OPENER.open("), 2)

    def test_the_entry_shim_is_exactly_two_lines(self):
        all_lines = self.SOURCE.splitlines()
        shim_lines = [ln for ln in all_lines if ln.startswith("if __name__")]
        self.assertEqual(len(shim_lines), 1)
        idx = all_lines.index(shim_lines[0])
        self.assertEqual(all_lines[idx + 1].strip(), "sys.exit(main())")


if __name__ == "__main__":
    unittest.main()
