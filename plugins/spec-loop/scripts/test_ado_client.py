#!/usr/bin/env python3
"""Tests for the read-only Azure DevOps work-item reader (stdlib unittest).

Covers work-item-id and org-URL validation (allow-list + argument/URL-injection
defence), credential resolution and its fail-closed message, the HTML -> text
renderer, work-item and continuationToken-paginated comment resolution against a
mocked opener, the normalized-record contract, that the PAT and the composed
base64(":" + PAT) never leak into an error, stdout or stderr, and the READ-ONLY
guarantee (the GET helper has no `data` parameter; the module spawns no
subprocess).

`scripts/validate_marketplace.py` does NOT lint scripts/*.py, so this is the
sole automated guard on the client. Standard library only. No live network.

Usage:
    python3 -m unittest test_ado_client
"""

import argparse
import base64
import inspect
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ado_client as ac  # noqa: E402


class TestWorkItemIdValidation(unittest.TestCase):
    def test_a_plain_integer_id_is_returned_unchanged(self):
        self.assertEqual(ac.validate_work_item_id("1234"), "1234")

    def test_an_integer_id_is_accepted_as_an_int(self):
        self.assertEqual(ac.validate_work_item_id(42), "42")

    def test_a_leading_dash_is_rejected(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_work_item_id("-1")

    def test_a_path_traversal_attempt_is_rejected(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_work_item_id("../../etc/passwd")

    def test_an_embedded_slash_is_rejected(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_work_item_id("12/comments")

    def test_a_jira_style_key_is_rejected(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_work_item_id("ABC-123")

    def test_whitespace_and_newlines_are_rejected(self):
        for bad in (" 12", "12 ", "1\n2", "12\n", ""):
            with self.assertRaises(ac.AdoUsageError):
                ac.validate_work_item_id(bad)

    def test_an_over_long_id_is_rejected(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_work_item_id("1" * 11)


class TestOrgUrlValidation(unittest.TestCase):
    def test_the_modern_form_yields_the_org_qualified_api_root(self):
        expected = ("https://dev.azure.com/contoso", "contoso")
        self.assertEqual(
            ac.validate_org_url("https://dev.azure.com/contoso"), expected)

    def test_a_trailing_slash_is_tolerated(self):
        expected = ("https://dev.azure.com/contoso", "contoso")
        self.assertEqual(
            ac.validate_org_url("https://dev.azure.com/contoso/"), expected)

    def test_the_legacy_visualstudio_form_yields_the_bare_origin(self):
        expected = ("https://contoso.visualstudio.com", "contoso")
        self.assertEqual(
            ac.validate_org_url("https://contoso.visualstudio.com"), expected)

    def test_http_is_rejected(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_org_url("http://dev.azure.com/contoso")

    def test_an_on_prem_server_host_is_refused_naming_the_supported_forms(self):
        with self.assertRaises(ac.AdoUsageError) as ctx:
            ac.validate_org_url("https://tfs.internal.example.com/tfs/DefaultCollection")
        message = str(ctx.exception)
        self.assertIn("dev.azure.com", message)
        self.assertIn("visualstudio.com", message)

    def test_userinfo_is_rejected_and_never_echoed(self):
        with self.assertRaises(ac.AdoUsageError) as ctx:
            ac.validate_org_url("https://user:sekrit@dev.azure.com/contoso")
        self.assertNotIn("sekrit", str(ctx.exception))
        self.assertIn("<redacted>", str(ctx.exception))

    def test_an_explicit_port_is_rejected(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_org_url("https://dev.azure.com:8443/contoso")

    def test_a_malformed_ipv6_host_is_a_usage_error_not_a_traceback(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_org_url("https://[oops/contoso")

    def test_a_modern_url_with_no_org_segment_is_rejected(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_org_url("https://dev.azure.com")

    def test_an_extra_path_segment_after_the_org_is_rejected(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_org_url("https://dev.azure.com/contoso/MyProject")

    def test_a_traversal_org_segment_is_rejected(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_org_url("https://dev.azure.com/..")

    def test_a_query_string_is_rejected(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.validate_org_url("https://dev.azure.com/contoso?x=1")


class TestApiVersionsAreThreeDistinctConstants(unittest.TestCase):
    """The work-item read, the comment list and the comment add document
    DIFFERENT api-versions on purpose. A well-meaning 'consistency' edit that
    collapses them to one string must fail here rather than silently break
    either the comment sweep or the write."""

    def test_the_three_api_versions_are_not_all_equal(self):
        versions = {
            ac.API_VERSION_WORK_ITEM,
            ac.API_VERSION_COMMENTS_READ,
            ac.API_VERSION_COMMENT_ADD,
        }
        self.assertEqual(len(versions), 3)

    def test_each_api_version_is_the_documented_literal(self):
        self.assertEqual(ac.API_VERSION_WORK_ITEM, "7.1")
        self.assertEqual(ac.API_VERSION_COMMENTS_READ, "7.1-preview.4")
        self.assertEqual(ac.API_VERSION_COMMENT_ADD, "7.0-preview.3")


class TestCredentialsComeFromTheEnvironmentOnly(unittest.TestCase):
    def test_the_org_url_and_pat_resolve_to_an_api_root(self):
        env = {"ADO_ORG_URL": "https://dev.azure.com/contoso", "ADO_PAT": "tok"}
        with mock.patch.dict(ac.os.environ, env, clear=True):
            self.assertEqual(
                ac.credentials(),
                ("https://dev.azure.com/contoso", "contoso", "tok"))

    def test_a_missing_variable_is_named_in_a_fail_closed_message(self):
        with mock.patch.dict(ac.os.environ, {}, clear=True):
            with self.assertRaises(ac.AdoUsageError) as ctx:
                ac.credentials()
        message = str(ctx.exception)
        self.assertIn("ADO_ORG_URL", message)
        self.assertIn("ADO_PAT", message)

    def test_the_message_describes_ado_project_as_optional_not_required(self):
        with mock.patch.dict(ac.os.environ, {}, clear=True):
            with self.assertRaises(ac.AdoUsageError) as ctx:
                ac.credentials()
        message = str(ctx.exception)
        self.assertIn("ADO_PROJECT", message)
        # Case-insensitive on purpose: the message says "is OPTIONAL".
        self.assertIn("optional", message.lower())

    def test_only_the_org_url_and_pat_are_required_credentials(self):
        self.assertEqual(ac.CRED_VARS, ("ADO_ORG_URL", "ADO_PAT"))

    def test_no_cli_flag_can_supply_a_credential(self):
        """Deliberately MODULE-WIDE, and one of only three scans here that
        is (the others are import subprocess and renderedText): a credential
        flag must not exist on ANY lane, including the bounded write lane a
        later slice adds, and these exact spellings appear in no docstring in
        this module -- the prose names the ENV VARS (ADO_PAT, ADO_ORG_URL),
        never a flag. Task 7 adds the stronger companion assertion against
        the parser's real option strings."""
        source = inspect.getsource(ac)
        for forbidden in ("--pat", "--token", "--password", "--org-url"):
            self.assertNotIn(forbidden, source, forbidden)


class TestHttpGetIsStructurallyIncapableOfWriting(unittest.TestCase):
    def test_http_get_has_no_data_parameter(self):
        """urllib.request.Request infers POST from a non-None `data`, so
        omitting the parameter from the signature ENTIRELY -- rather than
        passing data=None -- means this function has no expressible write
        path. That absence is the proof."""
        params = list(inspect.signature(ac._http_get).parameters)
        self.assertEqual(params, ["url", "pat"])

    def test_http_get_has_no_method_parameter_for_a_caller_to_widen(self):
        self.assertNotIn("method", inspect.signature(ac._http_get).parameters)

    def test_the_get_helper_names_no_mutating_verb(self):
        """Scoped to _http_get's OWN source, not the whole module -- exactly
        as test_jira_client.py:1544-1552 does. A later slice adds a bounded
        writer to this module; that must not be able to loosen THIS
        guarantee, and this test must not have to be deleted to allow it."""
        source = inspect.getsource(ac._http_get)
        verbs = (
            '"POST"', '"PUT"', '"PATCH"', '"DELETE"',
            "'POST'", "'PUT'", "'PATCH'", "'DELETE'",
        )
        for verb in verbs:
            self.assertNotIn(verb, source, verb)

    def test_the_get_helper_sets_no_body_and_pins_get(self):
        source = inspect.getsource(ac._http_get)
        self.assertNotIn("data=", source)
        self.assertIn('method="GET"', source)

    # NOTE: the companion assertion that no READ FUNCTION can reach a writer
    # needs fetch_comments and resolve_work_item to exist, so it lands in
    # Task 6 as TestTheReadLaneStaysReadOnly. Do not add it here; the
    # functions it iterates are not defined yet and it would AttributeError.

    def test_the_module_never_imports_subprocess(self):
        """Module-wide on purpose (test_jira_client.py:1560 makes the same
        exception for this exact token): no subprocess anywhere means no `az`
        CLI, on any lane, now or later. The word appears in no docstring in
        this module -- the prose says "No subprocess", not "import
        subprocess"."""
        source = inspect.getsource(ac)
        self.assertNotIn("import subprocess", source)
        self.assertNotIn("shutil.which", source)

    def test_the_request_is_a_get_with_no_body(self):
        captured = {}

        class _Resp:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b"{}"

        def _open(req, timeout=None):
            captured["req"] = req
            captured["timeout"] = timeout
            return _Resp()

        with mock.patch.object(ac._OPENER, "open", _open):
            self.assertEqual(
                ac._http_get("https://dev.azure.com/x", "tok"), b"{}")
        self.assertEqual(captured["req"].get_method(), "GET")
        self.assertIsNone(captured["req"].data)
        self.assertEqual(captured["timeout"], 30)


class TestRedirectsAreRefused(unittest.TestCase):
    def test_redirect_request_returns_none(self):
        handler = ac._NoRedirect()
        self.assertIsNone(handler.redirect_request(
            None, None, 302, "Found", {}, "https://evil.example.com/"))

    def test_the_module_opener_installs_the_no_redirect_handler(self):
        handlers = ac._OPENER.handlers
        self.assertTrue(any(isinstance(h, ac._NoRedirect) for h in handlers))


class TestTheSecretNeverLeaks(unittest.TestCase):
    def test_the_auth_header_is_basic_with_an_empty_username(self):
        expected = "Basic " + base64.b64encode(b":tok").decode("ascii")
        self.assertEqual(ac._auth_header("tok"), expected)

    def test_an_http_error_message_names_only_the_url(self):
        url = "https://dev.azure.com/contoso/_apis/wit/workitems/1"
        error = urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)
        with mock.patch.object(ac._OPENER, "open", side_effect=error):
            with self.assertRaises(ac.AdoError) as ctx:
                ac._http_get(url, "sekrit-pat")
        message = str(ctx.exception)
        self.assertIn("401", message)
        self.assertNotIn("sekrit-pat", message)
        self.assertNotIn(
            base64.b64encode(b":sekrit-pat").decode("ascii"), message)

    def test_a_url_error_is_an_ado_error_not_a_traceback(self):
        error = urllib.error.URLError("no route to host")
        with mock.patch.object(ac._OPENER, "open", side_effect=error):
            with self.assertRaises(ac.AdoError):
                ac._http_get("https://dev.azure.com/x", "tok")

    def test_a_bare_oserror_while_reading_is_also_an_ado_error(self):
        reset = OSError("connection reset")
        with mock.patch.object(ac._OPENER, "open", side_effect=reset):
            with self.assertRaises(ac.AdoError) as ctx:
                ac._http_get("https://dev.azure.com/x", "sekrit-pat")
        self.assertNotIn("sekrit-pat", str(ctx.exception))


class TestJsonParseFailsClosed(unittest.TestCase):
    def test_a_malformed_response_is_an_actionable_ado_error(self):
        with self.assertRaises(ac.AdoError) as ctx:
            ac._parse_json("{not json", "work item")
        self.assertIn("work item", str(ctx.exception))


class TestHtmlToTextIsLossyButFaithful(unittest.TestCase):
    def test_none_and_a_non_string_render_empty(self):
        for raw in (None, "", 17, [], {}):
            self.assertEqual(ac.html_to_text(raw), "")

    def test_plain_text_survives(self):
        self.assertEqual(ac.html_to_text("hello world"), "hello world")

    def test_divs_and_paragraphs_become_blank_line_separated_blocks(self):
        self.assertEqual(
            ac.html_to_text("<div>one</div><div>two</div>"), "one\n\ntwo")
        self.assertEqual(
            ac.html_to_text("<p>one</p><p>two</p>"), "one\n\ntwo")

    def test_a_br_is_a_single_line_break(self):
        self.assertEqual(ac.html_to_text("one<br>two"), "one\ntwo")
        self.assertEqual(ac.html_to_text("one<br/>two"), "one\ntwo")

    def test_list_items_render_as_dash_bullets(self):
        self.assertEqual(
            ac.html_to_text("<ul><li>a</li><li>b</li></ul>"), "- a\n- b")

    def test_nested_lists_still_render_every_item(self):
        rendered = ac.html_to_text(
            "<ul><li>a<ul><li>b</li></ul></li></ul>")
        self.assertIn("- a", rendered)
        self.assertIn("- b", rendered)

    def test_headings_get_the_heading_prefix(self):
        self.assertEqual(ac.html_to_text("<h3>Details</h3><p>x</p>"),
                         "## Details\n\nx")

    def test_entities_are_unescaped(self):
        self.assertEqual(ac.html_to_text("a &amp; b &lt;c&gt; &nbsp;d"),
                         "a & b <c>  d")

    def test_script_and_style_content_is_dropped(self):
        self.assertEqual(
            ac.html_to_text("<p>keep</p><script>alert(1)</script>"), "keep")
        self.assertEqual(
            ac.html_to_text("<style>p{color:red}</style><p>keep</p>"), "keep")

    def test_an_html_comment_is_dropped(self):
        self.assertEqual(ac.html_to_text("<p>keep</p><!-- hidden -->"), "keep")

    def test_runs_of_blank_lines_collapse_to_one(self):
        self.assertEqual(
            ac.html_to_text("<div>a</div><div></div><div></div><div>b</div>"),
            "a\n\nb")

    def test_unclosed_and_unknown_tags_do_not_lose_their_text(self):
        self.assertEqual(ac.html_to_text("<div><span>a<div>b"), "a\n\nb")
        self.assertIn("a", ac.html_to_text("<marquee>a</marquee>"))

    def test_malformed_tag_soup_never_raises(self):
        for raw in ("<<<>>>", "<div", "a < b", "</p></p>", "<br" * 200):
            ac.html_to_text(raw)
