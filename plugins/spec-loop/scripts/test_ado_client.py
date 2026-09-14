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
import contextlib
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
        # An HTTPError IS a response object (addinfourl extends
        # tempfile._TemporaryFileWrapper), so an unclosed one emits a
        # ResourceWarning to stderr whenever the collector gets to it --
        # landing in whichever test happens to be capturing stderr then.
        # Closed deterministically here so this file leaks no warning into
        # another test module.
        self.addCleanup(error.close)
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


def work_item(**overrides):
    """One raw work-item response object, shaped like the documented payload.
    Field overrides are merged into `fields`; a top-level override (e.g.
    _links) replaces that key."""
    fields = {
        ac.FIELD_TITLE: "Make the widget spin",
        ac.FIELD_DESCRIPTION: "<div>spin it</div>",
        ac.FIELD_TYPE: "User Story",
        ac.FIELD_PROJECT: "Contoso Platform",
        ac.FIELD_STATE: "Active",
    }
    fields.update({k: v for k, v in overrides.items() if k.count(".")})
    href = ("https://dev.azure.com/contoso/Contoso%20Platform"
            "/_workitems/edit/1234")
    payload = {
        "id": 1234,
        "fields": fields,
        "_links": {"html": {"href": href}},
    }
    payload.update({k: v for k, v in overrides.items() if not k.count(".")})
    return payload


class TestUrlsAreComposedLocally(unittest.TestCase):
    def test_the_work_item_url_omits_the_project_and_pins_its_api_version(self):
        url = ac.work_item_url("https://dev.azure.com/contoso", "1234")
        self.assertEqual(
            url,
            "https://dev.azure.com/contoso/_apis/wit/workitems/1234"
            "?api-version=7.1")

    def test_the_work_item_url_percent_encodes_the_id_it_was_given(self):
        with self.assertRaises(ac.AdoUsageError):
            ac.work_item_url("https://dev.azure.com/contoso", "1/../2")

    def test_the_comments_url_carries_the_encoded_project_and_its_api_version(self):
        url = ac.comments_url(
            "https://dev.azure.com/contoso", "Contoso Platform", "1234")
        self.assertEqual(
            url,
            "https://dev.azure.com/contoso/Contoso%20Platform/_apis/wit/"
            "workItems/1234/comments?api-version=7.1-preview.4"
            "&$top=100")

    def test_the_comments_url_encodes_a_slash_in_a_project_name(self):
        url = ac.comments_url("https://dev.azure.com/contoso", "a/b", "1")
        self.assertIn("a%2Fb", url)
        self.assertNotIn("/a/b/", url)

    def test_no_url_composer_reads_anything_from_a_response_body(self):
        """Function-scoped, and docstring-stripped, ON PURPOSE. The module's
        docstrings are load-bearing doctrine whose JOB is to discuss
        `nextPage`, so a whole-module token scan would fail against the
        repo's own required prose (and would tempt an executor to weaken the
        assertion instead of the code). What must hold is that the URL
        composers read nothing from a response body. The behavioural proof
        that the hostile `nextPage` in the fixture is never fetched lives in
        Task 5's test_the_server_supplied_next_page_url_is_never_fetched;
        this is the structural companion. Never weaken either -- conventions
        §23 is a blocking rule."""
        for fn in (ac.work_item_url, ac.comments_url):
            with self.subTest(fn=fn.__name__):
                source = inspect.getsource(fn)
                parts = source.split('"""')
                code = parts[2] if len(parts) >= 3 else source
                self.assertNotIn("nextPage", code)
                self.assertNotIn("_links", code)


