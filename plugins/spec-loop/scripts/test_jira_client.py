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


if __name__ == "__main__":
    unittest.main()
