"""Shared node driver for the refactor-radius contract checks.

Split out of test_slice_wave_contract_radius.py so that
test_slice_wave_contract_radius_basis.py can execute
`refactorRadiusStatus()` too, without importing a TestCase class from one
test module into another - unittest discovery would then collect and run
that class's tests twice. This module carries no `test_*` method itself, so
`unittest discover -p 'test_*.py'` never collects it directly.

Usage: imported by test_slice_wave_contract_radius.py and
test_slice_wave_contract_radius_basis.py; not runnable on its own.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from slice_wave_contract_base import SOURCE

RADIUS_START = "const RADIUS_NULL ="
RADIUS_END = "function scopeRecord("

# The extracted radius block plus a driver that judges each [plan, ctx] pair.
# %s is the function source, then the JSON case list - the same two-slot shape
# SCOPE_DRIVER uses in slice_wave_contract_base.py.
RADIUS_DRIVER = """%s
const cases = %s
const run = (c) => refactorRadiusStatus(c[0], refactorLimits({ refactor_radius: c[1] }))
console.log(JSON.stringify(cases.map(run)))
"""


def radius_region():
    """The refactorRadiusStatus()/refactorLimits() source, straight from
    the workflow file (not from a TestCase's cached `self.src`)."""
    start = SOURCE.find(RADIUS_START)
    end = SOURCE.find(RADIUS_END, start + 1)
    assert start != -1 and end != -1, "missing radius anchor"
    return SOURCE[start:end]


def radius_status(cases):
    """refactorRadiusStatus() applied to each [plan, ctx] pair by real node."""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node is not available on this machine")
    fd, path = tempfile.mkstemp(suffix=".mjs")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(RADIUS_DRIVER % (radius_region(), json.dumps(cases)))
        proc = subprocess.run(
            [node, path], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = proc.stdout.decode()
        if proc.returncode != 0:
            raise AssertionError("node failed:\n%s" % (out,))
        return json.loads(out)
    finally:
        os.unlink(path)