class TestTheProjectComesFromTheRead(unittest.TestCase):
    def test_the_project_is_taken_from_system_teamproject(self):
        fields = {ac.FIELD_PROJECT: "Contoso Platform"}
        self.assertEqual(ac.resolve_project(fields), "Contoso Platform")

    def test_a_missing_project_is_a_half_resolve_and_raises(self):
        shapes = (
            {},
            {ac.FIELD_PROJECT: ""},
            {ac.FIELD_PROJECT: "   "},
            {ac.FIELD_PROJECT: 7},
        )
        for fields in shapes:
            with self.assertRaises(ac.AdoError):
                ac.resolve_project(fields)

    def test_a_project_name_with_a_control_character_is_refused_not_rewritten(self):
        for bad in ("a\nb", "a\rb", "a\x00b", "a\tb"):
            with self.assertRaises(ac.AdoError):
                ac.resolve_project({ac.FIELD_PROJECT: bad})

    def test_an_unset_ado_project_asserts_nothing(self):
        with mock.patch.dict(ac.os.environ, {}, clear=True):
            self.assertIsNone(ac.assert_project_matches_env("Contoso Platform"))

    def test_a_matching_ado_project_passes(self):
        env = {"ADO_PROJECT": " Contoso Platform "}
        with mock.patch.dict(ac.os.environ, env, clear=True):
            self.assertIsNone(ac.assert_project_matches_env("Contoso Platform"))

    def test_a_mismatched_ado_project_refuses_and_names_both_values(self):
        env = {"ADO_PROJECT": "Other"}
        with mock.patch.dict(ac.os.environ, env, clear=True):
            with self.assertRaises(ac.AdoUsageError) as ctx:
                ac.assert_project_matches_env("Contoso Platform")
        message = str(ctx.exception)
        self.assertIn("Other", message)
        self.assertIn("Contoso Platform", message)


class TestTheWebUrlIsValidatedBeforeItIsEverDisplayed(unittest.TestCase):
    def test_an_href_under_the_validated_api_root_is_returned(self):
        href = ("https://dev.azure.com/contoso/Contoso%20Platform"
                "/_workitems/edit/1234")
        root = "https://dev.azure.com/contoso"
        self.assertEqual(ac.validate_web_url(href, root), href)

    def test_the_host_comparison_is_case_insensitive(self):
        href = "https://DEV.AZURE.COM/contoso/_workitems/edit/1"
        root = "https://dev.azure.com/contoso"
        self.assertEqual(ac.validate_web_url(href, root), href)

    def test_an_href_on_another_origin_is_refused(self):
        hrefs = (
            "https://evil.example.com/contoso/_workitems/edit/1",
            "http://dev.azure.com/contoso/_workitems/edit/1",
            "https://dev.azure.com/otherorg/_workitems/edit/1",
            "https://dev.azure.com.evil.example/contoso/x",
            "javascript:alert(1)", "", None, 42,
        )
        for bad in hrefs:
            with self.assertRaises(ac.AdoError):
                ac.validate_web_url(bad, "https://dev.azure.com/contoso")

    def test_a_prefix_lookalike_org_is_refused(self):
        bad = "https://dev.azure.com/contoso-evil/_workitems/edit/1"
        with self.assertRaises(ac.AdoError):
            ac.validate_web_url(bad, "https://dev.azure.com/contoso")

    def test_a_mismatched_href_names_the_other_host_but_not_its_path(self):
        bad = ("https://contoso.visualstudio.com/Contoso%20Platform"
               "/_workitems/edit/1234?secret=leak")
        with self.assertRaises(ac.AdoError) as ctx:
            ac.validate_web_url(bad, "https://dev.azure.com/contoso")
        message = str(ctx.exception)
        self.assertIn("https://dev.azure.com/contoso", message)
        self.assertIn("https://contoso.visualstudio.com", message)
        self.assertNotIn("_workitems", message)
        self.assertNotIn("secret", message)


class TestFetchWorkItem(unittest.TestCase):
    def test_the_read_issues_one_get_to_the_locally_composed_url(self):
        payload = json.dumps(work_item()).encode("utf-8")
        with mock.patch.object(ac, "_http_get", return_value=payload) as get:
            item = ac.fetch_work_item(
                "https://dev.azure.com/contoso", "tok", "1234")
        self.assertEqual(item["id"], 1234)
        get.assert_called_once_with(
            "https://dev.azure.com/contoso/_apis/wit/workitems/1234"
            "?api-version=7.1", "tok")

    def test_a_non_object_response_is_a_contract_failure(self):
        with mock.patch.object(ac, "_http_get", return_value=b"[]"):
            with self.assertRaises(ac.AdoError):
                ac.fetch_work_item("https://dev.azure.com/contoso", "tok", "1")


def raw_comment(cid, text, author="Ada", id_key="id"):
    """One raw comment object. `id_key` selects which of the two documented
    spellings carries the id: the definition table names it `id`, while
    Microsoft's own sample payloads show `commentId`."""
    return {
        id_key: cid,
        "text": text,
        "createdBy": {"displayName": author},
        "createdDate": "2026-09-14T10:00:00Z",
        "modifiedDate": "2026-09-14T10:00:00Z",
    }


