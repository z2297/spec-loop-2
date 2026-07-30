# Defense-in-Depth Validation

## Overview

When you fix a bug caused by invalid data, adding validation in one place feels sufficient. But
that single check can be bypassed by a different code path, by refactoring, or by a mock.

**Core principle:** validate at EVERY layer the data passes through. Make the bug structurally
impossible.

Single validation says "we fixed the bug." Multiple layers say "we made the bug impossible" — and
each layer catches a different class of case: entry validation catches most bugs, business logic
catches edge cases, environment guards prevent context-specific dangers, and debug logging is what
helps when the other three fail.

## The Four Layers

**Layer 1 — Entry point validation.** Reject obviously invalid input at the API boundary.

```typescript
function createProject(name: string, workingDirectory: string) {
  if (!workingDirectory?.trim()) throw new Error('workingDirectory cannot be empty');
  if (!existsSync(workingDirectory)) throw new Error(`does not exist: ${workingDirectory}`);
  if (!statSync(workingDirectory).isDirectory()) throw new Error(`not a directory: ${workingDirectory}`);
}
```

**Layer 2 — Business logic validation.** Ensure the data makes sense for *this* operation.

```typescript
function initializeWorkspace(projectDir: string, sessionId: string) {
  if (!projectDir) throw new Error('projectDir required for workspace initialization');
}
```

**Layer 3 — Environment guards.** Refuse dangerous operations in contexts where they cannot be
legitimate.

```typescript
async function gitInit(directory: string) {
  if (process.env.NODE_ENV === 'test') {
    const normalized = normalize(resolve(directory));
    if (!normalized.startsWith(normalize(resolve(tmpdir())))) {
      throw new Error(`Refusing git init outside temp dir during tests: ${directory}`);
    }
  }
}
```

**Layer 4 — Debug instrumentation.** Capture context for forensics before the operation runs
(directory, cwd, stack).

## Applying the Pattern

1. **Trace the data flow** — where does the bad value originate, and where is it used?
2. **Map all checkpoints** — list every point the data passes through.
3. **Add validation at each layer** — entry, business, environment, debug.
4. **Test each layer** — try to bypass layer 1 and verify layer 2 catches it. A layer you never
   proved fires is a layer you don't have.

## Worked example

An empty `projectDir` caused `git init` to run in the source tree. Data flow: test setup produced
an empty string → `Project.create(name, '')` → `WorkspaceManager.createWorkspace('')` → `git init`
in `process.cwd()`. Four layers were added — `Project.create` validates non-empty/exists/writable,
`WorkspaceManager` validates non-empty, `WorktreeManager` refuses git init outside tmpdir during
tests, and stack-trace logging fires before git init.

All four proved necessary: different code paths bypassed the entry validation, mocks bypassed the
business-logic check, platform edge cases needed the environment guard, and the logging is what
identified structural misuse. **Don't stop at one validation point.**
