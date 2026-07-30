# Testing Anti-Patterns

**Load this reference when:** writing or changing tests, adding mocks, or tempted to add
test-only methods to production code.

## Overview

Tests must verify real behavior, not mock behavior. Mocks are a means to isolate, not the thing
being tested.

**Core principle:** Test what the code does, not what the mocks do.

Following strict TDD prevents all five of these.

## The Iron Laws

```
1. NEVER test mock behavior
2. NEVER add test-only methods to production classes
3. NEVER mock without understanding dependencies
```

## Anti-Pattern 1: Testing Mock Behavior

```typescript
// ❌ BAD: asserting the mock exists
test('renders sidebar', () => {
  render(<Page />);
  expect(screen.getByTestId('sidebar-mock')).toBeInTheDocument();
});

// ✅ GOOD: test the real component's observable behavior
test('renders sidebar', () => {
  render(<Page />);            // don't mock the sidebar
  expect(screen.getByRole('navigation')).toBeInTheDocument();
});
```

The bad version passes when the mock is present and fails when it isn't — it says nothing about
the component. If the dependency genuinely must be mocked for isolation, assert on the *host's*
behavior with it present, never on the mock itself.

**Gate:** before asserting on any mock element, ask "am I testing real behavior or mock
existence?" If the latter, delete the assertion or unmock the component.

## Anti-Pattern 2: Test-Only Methods in Production

```typescript
// ❌ BAD: destroy() exists only so tests can clean up — but it looks like production API
class Session {
  async destroy() { await this._workspaceManager?.destroyWorkspace(this.id); }
}

// ✅ GOOD: test utilities own test cleanup; Session has no destroy()
export async function cleanupSession(session: Session) { /* … */ }
```

A production class polluted with test-only code is dangerous if it is ever called for real, and it
confuses object lifecycle with entity lifecycle.

**Gate:** before adding any method to a production class, ask "is this only used by tests?" (then
it belongs in test utilities) and "does this class own this resource's lifecycle?" (if not, wrong
class).

## Anti-Pattern 3: Mocking Without Understanding

```typescript
// ❌ BAD: the mock removes the config write this test depends on — the duplicate is never detected
test('detects duplicate server', () => {
  vi.mock('ToolCatalog', () => ({ discoverAndCacheTools: vi.fn().mockResolvedValue(undefined) }));
  await addServer(config);
  await addServer(config);   // should throw — won't
});

// ✅ GOOD: mock the slow part only, preserve the behavior the test needs
test('detects duplicate server', () => {
  vi.mock('MCPServerManager');  // just the slow server startup
  await addServer(config);
  await addServer(config);      // duplicate detected
});
```

Over-mocking "to be safe" makes the test pass for the wrong reason or fail mysteriously.

**Gate:** before mocking a method, answer three questions — what side effects does the real method
have, does this test depend on any of them, and do I understand what the test needs? If it depends
on side effects, mock at a lower level (the actual slow/external operation), not the high-level
method. If you can't answer, run the test against the real implementation first and observe what
must happen.

**Red flags:** "I'll mock this to be safe." "This might be slow, better mock it." Mocking without
knowing the dependency chain.

## Anti-Pattern 4: Incomplete Mocks

```typescript
// ❌ BAD: only the fields you happened to think of
const mockResponse = { status: 'success', data: { userId: '123', name: 'Alice' } };
// breaks later when code reads response.metadata.requestId

// ✅ GOOD: mirror the real response completely
const mockResponse = {
  status: 'success',
  data: { userId: '123', name: 'Alice' },
  metadata: { requestId: 'req-789', timestamp: 1234567890 },
};
```

Partial mocks hide structural assumptions: downstream code may depend on fields you omitted, so
the test passes while the integration fails.

**The Iron Rule:** mock the COMPLETE data structure as it exists in reality, not just the fields
your immediate test reads. If you are creating a mock, you must understand the entire structure;
when uncertain, include every documented field.

## Anti-Pattern 5: Tests as an Afterthought

"Implementation complete, no tests written, ready for testing" is not a complete implementation.
Testing is part of implementation, not an optional follow-up — and TDD would have caught the gap
before it existed.

## When Mocks Become Too Complex

**Warning signs:** mock setup longer than the test logic; mocking everything to make a test pass;
mocks missing methods the real components have; the test breaking whenever the mock changes.

**Consider:** integration tests with real components are often simpler than elaborate mocks. The
useful question is "do we need a mock here at all?"

## Quick Reference

| Anti-Pattern | Fix |
|--------------|-----|
| Assert on mock elements | Test the real component, or unmock it |
| Test-only methods in production | Move to test utilities |
| Mock without understanding | Understand dependencies first, mock minimally |
| Incomplete mocks | Mirror the real structure completely |
| Tests as afterthought | TDD — test first |
| Over-complex mocks | Consider integration tests |

**Red flags:** assertions on `*-mock` test IDs; methods called only from test files; mock setup
>50% of the test; a test that fails when you remove a mock; not being able to explain why a mock
is needed.

## The Bottom Line

Mocks are tools to isolate, not things to test. If you are testing mock behavior, you added mocks
without ever watching the test fail against real code — which means you skipped TDD.

---

*Ported from `superpowers` v6.1.1 (github.com/obra/superpowers, MIT)
`skills/test-driven-development/testing-anti-patterns.md` via spec-loop v1; condensed for v2,
doctrine unchanged. Referenced from `SKILL.md` "when adding mocks or test utilities".*