def comment_page(comments, total, token=None):
    """One raw comment-list page. Every page also carries a server-chosen
    `nextPage` URL, which this client must never fetch -- it is included in
    the fixture pointing at a hostile origin precisely so a test can prove the
    client ignores it."""
    page = {
        "comments": comments,
        "totalCount": total,
        "nextPage": "https://evil.example.com/steal-the-pat",
    }
    if token is not None:
        page["continuationToken"] = token
    return page


class TestTheCommentSweepIsFailClosed(unittest.TestCase):
    API_ROOT = "https://dev.azure.com/contoso"
    SWEEP_ARGS = (API_ROOT, "tok", "Contoso Platform", "1234")

    def _sweep(self, pages):
        bodies = [json.dumps(p).encode("utf-8") for p in pages]
        with mock.patch.object(ac, "_http_get", side_effect=bodies) as get:
            result = ac.fetch_comments(*self.SWEEP_ARGS)
        return result, get

    def _assert_sweep_refuses(self, page):
        """Sweep one fail-closed page and require the refusal. Extracted so
        each integrity rule below reads `for case -> subTest -> assert` at
        three levels of nesting instead of four."""
        with self.assertRaises(ac.AdoError):
            self._sweep([page])

    def test_a_single_page_sweep_normalizes_every_comment(self):
        raws = [raw_comment(1, "hello"), raw_comment(2, "world")]
        comments, _ = self._sweep([comment_page(raws, 2)])
        self.assertEqual([c["text"] for c in comments], ["hello", "world"])
        self.assertEqual([c["id"] for c in comments], ["1", "2"])
        self.assertEqual(comments[0]["author"], "Ada")
        self.assertEqual(comments[0]["created"], "2026-09-14T10:00:00Z")

    def test_an_empty_history_is_a_legitimate_empty_list(self):
        comments, _ = self._sweep([comment_page([], 0)])
        self.assertEqual(comments, [])

    def test_the_sweep_follows_the_continuation_token_it_composes_itself(self):
        pages = [
            comment_page([raw_comment(1, "a")], 2, token="TOKEN-2"),
            comment_page([raw_comment(2, "b")], 2),
        ]
        comments, get = self._sweep(pages)
        self.assertEqual([c["text"] for c in comments], ["a", "b"])
        second_url = get.call_args_list[1].args[0]
        self.assertIn("continuationToken=TOKEN-2", second_url)
        self.assertTrue(
            second_url.startswith("https://dev.azure.com/contoso/"))

    def test_the_server_supplied_next_page_url_is_never_fetched(self):
        pages = [
            comment_page([raw_comment(1, "a")], 2, token="TOKEN-2"),
            comment_page([raw_comment(2, "b")], 2),
        ]
        _, get = self._sweep(pages)
        for call in get.call_args_list:
            self.assertNotIn("evil.example.com", call.args[0])

    def test_a_comment_id_spelled_commentid_is_accepted(self):
        raws = [raw_comment(9, "a", id_key="commentId")]
        comments, _ = self._sweep([comment_page(raws, 1)])
        self.assertEqual(comments[0]["id"], "9")

    def test_a_comment_with_no_text_raises_rather_than_shrink_the_haystack(self):
        broken_comments = (
            {"id": 1},
            {"id": 1, "text": ""},
            {"id": 1, "text": None},
            {"id": 1, "text": 7},
        )
        for broken in broken_comments:
            with self.subTest(broken=broken):
                self._assert_sweep_refuses(comment_page([broken], 1))

    def test_a_missing_or_non_numeric_total_count_raises(self):
        pages = (
            {"comments": []},
            {"comments": [], "totalCount": None},
            {"comments": [], "totalCount": "lots"},
        )
        for page in pages:
            with self.subTest(page=page):
                self._assert_sweep_refuses(page)

    def test_a_page_missing_the_comments_list_raises(self):
        pages = (
            {"totalCount": 1},
            {"comments": {}, "totalCount": 1},
            {"comments": "a", "totalCount": 1},
        )
        for page in pages:
            with self.subTest(page=page):
                self._assert_sweep_refuses(page)

    def test_terminating_with_fewer_comments_than_total_count_raises(self):
        with self.assertRaises(ac.AdoError) as ctx:
            self._sweep([comment_page([raw_comment(1, "a")], 5)])
        self.assertIn("5", str(ctx.exception))

    def test_a_continuation_token_that_fails_its_allow_list_raises(self):
        for bad in ("tok en", "tok\n", "a" * 513, "tok&x=1", 42, []):
            with self.subTest(bad=bad):
                page = comment_page([raw_comment(1, "a")], 2, token=bad)
                self._assert_sweep_refuses(page)

    def test_a_traversal_shaped_token_is_neutralised_by_percent_encoding(self):
        """CONTINUATION_TOKEN_RE is pinned verbatim by conventions §31 and it
        permits '.', '/' and '-', so '../etc' MATCHES the allow-list. That is
        not a hole, and the regex is NOT what defends here: the token only
        ever lands in a query PARAMETER, quote(safe="")-encoded, so no path
        traversal is expressible. Assert the real defence directly rather
        than asserting a rejection that does not (and need not) happen."""
        url = ac.comments_url(
            "https://dev.azure.com/contoso", "P", "1", "../etc")
        self.assertIn("continuationToken=..%2Fetc", url)
        self.assertNotIn("../etc", url)
        self.assertNotIn("/etc", url)

    def test_an_unterminated_sweep_is_capped_and_raises(self):
        page = comment_page([raw_comment(1, "a")], 10 ** 6, token="TOKEN")
        bodies = [json.dumps(page).encode("utf-8")] * (ac.MAX_COMMENT_PAGES + 1)
        with mock.patch.object(ac, "_http_get", side_effect=bodies):
            with self.assertRaises(ac.AdoError) as ctx:
                ac.fetch_comments(*self.SWEEP_ARGS)
        self.assertIn(str(ac.MAX_COMMENT_PAGES), str(ctx.exception))

    def test_deleted_comments_stay_excluded(self):
        """includeDeleted stays at its default. Setting it would let a comment
        deleted in the web UI permanently suppress a legitimate re-post.

        Scoped to comments_url -- the only function that can send the
        parameter -- and matched as `includeDeleted=`, because conventions
        §24.3 REQUIRES the module and fetch_comments docstrings to document
        this consequence by name. A whole-module scan for the bare word would
        fail against that mandated prose."""
        source = inspect.getsource(ac.comments_url)
        self.assertNotIn("includeDeleted=", source)
        self.assertNotIn(
            "includeDeleted=true", inspect.getsource(ac.fetch_comments))


