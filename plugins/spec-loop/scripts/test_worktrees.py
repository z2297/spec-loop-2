#!/usr/bin/env python3
"""Tests for worktrees.py — slice worktree/branch lifecycle (stdlib unittest).

The porcelain parser and the path/branch naming are pure and tested on embedded
fixture text. Everything else talks to real git: each test builds a throwaway
repository (one file, one commit) in a tempfile directory and drives prepare /
cleanup against it, because the behaviour worth pinning here is exactly what
git does with worktrees (reuse, stale registrations, detached HEADs, missing
branches, forced removal) — mocking subprocess would only test our guesses
about git. Every fixture repo is tiny and deleted in tearDown.

Usage:
    python3 -m unittest test_worktrees
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import worktrees as wt  # noqa: E402

RUN_ID = "20260730-demo"


# --------------------------------------------------------------------------
# pure helpers
# --------------------------------------------------------------------------

class TestNaming(unittest.TestCase):
    def test_worktree_path(self):
        self.assertEqual(
            wt.worktree_path("/repo", RUN_ID, "s1"),
            os.path.join("/repo", ".worktrees", "spec-loop", RUN_ID, "s1"))

    def test_worktree_path_is_absolute(self):
        self.assertTrue(os.path.isabs(wt.worktree_path(".", RUN_ID, "s1")))

    def test_branch_name(self):
        self.assertEqual(wt.branch_name(RUN_ID, "s1.2"),
                         "spec-loop/%s/s1.2" % RUN_ID)


class TestParseWorktreeList(unittest.TestCase):
    PORCELAIN = (
        "worktree /repo\n"
        "HEAD 1111111111111111111111111111111111111111\n"
        "branch refs/heads/main\n"
        "\n"
        "worktree /repo/.worktrees/spec-loop/run/s1\n"
        "HEAD 2222222222222222222222222222222222222222\n"
        "branch refs/heads/spec-loop/run/s1\n"
        "\n"
        "worktree /repo/.worktrees/spec-loop/run/s2\n"
        "HEAD 3333333333333333333333333333333333333333\n"
        "detached\n"
        "\n"
        "worktree /repo/.worktrees/spec-loop/run/s3\n"
        "HEAD 4444444444444444444444444444444444444444\n"
        "branch refs/heads/spec-loop/run/s3\n"
        "prunable gitdir file points to non-existent location\n"
    )

    def test_parses_every_record(self):
        records = wt.parse_worktree_list(self.PORCELAIN)
        self.assertEqual([r["path"] for r in records], [
            "/repo",
            "/repo/.worktrees/spec-loop/run/s1",
            "/repo/.worktrees/spec-loop/run/s2",
            "/repo/.worktrees/spec-loop/run/s3",
        ])

    def test_branch_is_shortened(self):
        records = wt.parse_worktree_list(self.PORCELAIN)
        self.assertEqual(records[1]["branch"], "spec-loop/run/s1")

    def test_detached_worktree_has_no_branch(self):
        records = wt.parse_worktree_list(self.PORCELAIN)
        self.assertIsNone(records[2]["branch"])
        self.assertTrue(records[2]["detached"])

    def test_prunable_is_recorded(self):
        records = wt.parse_worktree_list(self.PORCELAIN)
        self.assertTrue(records[3]["prunable"])
        self.assertFalse(records[1]["prunable"])

    def test_empty_output(self):
        self.assertEqual(wt.parse_worktree_list(""), [])

    def test_attributes_before_any_worktree_line_are_ignored(self):
        self.assertEqual(wt.parse_worktree_list("HEAD abc\nbranch refs/heads/main\n"), [])

    def test_bare_repository_record(self):
        records = wt.parse_worktree_list("worktree /repo.git\nbare\n")
        self.assertTrue(records[0]["bare"])


# --------------------------------------------------------------------------
# git fixture
# --------------------------------------------------------------------------

class GitRepoTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "loop@example.com")
        self.git("config", "user.name", "Spec Loop")
        self.git("config", "commit.gpgsign", "false")
        self.write("README.md", "hello\n")
        self.git("add", "README.md")
        self.git("commit", "-m", "init")
        self.git("branch", "csv-export")

    def git(self, *args, cwd=None):
        proc = subprocess.run(["git", "-C", cwd or self.repo] + list(args),
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0,
                         "git %s failed: %s" % (" ".join(args), proc.stderr))
        return proc.stdout.strip()

    def write(self, relpath, text, root=None):
        path = os.path.join(root or self.repo, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def read(self, relpath, root=None):
        with open(os.path.join(root or self.repo, relpath), "r", encoding="utf-8") as fh:
            return fh.read()

    def path_for(self, slice_id):
        return wt.worktree_path(self.repo, RUN_ID, slice_id)

    def branch_for(self, slice_id):
        return wt.branch_name(RUN_ID, slice_id)

    def branch_exists(self, slice_id):
        proc = subprocess.run(
            ["git", "-C", self.repo, "show-ref", "--verify", "--quiet",
             "refs/heads/%s" % self.branch_for(slice_id)],
            capture_output=True, text=True)
        return proc.returncode == 0

    def prepare(self, slices, base_ref="csv-export", resume=False):
        return wt.prepare(self.repo, RUN_ID, slices, base_ref=base_ref, resume=resume)

    def by_slice(self, results):
        return {r["slice"]: r for r in results}

    @contextlib.contextmanager
    def failing_git(self, prefix):
        """Make git calls whose args start with `prefix` fail (rc 1, "boom")."""
        real = wt.run_git

        def fake(repo_dir, *args):
            if tuple(args[:len(prefix)]) == tuple(prefix):
                return 1, "", "boom"
            return real(repo_dir, *args)

        with mock.patch.object(wt, "run_git", fake):
            yield

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdout", out), mock.patch("sys.stderr", err):
            code = wt.main(list(argv))
        payload = json.loads(out.getvalue()) if out.getvalue().strip() else None
        return code, payload, err.getvalue()


# --------------------------------------------------------------------------
# prepare — fresh
# --------------------------------------------------------------------------

class TestPrepareFresh(GitRepoTestCase):
    def test_creates_worktree_and_branch_per_slice(self):
        results = self.by_slice(self.prepare(["s1", "s2"]))
        self.assertEqual(results["s1"]["status"], "created")
        self.assertEqual(results["s2"]["status"], "created")
        for slice_id in ("s1", "s2"):
            self.assertEqual(results[slice_id]["path"], self.path_for(slice_id))
            self.assertEqual(results[slice_id]["branch"], self.branch_for(slice_id))
            self.assertTrue(os.path.isdir(self.path_for(slice_id)))
            self.assertTrue(self.branch_exists(slice_id))

    def test_branch_is_cut_from_the_base_ref_tip(self):
        base_sha = self.git("rev-parse", "csv-export")
        self.prepare(["s1"])
        self.assertEqual(
            self.git("rev-parse", "HEAD", cwd=self.path_for("s1")), base_sha)

    def test_worktree_has_the_expected_branch_checked_out(self):
        self.prepare(["s1"])
        self.assertEqual(
            self.git("branch", "--show-current", cwd=self.path_for("s1")),
            self.branch_for("s1"))

    def test_nested_slice_ids_are_supported(self):
        results = self.by_slice(self.prepare(["s1.2"]))
        self.assertEqual(results["s1.2"]["status"], "created")
        self.assertTrue(self.branch_exists("s1.2"))

    def test_second_prepare_reuses(self):
        self.prepare(["s1"])
        head = self.git("rev-parse", "HEAD", cwd=self.path_for("s1"))
        results = self.by_slice(self.prepare(["s1"]))
        self.assertEqual(results["s1"]["status"], "reused")
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.path_for("s1")), head)

    def test_reuse_keeps_slice_commits(self):
        self.prepare(["s1"])
        worktree = self.path_for("s1")
        self.write("feature.py", "x = 1\n", root=worktree)
        self.git("add", "feature.py", cwd=worktree)
        self.git("commit", "-m", "slice work", cwd=worktree)
        head = self.git("rev-parse", "HEAD", cwd=worktree)
        self.assertEqual(self.by_slice(self.prepare(["s1"]))["s1"]["status"], "reused")
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=worktree), head)
        self.assertTrue(os.path.exists(os.path.join(worktree, "feature.py")))

    def test_detached_worktree_is_recreated(self):
        self.prepare(["s1"])
        worktree = self.path_for("s1")
        self.git("checkout", "--detach", cwd=worktree)
        results = self.by_slice(self.prepare(["s1"]))
        self.assertEqual(results["s1"]["status"], "recreated")
        self.assertEqual(self.git("branch", "--show-current", cwd=worktree),
                         self.branch_for("s1"))

    def test_worktree_on_the_wrong_branch_is_recreated(self):
        self.prepare(["s1"])
        worktree = self.path_for("s1")
        self.git("checkout", "-b", "somebody-elses-branch", cwd=worktree)
        self.assertEqual(self.by_slice(self.prepare(["s1"]))["s1"]["status"],
                         "recreated")

    def test_registration_whose_directory_vanished_is_recreated(self):
        self.prepare(["s1"])
        shutil.rmtree(self.path_for("s1"))
        results = self.by_slice(self.prepare(["s1"]))
        self.assertEqual(results["s1"]["status"], "recreated")
        self.assertTrue(os.path.isdir(self.path_for("s1")))

    def test_existing_branch_without_worktree_is_a_slice_error(self):
        # The integration-failure path keeps the branch; re-preparing it fresh
        # must not silently start over — that is what --resume is for.
        self.git("branch", self.branch_for("s1"), "csv-export")
        results = self.prepare(["s1"])
        self.assertEqual(results[0]["status"], "error")
        self.assertIn("--resume", results[0]["error"])

    def test_unrelated_directory_in_the_way_is_a_slice_error(self):
        self.write(os.path.join(".worktrees", "spec-loop", RUN_ID, "s1", "keep.txt"),
                   "not a worktree\n")
        results = self.prepare(["s1"])
        self.assertEqual(results[0]["status"], "error")
        self.assertTrue(results[0]["error"])

    def test_missing_base_ref_is_a_global_failure(self):
        with self.assertRaises(wt.PrepareError) as ctx:
            self.prepare(["s1"], base_ref="no-such-branch")
        self.assertIn("no-such-branch", str(ctx.exception))
        self.assertFalse(os.path.exists(self.path_for("s1")))

    def test_base_ref_is_required_when_not_resuming(self):
        with self.assertRaises(wt.PrepareError):
            wt.prepare(self.repo, RUN_ID, ["s1"], base_ref=None)

    def test_no_slices_is_a_global_failure(self):
        with self.assertRaises(wt.PrepareError):
            self.prepare([])

    def test_one_bad_slice_does_not_stop_the_others(self):
        self.git("branch", self.branch_for("s1"), "csv-export")
        results = self.by_slice(self.prepare(["s1", "s2"]))
        self.assertEqual(results["s1"]["status"], "error")
        self.assertEqual(results["s2"]["status"], "created")

    def test_not_a_git_repository(self):
        with self.assertRaises(wt.WorktreeError):
            wt.prepare(self.tmp, RUN_ID, ["s1"], base_ref="main")

    def test_missing_repo_directory(self):
        with self.assertRaises(wt.WorktreeError) as ctx:
            wt.prepare(os.path.join(self.tmp, "gone"), RUN_ID, ["s1"], base_ref="main")
        self.assertIn("not a directory", str(ctx.exception))

    def test_git_add_failure_is_reported_per_slice(self):
        with self.failing_git(("worktree", "add")):
            results = self.prepare(["s1"])
        self.assertEqual(results[0]["status"], "error")
        self.assertIn("boom", results[0]["error"])

    def test_git_timeout_is_a_worktree_error(self):
        with mock.patch.object(
                wt.subprocess, "run",
                side_effect=subprocess.TimeoutExpired(cmd="git", timeout=1)):
            with self.assertRaises(wt.WorktreeError):
                wt.run_git(self.repo, "status")

    def test_worktree_list_failure_is_a_worktree_error(self):
        with self.failing_git(("worktree", "list")):
            with self.assertRaises(wt.WorktreeError):
                wt.list_worktrees(self.repo)

    def test_unwritable_gitignore_is_a_global_failure(self):
        os.mkdir(os.path.join(self.repo, ".gitignore"))
        with self.assertRaises(wt.PrepareError):
            self.prepare(["s1"])


# --------------------------------------------------------------------------
# prepare --resume
# --------------------------------------------------------------------------

class TestPrepareResume(GitRepoTestCase):
    def test_reattaches_an_existing_branch_at_its_head(self):
        self.prepare(["s1"])
        worktree = self.path_for("s1")
        self.write("feature.py", "x = 1\n", root=worktree)
        self.git("add", "feature.py", cwd=worktree)
        self.git("commit", "-m", "slice work", cwd=worktree)
        head = self.git("rev-parse", "HEAD", cwd=worktree)
        wt.cleanup(self.repo, RUN_ID, ["s1"])
        self.assertFalse(os.path.exists(worktree))

        results = self.by_slice(self.prepare(["s1"], base_ref=None, resume=True))
        self.assertEqual(results["s1"]["status"], "created")
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=worktree), head)
        self.assertTrue(os.path.exists(os.path.join(worktree, "feature.py")))

    def test_live_worktree_is_reused_on_resume(self):
        self.prepare(["s1"])
        results = self.by_slice(self.prepare(["s1"], base_ref=None, resume=True))
        self.assertEqual(results["s1"]["status"], "reused")

    def test_detached_worktree_is_reattached_on_resume(self):
        self.prepare(["s1"])
        self.git("checkout", "--detach", cwd=self.path_for("s1"))
        results = self.by_slice(self.prepare(["s1"], base_ref=None, resume=True))
        self.assertEqual(results["s1"]["status"], "recreated")
        self.assertEqual(
            self.git("branch", "--show-current", cwd=self.path_for("s1")),
            self.branch_for("s1"))

    def test_missing_branch_is_a_per_slice_error(self):
        results = self.prepare(["s1"], base_ref=None, resume=True)
        self.assertEqual(results[0]["status"], "error")
        self.assertIn("branch", results[0]["error"])

    def test_missing_branch_does_not_crash_the_other_slices(self):
        self.prepare(["s2"])
        wt.cleanup(self.repo, RUN_ID, ["s2"])
        results = self.by_slice(self.prepare(["s1", "s2"], base_ref=None, resume=True))
        self.assertEqual(results["s1"]["status"], "error")
        self.assertEqual(results["s2"]["status"], "created")

    def test_resume_ignores_base_ref(self):
        self.prepare(["s1"])
        wt.cleanup(self.repo, RUN_ID, ["s1"])
        results = self.by_slice(
            self.prepare(["s1"], base_ref="no-such-branch", resume=True))
        self.assertEqual(results["s1"]["status"], "created")


# --------------------------------------------------------------------------
# .gitignore management
# --------------------------------------------------------------------------

class TestGitignore(GitRepoTestCase):
    def test_created_when_absent(self):
        self.assertEqual(wt.ensure_gitignore(self.repo), "created")
        self.assertIn(".worktrees/", self.read(".gitignore"))

    def test_appended_when_missing(self):
        self.write(".gitignore", "*.pyc\n")
        self.assertEqual(wt.ensure_gitignore(self.repo), "added")
        body = self.read(".gitignore")
        self.assertIn("*.pyc", body)
        self.assertIn(".worktrees/", body)

    def test_appends_a_newline_when_the_file_lacks_one(self):
        self.write(".gitignore", "*.pyc")
        wt.ensure_gitignore(self.repo)
        lines = [line.strip() for line in self.read(".gitignore").splitlines()]
        self.assertIn("*.pyc", lines)
        self.assertIn(".worktrees/", lines)

    def test_already_present_is_left_alone(self):
        self.write(".gitignore", "*.pyc\n.worktrees/\n")
        self.assertEqual(wt.ensure_gitignore(self.repo), "present")
        self.assertEqual(self.read(".gitignore"), "*.pyc\n.worktrees/\n")

    def test_unslashed_entry_counts_as_present(self):
        self.write(".gitignore", ".worktrees\n")
        self.assertEqual(wt.ensure_gitignore(self.repo), "present")

    def test_prepare_ensures_the_ignore_entry(self):
        self.prepare(["s1"])
        self.assertIn(".worktrees/", self.read(".gitignore"))

    def test_worktrees_are_actually_ignored_by_git(self):
        self.prepare(["s1"])
        status = self.git("status", "--porcelain")
        self.assertNotIn(".worktrees", status)


# --------------------------------------------------------------------------
# cleanup
# --------------------------------------------------------------------------

class TestCleanup(GitRepoTestCase):
    def test_removes_the_worktree_and_keeps_the_branch(self):
        self.prepare(["s1"])
        results = self.by_slice(wt.cleanup(self.repo, RUN_ID, ["s1"]))
        self.assertEqual(results["s1"]["status"], "removed")
        self.assertFalse(os.path.exists(self.path_for("s1")))
        self.assertTrue(self.branch_exists("s1"))

    def test_delete_branch_removes_the_branch_too(self):
        self.prepare(["s1"])
        results = self.by_slice(
            wt.cleanup(self.repo, RUN_ID, ["s1"], delete_branch=True))
        self.assertEqual(results["s1"]["status"], "removed")
        self.assertTrue(results["s1"]["branch_deleted"])
        self.assertFalse(self.branch_exists("s1"))

    def test_absent_worktree_is_tolerated(self):
        results = self.by_slice(wt.cleanup(self.repo, RUN_ID, ["s1"]))
        self.assertEqual(results["s1"]["status"], "absent")

    def test_cleanup_is_idempotent(self):
        self.prepare(["s1"])
        wt.cleanup(self.repo, RUN_ID, ["s1"], delete_branch=True)
        results = self.by_slice(
            wt.cleanup(self.repo, RUN_ID, ["s1"], delete_branch=True))
        self.assertEqual(results["s1"]["status"], "absent")
        self.assertFalse(results["s1"]["branch_deleted"])

    def test_uncommitted_changes_are_force_removed(self):
        self.prepare(["s1"])
        self.write("scratch.py", "junk\n", root=self.path_for("s1"))
        results = self.by_slice(wt.cleanup(self.repo, RUN_ID, ["s1"]))
        self.assertEqual(results["s1"]["status"], "removed")
        self.assertFalse(os.path.exists(self.path_for("s1")))

    def test_vanished_directory_is_still_deregistered(self):
        # The directory is gone but git still has the worktree registered, so
        # this is a real removal (not "absent") and the registration must go.
        self.prepare(["s1"])
        shutil.rmtree(self.path_for("s1"))
        results = self.by_slice(wt.cleanup(self.repo, RUN_ID, ["s1"]))
        self.assertEqual(results["s1"]["status"], "removed")
        self.assertIsNone(wt.registered_worktree(self.repo, self.path_for("s1")))

    def test_removal_failure_is_reported_as_an_error(self):
        self.prepare(["s1"])
        with self.failing_git(("worktree", "remove")):
            results = self.by_slice(wt.cleanup(self.repo, RUN_ID, ["s1"]))
        self.assertEqual(results["s1"]["status"], "error")
        self.assertTrue(os.path.isdir(self.path_for("s1")))

    def test_failed_removal_of_a_vanished_worktree_falls_back_to_prune(self):
        self.prepare(["s1"])
        shutil.rmtree(self.path_for("s1"))
        with self.failing_git(("worktree", "remove")):
            results = self.by_slice(wt.cleanup(self.repo, RUN_ID, ["s1"]))
        self.assertEqual(results["s1"]["status"], "removed")
        self.assertIsNone(wt.registered_worktree(self.repo, self.path_for("s1")))

    def test_branch_delete_failure_is_reported_as_an_error(self):
        self.prepare(["s1"])
        with self.failing_git(("branch", "-D")):
            results = self.by_slice(
                wt.cleanup(self.repo, RUN_ID, ["s1"], delete_branch=True))
        self.assertEqual(results["s1"]["status"], "error")
        self.assertFalse(results["s1"]["branch_deleted"])

    def test_stale_registration_that_will_not_go_is_a_prepare_error(self):
        self.prepare(["s1"])
        self.git("checkout", "--detach", cwd=self.path_for("s1"))
        with self.failing_git(("worktree", "remove")):
            results = self.prepare(["s1"])
        self.assertEqual(results[0]["status"], "error")

    def test_several_slices_at_once(self):
        self.prepare(["s1", "s2"])
        results = self.by_slice(wt.cleanup(self.repo, RUN_ID, ["s1", "s2"]))
        self.assertEqual(results["s1"]["status"], "removed")
        self.assertEqual(results["s2"]["status"], "removed")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

class TestCli(GitRepoTestCase):
    def test_prepare_prints_an_array(self):
        code, payload, _ = self.cli("prepare", "--repo-dir", self.repo,
                                    "--run-id", RUN_ID, "--slices", "s1,s2",
                                    "--base-ref", "csv-export")
        self.assertEqual(code, 0)
        self.assertEqual([r["slice"] for r in payload], ["s1", "s2"])
        self.assertEqual({r["status"] for r in payload}, {"created"})

    def test_prepare_tolerates_spaces_in_slices(self):
        code, payload, _ = self.cli("prepare", "--repo-dir", self.repo,
                                    "--run-id", RUN_ID, "--slices", "s1, s2",
                                    "--base-ref", "csv-export")
        self.assertEqual(code, 0)
        self.assertEqual(len(payload), 2)

    def test_prepare_slice_error_is_exit_one(self):
        self.git("branch", self.branch_for("s1"), "csv-export")
        code, payload, _ = self.cli("prepare", "--repo-dir", self.repo,
                                    "--run-id", RUN_ID, "--slices", "s1",
                                    "--base-ref", "csv-export")
        self.assertEqual(code, 1)
        self.assertEqual(payload[0]["status"], "error")

    def test_prepare_global_failure_is_exit_one_with_an_object(self):
        code, payload, _ = self.cli("prepare", "--repo-dir", self.repo,
                                    "--run-id", RUN_ID, "--slices", "s1",
                                    "--base-ref", "ghost")
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertIn("ghost", payload["error"])

    def test_prepare_resume_flag(self):
        self.cli("prepare", "--repo-dir", self.repo, "--run-id", RUN_ID,
                 "--slices", "s1", "--base-ref", "csv-export")
        wt.cleanup(self.repo, RUN_ID, ["s1"])
        code, payload, _ = self.cli("prepare", "--repo-dir", self.repo,
                                    "--run-id", RUN_ID, "--slices", "s1", "--resume")
        self.assertEqual(code, 0)
        self.assertEqual(payload[0]["status"], "created")

    def test_cleanup_cli(self):
        self.prepare(["s1"])
        code, payload, _ = self.cli("cleanup", "--repo-dir", self.repo,
                                    "--run-id", RUN_ID, "--slices", "s1",
                                    "--delete-branch")
        self.assertEqual(code, 0)
        self.assertEqual(payload[0]["status"], "removed")
        self.assertFalse(self.branch_exists("s1"))

    def test_cleanup_absent_is_exit_zero(self):
        code, payload, _ = self.cli("cleanup", "--repo-dir", self.repo,
                                    "--run-id", RUN_ID, "--slices", "s1")
        self.assertEqual(code, 0)
        self.assertEqual(payload[0]["status"], "absent")

    def test_non_repo_is_exit_two(self):
        code, payload, err = self.cli("cleanup", "--repo-dir", self.tmp,
                                      "--run-id", RUN_ID, "--slices", "s1")
        self.assertEqual(code, 2)
        self.assertIsNone(payload)
        self.assertIn("error:", err)

    def test_missing_git_binary_is_exit_two(self):
        with mock.patch.object(wt.subprocess, "run", side_effect=OSError("no git")):
            code, _, err = self.cli("cleanup", "--repo-dir", self.repo,
                                    "--run-id", RUN_ID, "--slices", "s1")
        self.assertEqual(code, 2)
        self.assertIn("git", err)

    def test_slices_are_required(self):
        with self.assertRaises(SystemExit):
            self.cli("prepare", "--repo-dir", self.repo, "--run-id", RUN_ID)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
