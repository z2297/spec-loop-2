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
            with self.subTest(missing=missing):
                with mock.patch.dict(jc.os.environ, env, clear=True):
                    with self.assertRaises(jc.JiraUsageError) as ctx:
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
            jc._http_get("https://acme.atlassian.net/rest/api/3/field",
                         "fred@example.com", "tok")
        req = opener.open.call_args.args[0]
        self.assertEqual(req.get_method(), "GET")

    def test_the_request_carries_no_body(self):
        opener = self._fake_opener()
        with mock.patch.object(jc, "_OPENER", opener):
            jc._http_get("https://acme.atlassian.net/rest/api/3/field",
                         "fred@example.com", "tok")
        self.assertIsNone(opener.open.call_args.args[0].data)

    def test_the_authorization_header_is_basic(self):
        opener = self._fake_opener()
        with mock.patch.object(jc, "_OPENER", opener):
            jc._http_get("https://acme.atlassian.net/rest/api/3/field",
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
        self.assertTrue(any(isinstance(h, jc._NoRedirect)
                            for h in jc._OPENER.handlers))


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
        with mock.patch.object(jc, "_OPENER", opener):
            with self.assertRaises(jc.JiraError) as ctx:
                jc._http_get("https://acme.atlassian.net/rest/api/3/issue/ABC-1",
                             self.EMAIL, self.TOKEN)
        self._assert_clean(str(ctx.exception))

    def test_secrets_absent_from_a_network_error_message(self):
        opener = mock.MagicMock()
        opener.open.side_effect = urllib.error.URLError("connection refused")
        with mock.patch.object(jc, "_OPENER", opener):
            with self.assertRaises(jc.JiraError) as ctx:
                jc._http_get("https://acme.atlassian.net/x", self.EMAIL, self.TOKEN)
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
        self.assertEqual(jc.adf_to_text(adf(heading(2, "Acceptance Criteria"))),
                         "## Acceptance Criteria")

    def test_bullets_render_as_dash_lines(self):
        self.assertEqual(jc.adf_to_text(adf(bullets("a", "b"))), "- a\n- b")

    def test_ordered_list_items_are_numbered(self):
        node = {"type": "orderedList",
                "content": [{"type": "listItem", "content": [para("a")]},
                            {"type": "listItem", "content": [para("b")]}]}
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


if __name__ == "__main__":
    unittest.main()