class TestTheDedupeHaystackComesFromStoredTextOnly(unittest.TestCase):
    """A marker is matched against what was STORED. renderedText is an
    optional HTML RENDERING that a renderer may entity-encode or strip; a
    marker it altered would go unmatched and the comment lane would post
    again on a live work item. This test fails if the gate is ever
    repointed."""

    def test_the_normalized_text_is_the_stored_text_not_the_rendered_text(self):
        raw = raw_comment(1, "[spec-loop-intake:decision:0123456789ab] body")
        raw["renderedText"] = "<p>totally different</p>"
        normalized = ac._normalize_comment(raw)
        self.assertEqual(normalized["text"], raw["text"])
        self.assertNotIn("renderedText", normalized)

    def test_the_module_never_mentions_rendered_text_as_a_data_source(self):
        """Module-wide but QUOTE-SCOPED: it looks for the field being used as
        a dict KEY ('"renderedText"'), not for the bare word. The docstrings
        must stay free to explain why renderedText is not the haystack, and
        they name it with backticks, so this cannot fire on its own required
        prose."""
        source = inspect.getsource(ac)
        self.assertNotIn('"renderedText"', source)
        self.assertNotIn("'renderedText'", source)


class TestAcceptanceCriteriaResolveInAFixedOrder(unittest.TestCase):
    def test_the_field_wins_when_present_and_non_empty(self):
        fields = {ac.FIELD_ACCEPTANCE_CRITERIA: "<ul><li>it spins</li></ul>"}
        resolved = ac.resolve_acceptance_criteria(
            fields, "## Acceptance Criteria\n\nfrom desc")
        self.assertEqual(resolved, ("- it spins", "field"))

    def test_an_absent_field_is_the_common_case_not_a_failure(self):
        """An Agile User Story and a Task have no acceptance-criteria field at
        all, so its absence must fall through to the description."""
        rendered = "intro\n\n## Acceptance Criteria\n\n- it spins\n- it stops"
        self.assertEqual(
            ac.resolve_acceptance_criteria({}, rendered),
            ("- it spins\n- it stops", "description"))

    def test_an_empty_field_falls_through_to_the_description(self):
        fields = {ac.FIELD_ACCEPTANCE_CRITERIA: "<div>   </div>"}
        rendered = "## Acceptance Criteria\n\n- it spins"
        self.assertEqual(
            ac.resolve_acceptance_criteria(fields, rendered),
            ("- it spins", "description"))

    def test_a_field_of_an_unexpected_shape_degrades_rather_than_crashes(self):
        for raw in (7, [], {}, None):
            fields = {ac.FIELD_ACCEPTANCE_CRITERIA: raw}
            self.assertEqual(
                ac.resolve_acceptance_criteria(fields, ""), ("", ""))

    def test_neither_source_yields_an_empty_pair(self):
        self.assertEqual(
            ac.resolve_acceptance_criteria({}, "just prose"), ("", ""))

    def test_the_section_stops_at_the_next_heading(self):
        rendered = ("## Acceptance Criteria\n\n- it spins\n\n"
                    "## Notes\n\nnot criteria")
        criteria, source = ac.resolve_acceptance_criteria({}, rendered)
        self.assertEqual(criteria, "- it spins")
        self.assertEqual(source, "description")
        self.assertNotIn("not criteria", criteria)

    def test_the_heading_match_is_case_and_colon_insensitive(self):
        headings = ("## acceptance criteria", "## ACCEPTANCE CRITERIA:",
                    "Acceptance Criteria:", "acceptance  criteria")
        for heading in headings:
            resolved = ac.resolve_acceptance_criteria(
                {}, f"{heading}\n\n- it spins")
            self.assertEqual(resolved, ("- it spins", "description"))


