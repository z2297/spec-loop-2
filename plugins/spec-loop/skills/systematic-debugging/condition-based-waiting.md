# Condition-Based Waiting

## Overview

Flaky tests often guess at timing with arbitrary delays. That creates race conditions: the test
passes on a fast machine and fails under load or in CI.

**Core principle:** wait for the actual condition you care about, not a guess about how long it
takes.

**Use when:** tests contain arbitrary delays (`setTimeout`, `sleep`, `time.sleep()`); tests are
flaky or time out when run in parallel; you are waiting for an async operation to complete.

**Don't use when:** you are testing timing behavior itself (debounce, throttle intervals). Even
then, document *why* the timeout is needed.

## Core Pattern

```typescript
// ❌ BEFORE: guessing at timing
await new Promise(r => setTimeout(r, 50));
const result = getResult();

// ✅ AFTER: waiting for the condition
await waitFor(() => getResult() !== undefined);
const result = getResult();
```

| Scenario | Pattern |
|----------|---------|
| Wait for event | `waitFor(() => events.find(e => e.type === 'DONE'))` |
| Wait for state | `waitFor(() => machine.state === 'ready')` |
| Wait for count | `waitFor(() => items.length >= 5)` |
| Wait for file | `waitFor(() => fs.existsSync(path))` |
| Complex condition | `waitFor(() => obj.ready && obj.value > 10)` |

## Implementation

```typescript
async function waitFor<T>(
  condition: () => T | undefined | null | false,
  description: string,
  timeoutMs = 5000
): Promise<T> {
  const startTime = Date.now();
  while (true) {
    const result = condition();
    if (result) return result;
    if (Date.now() - startTime > timeoutMs) {
      throw new Error(`Timeout waiting for ${description} after ${timeoutMs}ms`);
    }
    await new Promise(r => setTimeout(r, 10)); // poll every 10ms
  }
}
```

Wrap it in domain-specific helpers where the same wait recurs (`waitForEvent`,
`waitForEventCount`, `waitForEventMatch`) so the intent reads at the call site.

## Common Mistakes

- **Polling too fast** (`setTimeout(check, 1)`) wastes CPU → poll every ~10ms.
- **No timeout** loops forever when the condition never holds → always time out with a message
  naming what you were waiting for.
- **Stale data** captured before the loop → call the getter *inside* the loop.

## When an Arbitrary Timeout IS Correct

```typescript
await waitForEvent(manager, 'TOOL_STARTED'); // first: wait for the triggering condition
await new Promise(r => setTimeout(r, 200));  // then: 2 ticks at the tool's known 100ms interval
```

Three requirements: wait for the triggering condition first; base the delay on known timing rather
than a guess; comment why.
