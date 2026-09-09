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
import json
import sys
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


class TestReadOnlyContract(unittest.TestCase):
    """The module must be structurally incapable of mutating Jira."""

    SOURCE = (Path(__file__).resolve().parent / "jira_client.py").read_text()

    def test_the_module_never_imports_subprocess(self):
        self.assertNotIn("import subprocess", self.SOURCE)

    def test_the_module_never_calls_datetime_now(self):
        self.assertNotIn("datetime", self.SOURCE.replace("# ", ""))

    MUTATING_VERBS = ('"POST"', '"PUT"', '"PATCH"', '"DELETE"',
                      "'POST'", "'PUT'", "'PATCH'", "'DELETE'")

    def test_no_mutating_http_method_appears_in_the_source(self):
        for verb in self.MUTATING_VERBS:
            self.assertNotIn(verb, self.SOURCE, verb)

    def test_the_only_request_construction_sets_method_get(self):
        self.assertEqual(self.SOURCE.count("urllib.request.Request("), 1)
        self.assertIn('method="GET"', self.SOURCE)

    def test_the_only_network_call_goes_through_the_module_opener(self):
        self.assertEqual(self.SOURCE.count("_OPENER.open("), 1)

    def test_the_entry_shim_is_exactly_two_lines(self):
        all_lines = self.SOURCE.splitlines()
        shim_lines = [ln for ln in all_lines if ln.startswith("if __name__")]
        self.assertEqual(len(shim_lines), 1)
        idx = all_lines.index(shim_lines[0])
        self.assertEqual(all_lines[idx + 1].strip(), "sys.exit(main())")

if __name__ == "__main__":
    unittest.main()
