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
        self.assertEqual(ac.validate_org_url("https://dev.azure.com/contoso"),
                         ("https://dev.azure.com/contoso", "contoso"))

    def test_a_trailing_slash_is_tolerated(self):
        self.assertEqual(ac.validate_org_url("https://dev.azure.com/contoso/"),
                         ("https://dev.azure.com/contoso", "contoso"))

    def test_the_legacy_visualstudio_form_yields_the_bare_origin(self):
        self.assertEqual(ac.validate_org_url("https://contoso.visualstudio.com"),
                         ("https://contoso.visualstudio.com", "contoso"))

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
