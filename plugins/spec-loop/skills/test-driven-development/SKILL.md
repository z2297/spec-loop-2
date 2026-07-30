---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code — write the test first, watch it fail, then write minimal code to pass
---

# Test-Driven Development (TDD) — test first, watch it fail, then implement

## Overview

Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

**Inside a `/spec-loop` run this doctrine is the implementer agent's, not yours** — it works
test-first by definition and you never dispatch this skill on a slice's behalf. This skill is for
interactive work: a change you are making yourself, in this session.

## When to Use

**Always:** new features, bug fixes, refactoring, behavior changes.

**Exceptions (ask your human partner):** throwaway prototypes, generated code, configuration
files. The Verify RED / Verify GREEN gates below are never an exception and never a human gate.

## When NOT to use this

- **You have a bug and don't yet know the cause** → start with `spec-loop:systematic-debugging`
  to find root cause, then come back here to write the failing test that reproduces it before
  you fix it.
- **You are about to claim the work is done, fixed, or passing** → that is
  `spec-loop:verification-before-completion` (a hard, no-human evidence gate), not this skill.

This skill governs *how you write code*, not *whether the finished work is trustworthy* — those
are the two siblings above.

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Wrote code before the test? Delete it and implement fresh from tests. Not kept as reference, not
adapted while writing tests — deleted. Code you keep around is code you will adapt, and adapting
it is testing after.

## Red-Green-Refactor

**RED — write the failing test.** One minimal test showing what should happen: one behavior, a
name that describes that behavior, exercising real code rather than mocks. If the name needs an
"and", split it.

**Verify RED — watch it fail.** Mandatory; run it yourself, every time. Confirm the test *fails*
rather than errors, that the failure message is the one you expected, and that it fails because
the feature is missing rather than because of a typo. A test that passes here is testing existing
behavior — fix the test. A test that errors here needs the error fixed and a re-run.

**GREEN — minimal code.** The simplest code that passes the test in front of you. No extra
options, hooks, or configurability for a feature you imagine coming next — that is YAGNI. No
refactoring of other code, no improvements beyond the test.

**Verify GREEN — watch it pass.** Mandatory; run it yourself. Confirm the new test passes, the
other tests still pass, and the output is pristine (no stray errors or warnings). If the new test
fails, fix the code, not the test. If other tests fail, fix them now.

**REFACTOR — clean up.** Only after green: remove duplication, improve names, extract helpers.
Tests stay green; no new behavior.

Then repeat with the next failing test.

## Good Tests

A good test is **minimal** (one thing), **clear** (the name describes the behavior, not `test1`),
and **shows intent** (it demonstrates the API you want, so a reader learns how the code is meant
to be used).

## Why Order Matters

A test written after the code passes immediately, and passing immediately proves nothing — you
never saw it catch anything, and it is shaped by the implementation you already wrote rather than
by what the code is required to do. Test-first forces you to discover the edge cases before
implementing; tests-after only verify the ones you happened to remember.

## When Stuck

| Problem | Solution |
|---------|----------|
| Don't know how to test | Write the wished-for API. Write the assertion first. Ask your human partner. |
| Test too complicated | The design is too complicated. Simplify the interface. |
| Must mock everything | Code too coupled. Use dependency injection. |
| Test setup huge | Extract helpers. Still complex? Simplify the design. |

## Debugging Integration

Bug found? Write a failing test reproducing it, then follow the cycle — the test proves the fix
and prevents the regression. When the cause is not yet obvious, find root cause first with
`spec-loop:systematic-debugging`, then return here to write the reproducing test before touching
the fix.

## Testing Anti-Patterns

When adding mocks or test utilities, read [testing-anti-patterns.md](testing-anti-patterns.md) —
testing mock behavior instead of real behavior, test-only methods on production classes, mocking
without understanding the dependency, and partial mocks that fail silently.

## Verification Checklist

Before marking work complete:

- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing, for the expected reason
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass, output pristine
- [ ] Tests use real code (mocks only if unavoidable)
- [ ] Edge cases and errors covered

## Final Rule

```
Production code → test exists and failed first
Otherwise → not TDD
```

No exceptions without your human partner's permission.