class TestTheNormalizedRecord(unittest.TestCase):
    def _values(self, **overrides):
        """Every RECORD_FIELDS value for a whole, resolvable work item, with
        the optional ones already at their legitimately-empty value."""
        values = {
            "org": "contoso",
            "project": "Contoso Platform",
            "id": "1234",
            "web_url": "https://dev.azure.com/contoso/_workitems/edit/1234",
            "title": "Make the widget spin",
            "work_item_type": "User Story",
            "state": "Active",
            "description": "",
            "acceptance_criteria": "",
            "acceptance_criteria_source": "",
            "repro_steps": "",
            "comments": [],
        }
        values.update(overrides)
        return values

    def test_the_record_is_built_in_record_fields_order(self):
        record = ac._normalized(self._values())
        self.assertEqual(list(record), list(ac.RECORD_FIELDS))

    def test_org_project_and_id_are_all_required(self):
        for field in ("org", "project", "id"):
            self.assertIn(field, ac.REQUIRED_FIELDS)

    def test_an_empty_required_field_is_a_half_resolve_and_raises(self):
        for field in ac.REQUIRED_FIELDS:
            values = self._values(**{field: ""})
            with self.assertRaises(ac.AdoError) as ctx:
                ac._normalized(values)
            self.assertIn(field, str(ctx.exception))

    def test_the_optional_fields_are_legitimately_empty(self):
        record = ac._normalized(self._values())
        self.assertEqual(record["description"], "")
        self.assertEqual(record["comments"], [])

    def test_rendered_text_and_next_page_are_not_record_fields(self):
        absent = ("rendered_text", "renderedText", "next_page", "nextPage")
        for name in absent:
            self.assertNotIn(name, ac.RECORD_FIELDS)


