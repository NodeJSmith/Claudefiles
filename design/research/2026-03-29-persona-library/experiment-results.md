# Persona Experiment Analysis
Date: 2026-03-29

## Experiment Design

- **Target A**: `mine.challenge/SKILL.md` (373 lines) — 3 generic critics + 3 SKILL.md specialists
- **Target B**: hassette `command_executor.py` + `scheduler_service.py` (1105 lines) — 3 generic critics + 3 Python async specialists
- **Control**: Current generic personas (Senior Engineer, Systems Architect, Adversarial Reviewer)
- **Treatment A**: SKILL.md specialists (Prompt Engineering, Contract & Caller, Workflow & UX)
- **Treatment B**: Python specialists (Async & Concurrency, Data Integrity, Operational Resilience)

## SKILL.md Target Results

### Findings that ALL 6 critics caught (overlap)
- Pushback section produces hallucinated disagreements (6/6)
- Inline content detection heuristic is fragile (4/6)
- Auto-apply concept is problematic (4/6)
- Rule count mismatch "six rules" → seven items (2/6)

### Findings ONLY generics caught
- WebSearch requirement creates unbounded critic latency (Senior)
- No guardrail against persona convergence across same-model agents (Adversarial)
- 4-level agent nesting via orchestrate degrades instructions (Adversarial)
- TENSION overloads severity — should be a separate flag (Adversarial)

### Findings ONLY specialists caught
**Contract & Caller (5 unique findings)**:
- `Target:` field used by callers but NOT in the output contract
- Findings file header fields (Date, Target, Temp dir) are load-bearing but undocumented
- mine.build detects prior challenge via conversation text, coupling to presentation format
- Confidence tag format is inconsistent between examples (N/3 vs 1/3, X only)
- mine.grill uses structured-caller args with passthrough behavior = undocumented hybrid

**Workflow & UX (4 unique findings)**:
- No progress signal during the long parallel-critic wait
- Empty-arguments recon uses weak heuristics (largest files, recent changes)
- Information overload: 5 representations of the same findings
- No redirect when user invokes challenge on an artifact better suited to grill

**Prompt Engineering (1 unique finding)**:
- file:line citation requirement conflicts with Gap-type findings on document targets

### SKILL.md Verdict
**Contract & Caller was the standout** — 5 findings no generic critic surfaced, all about the integration surface between skills. These are actionable, specific, and non-obvious.

**Workflow & UX** found 4 novel UX issues invisible to correctness-focused critics.

**Prompt Engineering** had the most overlap with generics — it found the same issues with slightly different framing. Only 1 truly unique finding.

---

## Python Target Results

### Findings that ALL 6 critics caught (overlap)
- Unbounded write queue with no backpressure (6/6)
- Race between job enqueue and DB registration (5/6)
- _wakeup_event.clear() drops concurrent kicks (4/6)
- Non-future reschedule creates tight loop (4/6)
- _flush_queue has no error handling during shutdown (4/6)

### Findings ONLY generics caught
- _execute_handler / _execute_job are ~170 lines of near-identical code (Architect + Adversarial)
- Record construction copy-pasted into 8 sites (Architect)
- Trigger serialization isinstance chain with silent None fallback (Architect)
- Raw SQL hardcoded in CommandExecutor (Architect)
- _safe_session_id returns 0 causing silent record drops (Architect)
- HeapQueue.__iter__ returns live iterator over mutable list (Senior)
- HeapQueue removal is O(n) scan + O(n log n) heapify (Adversarial)

### Findings ONLY specialists caught
**Data Integrity (3 unique findings)**:
- _do_clear_registrations deletes from two tables without explicit transaction — crash between DELETEs leaves inconsistent state
- _do_persist_batch issues two executemany calls under one commit without explicit transaction boundary — partial batch on crash
- One-shot jobs queued but not yet executed are lost on restart (no job persistence)

**Operational Resilience (3 unique findings)**:
- No timeout on handler invoke — hung handler blocks indefinitely
- Unbounded concurrent job dispatch via task_bucket.spawn, thundering herd when cron jobs align
- No observability into queue depth, batch size, or persist latency

**Async & Concurrency (1 unique finding)**:
- ensure_future tasks in serve() leak if coroutine is cancelled externally rather than via shutdown_event

### Python Verdict
**Data Integrity was the standout** — found transaction safety issues (non-atomic multi-table deletes, partial batch writes, no job persistence) that NO generic critic caught. These are real bugs.

**Operational Resilience** found timeout and thundering herd issues that are genuine production risks no generic identified.

**Async & Concurrency** had the most overlap — the generics already have strong async instincts. Only 1 truly unique finding (task leak on cancellation).

**However**: The generics (especially Architect) caught structural/design issues that ALL specialists missed — code duplication, SQL coupling, isinstance chains, API contract quality. The specialists went deep on domain-specific failure modes but missed the forest for the trees.

---

## Cross-Target Patterns

### Which specialists added the most value?
1. **Contract & Caller** (SKILL.md) — 5 unique findings, all actionable
2. **Data Integrity** (Python) — 3 unique findings, real bugs
3. **Operational Resilience** (Python) — 3 unique findings, production risks
4. **Workflow & UX** (SKILL.md) — 4 unique findings, UX-specific
5. **Async & Concurrency** (Python) — 1 unique finding, mostly overlapped with generics
6. **Prompt Engineering** (SKILL.md) — 1 unique finding, mostly overlapped with generics

### Which generics would be missed if replaced?
- **Systems Architect** — caught structural/design issues no specialist found (code duplication, coupling, API contracts). Would be a significant loss.
- **Adversarial Reviewer** — caught systemic concerns (persona convergence, nesting depth, TENSION overloading severity). Some overlap with specialists but unique perspective.
- **Senior Engineer** — highest overlap with specialists. Most of their findings were also found by at least one specialist. Lowest unique contribution.

### Key insight
**The optimal set is NOT "replace generics with specialists."** It's **"keep the best generics and ADD the best specialists."** The Architect's structural eye and the specialists' domain depth are complementary, not substitutional.

---

## Implications for Issue #130

1. **The premise is validated**: Specialist personas DO surface findings that generic personas miss. The Contract & Caller critic and Data Integrity critic each found 3-5 unique, actionable findings.

2. **But replacement is wrong**: Dropping generics for specialists loses structural/design coverage. The ideal is augmentation — 3 generics + 1-2 domain specialists = 4-5 critics per run.

3. **Not all specialists add equal value**: Prompt Engineering and Async & Concurrency overlapped heavily with generics. The value is in critics whose focus area is ORTHOGONAL to the generics, not a subset.

4. **Selection criteria emerge naturally**: The best specialist for a target isn't "the one whose tags match" — it's "the one whose lens covers what the generics are blind to." For SKILL.md files, that's contract/caller concerns. For async Python, that's data integrity and operational resilience.
