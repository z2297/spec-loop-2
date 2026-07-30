# Root Cause Tracing

## Overview

Bugs often manifest deep in the call stack (git init in the wrong directory, a file created in the
wrong location, a database opened with the wrong path). Your instinct is to fix where the error
appears, but that treats a symptom.

**Core principle:** trace backward through the call chain until you find the original trigger,
then fix at the source.

**Use when:** the error happens deep in execution rather than at an entry point; the stack trace
shows a long call chain; it is unclear where invalid data originated; you need to find which test
or code path triggers the problem. If backward tracing genuinely dead-ends, fixing at the symptom
point is the fallback — but say so explicitly rather than drifting into it.

## The Tracing Process

1. **Observe the symptom.** `Error: git init failed in ~/project/packages/core`
2. **Find the immediate cause** — what code directly does this?
   `await execFileAsync('git', ['init'], { cwd: projectDir })`
3. **Ask what called this**, and keep going up:
   `WorktreeManager.createSessionWorktree(projectDir, sessionId)` ← `Session.initializeWorkspace()`
   ← `Session.create()` ← the test's `Project.create()`
4. **Follow the value, not just the frames.** `projectDir = ''` — an empty string as `cwd`
   resolves to `process.cwd()`, which is the source directory.
5. **Find the original trigger.** `setupCoreTest()` returns `{ tempDir: '' }`, and the test read
   `context.tempDir` before `beforeEach` populated it.

Root cause: top-level variable initialization reading a not-yet-populated value. Fix at the
source (make `tempDir` a getter that throws if read too early), then add defense-in-depth at the
layers in between.

## Adding Stack Traces

When you cannot trace manually, instrument before the dangerous operation:

```typescript
async function gitInit(directory: string) {
  console.error('DEBUG git init:', {
    directory,
    cwd: process.cwd(),
    nodeEnv: process.env.NODE_ENV,
    stack: new Error().stack,
  });
  await execFileAsync('git', ['init'], { cwd: directory });
}
```

Then run and capture: `npm test 2>&1 | grep 'DEBUG git init'`.

- **In tests use `console.error()`,** not a logger — loggers are often suppressed.
- **Log before the operation,** not after it fails.
- **Include context:** directory, cwd, relevant environment variables.
- **Capture `new Error().stack`** for the complete call chain.

Reading the traces: look for test file names, find the triggering line number, and identify the
pattern — is it always the same test, or always the same parameter?

## Finding Which Test Causes Pollution

If something appears during a test run but you don't know which test creates it, use the bisection
script in this directory:

```bash
./find-polluter.sh '.git' 'src/**/*.test.ts'
```

It runs tests one by one and stops at the first polluter.

## Key Principle

**Never fix just where the error appears.** Trace up one level at a time until you reach the
source; fix there; then add validation at each layer the bad value passed through, so the bug
becomes structurally impossible (see [defense-in-depth.md](defense-in-depth.md)).

Then run `spec-loop:verification-before-completion` before claiming the fix holds.