class TestResolveWorkItem(unittest.TestCase):
    ENV = {"ADO_ORG_URL": "https://dev.azure.com/contoso", "ADO_PAT": "tok"}

    def _patched(self, item, comments=None, env=None):
        """Enter the environment patch and both transport patches on ONE
        contextlib.ExitStack and return it, already entered, alongside the
        fetch_work_item and fetch_comments mocks. One stack rather than three
        nested `with` blocks keeps each test flat, and holding the two mocks is
        what lets a test assert an ORDER property -- that a refusal costs zero
        requests."""
        stack = contextlib.ExitStack()
        stack.enter_context(
            mock.patch.dict(ac.os.environ, env or self.ENV, clear=True))
        read = stack.enter_context(
            mock.patch.object(ac, "fetch_work_item", return_value=item))
        comment_patch = mock.patch.object(
            ac, "fetch_comments", return_value=comments or [])
        sweep = stack.enter_context(comment_patch)
        return stack, read, sweep

    def _resolve(self, item, comments=None, env=None):
        stack, _read, _sweep = self._patched(item, comments, env)
        with stack:
            return ac.resolve_work_item("1234")

    def test_a_user_story_resolves_to_the_whole_record(self):
        record = self._resolve(work_item())
        self.assertEqual(record["org"], "contoso")
        self.assertEqual(record["project"], "Contoso Platform")
        self.assertEqual(record["id"], "1234")
        self.assertEqual(record["title"], "Make the widget spin")
        self.assertEqual(record["work_item_type"], "User Story")
        self.assertEqual(record["state"], "Active")
        self.assertEqual(record["description"], "spin it")
        self.assertEqual(record["acceptance_criteria_source"], "")
        self.assertEqual(record["repro_steps"], "")

    def test_a_bugs_repro_steps_land_in_their_own_field_not_the_description(self):
        item = work_item(**{
            ac.FIELD_TYPE: "Bug",
            ac.FIELD_DESCRIPTION: "",
            ac.FIELD_REPRO_STEPS: "<ol><li>click it</li></ol>",
        })
        record = self._resolve(item)
        self.assertEqual(record["repro_steps"], "- click it")
        self.assertEqual(record["description"], "")

    def test_the_resolved_comments_are_the_swept_comments(self):
        comments = [{"id": "1", "author": "Ada", "created": "", "modified": "",
                     "text": "hello"}]
        record = self._resolve(work_item(), comments=comments)
        self.assertEqual(record["comments"], comments)

    def test_the_comment_sweep_is_called_with_the_project_from_the_read(self):
        stack, _read, sweep = self._patched(work_item())
        with stack:
            ac.resolve_work_item("1234")
        sweep.assert_called_once_with(
            "https://dev.azure.com/contoso", "tok", "Contoso Platform", "1234")

    def test_a_mismatched_ado_project_refuses_the_resolve(self):
        env = dict(self.ENV, ADO_PROJECT="SomethingElse")
        with self.assertRaises(ac.AdoUsageError):
            self._resolve(work_item(), env=env)

    def test_an_href_on_another_origin_refuses_the_resolve(self):
        item = work_item(_links={"html": {"href": "https://evil.example.com/x"}})
        with self.assertRaises(ac.AdoError):
            self._resolve(item)

    def test_a_work_item_with_no_title_is_a_half_resolve(self):
        item = work_item(**{ac.FIELD_TITLE: ""})
        with self.assertRaises(ac.AdoError):
            self._resolve(item)

    def test_the_id_is_validated_before_any_request(self):
        stack, read, _sweep = self._patched(work_item())
        with stack:
            with self.assertRaises(ac.AdoUsageError):
                ac.resolve_work_item("../../etc/passwd")
        read.assert_not_called()

    def test_a_half_resolve_refuses_before_it_sweeps_any_comment(self):
        """An empty required field is a half-resolve. It must cost ZERO
        comment requests, not a full MAX_COMMENT_PAGES sweep."""
        item = work_item(**{ac.FIELD_TITLE: "   "})
        stack, _read, sweep = self._patched(item)
        with stack:
            with self.assertRaises(ac.AdoError):
                ac.resolve_work_item("1234")
        sweep.assert_not_called()


class TestTheReadLaneStaysReadOnly(unittest.TestCase):
    """The read path is CLOSED: no read function so much as names a writer,
    so any bounded writer added to this module later is reachable only from
    its own explicitly-authorized entry point. Scoped per function on
    purpose (the shape of
    plugins/spec-loop/scripts/test_jira_client.py:1554), so a later slice
    ADDS a writer and its own tests rather than deleting these."""

    WRITERS = ("_http_post", "_http_patch", "_http_put", "_http_delete")

    def test_no_read_function_can_reach_a_writer(self):
        reads = (ac.fetch_work_item, ac.fetch_comments, ac.resolve_work_item,
                 ac.work_item_url, ac.comments_url)
        for fn in reads:
            with self.subTest(fn=fn.__name__):
                self._assert_names_no_writer(inspect.getsource(fn))

    def _assert_names_no_writer(self, source):
        for writer in self.WRITERS:
            self.assertNotIn(writer, source, writer)

    def test_the_only_network_entry_point_the_read_lane_uses_is_http_get(self):
        for fn in (ac.fetch_work_item, ac.fetch_comments):
            with self.subTest(fn=fn.__name__):
                self.assertIn("_http_get(", inspect.getsource(fn))
