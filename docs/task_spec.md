# Task Specification

Two formats depending on the nature of the task.

## Formal proposal (for non-trivial changes, filed in `docs/proposals/`)

```markdown
# Proposal: <name>

> <one-line summary>

---

## Problem

Why this change is needed.

## Diagnosis

Root cause analysis — what's actually broken or missing at the code level.

## Proposed solution

What will be done, which files change, and how.

## Rationale

Why this approach over alternatives. Tradeoffs considered and accepted.
```

## Lightweight task spec (for chat-based tasks — restated by the agent before coding)

```
**Goal:** <one sentence>
**Target files:** <path/to/file.py:function, path/to/other.py:Class>
**Current behavior:** <what happens now; include logs/types for bugs>
**Acceptance criteria:**
  - [ ]
**Non-goals:**
  - NOT ...
**Test plan:** <pytest -k test_X, or "add test for Y">
```

Both formats share the same spirit: upfront analysis, explicit scope, and falsifiable outcomes.
