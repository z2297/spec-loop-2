---
name: using-spec-loop
description: Use when starting any task or conversation in a repo that uses spec-loop, when unsure which skill or command you should use, or before responding, asking clarifying questions, or exploring the codebase — establishes how to find and invoke the right spec-loop entry point before ANY response.
---

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a task — an implementer, planner, critic, reviewer, verifier, simplifier, or the inline slice-worker fallback — ignore this skill. It routes interactive sessions; a task-executor that re-entered it would recursively re-run the framework on its own subtask. Do your assigned task under the doctrine your dispatch prompt and agent definition name.
</SUBAGENT-STOP>

# Using spec-loop — the router

## Overview

This is the gateway for interactive work in a spec-loop repo. spec-loop has **no SessionStart
hook** (deliberate — the framework stays dormant until it is relevant); this skill loads on
demand via its description. Its whole job is to make you check for the right entry point and
use it **before** you do anything else.

## The Rule

If an entry point plausibly applies to the task, use it before responding — including before
clarifying questions, exploring the codebase, or checking files. Say which one you are using and
why. If it turns out wrong for the situation you don't have to keep using it, but you check
first. Follow a skill exactly; if it has a checklist, create one todo per item.

## Multi-step work belongs in the loop

The single most common routing mistake is hand-rolling a multi-step change in the interactive
session. If the request needs more than one coherent commit — a feature, a refactor across
files, anything with a plan — run `/spec-loop`. Its Phase 0 does the intake work (restate,
explore, challenge the premise, decompose) that v1 shipped as separate brainstorming and
planning skills, and every slice then gets planning, critique, review, a quality gate, and
verification for free.

## Commands

| Command | Use WHEN |
|---|---|
| `/spec-loop <request>` | Any multi-step change. Decomposes into slices and runs each wave as a deterministic workflow: plan → critique → implement → review ∥ quality gate → fix → verify, merging serially onto one integration branch. Ends with a committed runbook and a publish prompt. |
| `/spec-loop:review-pr` | You want a review of a diff or PR *now*, aspect-based, without running a loop. Read-only. |
| `/spec-loop:peer-review` | A real open/merged PR plus business requirements to vet; publishes ONE advisory review report. Never edits, merges, or posts. |
| `/spec-loop:quality-gate` | View or change the objective code-quality thresholds (complexity, method length, CRAP, custom gates) the loop enforces at every tier. |
| `/spec-loop:knowledge-graph` | View or change the Obsidian knowledge-graph config, or ask a read-only question of the accumulated graph. |
| `/spec-loop:dashboard` | Read a run's state as terminal markdown (DAG, waves, slices, escalations, decisions). |
| `/spec-loop:dashboard-serve` | Start (or reuse) the machine-wide read-only web dashboard across every repo you have run the loop in. |

## Process skills

Five skills ship for interactive and non-loop use. Inside a run, the loop's agents carry this
doctrine themselves — you do not invoke these on a slice's behalf.

| Skill | Use WHEN |
|---|---|
| `using-spec-loop` | This router. Starting any task/conversation, or unsure what applies. |
| `test-driven-development` | Implementing any feature or bugfix, before writing implementation code. |
| `systematic-debugging` | Any bug, test failure, or unexpected behavior, before proposing a fix. |
| `verification-before-completion` | About to claim work is complete/fixed/passing, before committing or opening a PR. **Hard gate — never skipped, at any layer.** |
| `escalation-gate` | The autonomy contract *inside* a run: before stopping or asking the human anything, decide proceed-and-log vs. surface. Owns all human contact during a run. |

**Priority:** process skills come first — they set the approach, then the work carries it out.
"Fix this bug" starts at `systematic-debugging`; "implement this" starts at
`test-driven-development`; either way, finishing runs through `verification-before-completion`.

## Where the rest of the machinery lives

v2 has no skill for the loop's own internals — they are agents, one workflow, and reference
files, invoked by `/spec-loop`, not by you. Knowing where a concern already lives keeps you from
re-deriving it: risk tiers and what each tier buys → `references/risk-tiers.md`; run-state shapes
→ `references/run-state-v2.md`; the integration gate, runbook, and publish prompt →
`references/phase-5-integration.md`; grafting a SPLIT → `references/split-ingestion.md`; what
changed since v1 → `references/migration-from-v1.md`.

**Inside an active run:** subagents ignore this router (see `<SUBAGENT-STOP>`), and every human
checkpoint is governed by `escalation-gate` — batched to the wave boundary, never mid-wave.
`verification-before-completion` is the one thing that gate never waives.

## User Instructions

User instructions (CLAUDE.md, AGENTS.md, direct requests) take precedence over skills, which in
turn override default behavior. Only skip a skill or instruction when your human partner has
explicitly told you to.

## When NOT to use this

Skip it when you were dispatched as a task-executing subagent (see `<SUBAGENT-STOP>`), or when
you already know the exact entry point you need — use that directly. Deciding whether to
interrupt the human mid-run is `escalation-gate`, not this skill.
