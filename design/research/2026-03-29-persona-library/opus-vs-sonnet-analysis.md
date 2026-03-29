# Opus vs Sonnet Persona Experiment Comparison
Date: 2026-03-29

## Experiment Design

Same 12 critic configurations (3 generic + 3 specialist per target), same targets, same prompts.
- **Run 1 (Opus)**: Results in `*-opus` files (the originals without suffix)
- **Run 2 (Sonnet)**: Results in `*-sonnet` files

---

## SKILL.md Target: Finding Overlap

### Core findings BOTH models caught (high confidence — real issues)
- Pushback section produces hallucinated/speculative disagreements (all 6 critics, both models)
- Inline content vs file path detection is fragile (4+/6, both models)
- Auto-apply concept is problematic for a findings-only skill (3+/6, both models)
- Passthrough vs standalone caller detection is indistinguishable (3+/6, both models)
- Flag parsing breaks on edge cases (2+/6, both models)
- Target-type heuristic has no tiebreaker (2+/6, both models)

### Opus-only findings (not in any Sonnet report)
- WebSearch requirement creates unbounded critic latency (Senior)
- 4-level agent nesting via orchestrate degrades instructions (Adversarial)
- TENSION overloads severity — should be a separate flag (Adversarial)
- mine.grill is an undocumented hybrid caller category (Contract specialist)
- Confidence format inconsistent between examples (Contract specialist)

### Sonnet-only findings (not in any Opus report)
- No context budget cap for subagents — critics can evict target from window (Senior) **NEW**
- Output contract has no version field (Architect + Adversarial + Workflow) **NEW**
- Dual output surfaces — findings file + presentation must stay in sync (Architect) **NEW**
- Three-way behavioral fork defined at end of prompt, too late (Architect) **NEW**
- Highest severity lets one critic escalate without floor (Senior + Adversarial) **NEW**
- side-a/side-b/deciding-factor: callers don't read deciding-factor — info loss (Contract) **NEW**
- SYNC comments live in callers, not authoritative contract (Contract) **NEW**
- Auto-apply locality rules undefined for code targets (Prompt Engineering) **NEW**

### SKILL.md Specialist Advantage — Model Comparison

| Specialist | Opus unique findings | Sonnet unique findings |
|-----------|---------------------|----------------------|
| Contract & Caller | 5 | 5 |
| Workflow & UX | 4 | 4 |
| Prompt Engineering | 1 | 2 |

**Verdict**: Specialist advantage is consistent across models. Both Opus and Sonnet Contract & Caller critics found ~5 unique findings no generic caught. The specialist lens matters more than the model.

---

## Python Target: Finding Overlap

### Core findings BOTH models caught
- Unbounded write queue, no backpressure (all 6, both models)
- _enqueue_then_register race — job fires before db_id set (5/6, both)
- _wakeup_event.clear() drops concurrent kicks (4/6, both)
- Reschedule tight loop / stuck trigger (4/6, both)
- _flush_queue no error handling on shutdown (4/6, both)
- _execute_handler/_execute_job code duplication (Architect + Adversarial, both)
- isinstance trigger serialization chain (Architect, both)
- Mutable ScheduledJob shared across async boundaries (Async specialist, both)

### Opus-only findings
- HeapQueue.__iter__ returns live iterator over mutable list (Senior)
- Raw SQL hardcoded in CommandExecutor (Architect)
- _safe_session_id returns 0 causing silent drops (Architect)
- HeapQueue removal is O(n) scan + O(n log n) heapify (Adversarial)
- One-shot jobs lost on restart — no job persistence (Data Integrity specialist) **notable**

### Sonnet-only findings
- Mixed clocks: time.time() vs time.monotonic() — NTP steps corrupt timestamps (Senior) **NEW**
- execute() match has no wildcard arm — unknown commands silently no-op (Senior) **NEW**
- kick() has no shutdown guard — sets event on dead loop (Async specialist) **NEW**
- session_id == 0 dead-letter with no counter — invisible telemetry loss (Data specialist) **NEW**
- Interval rescheduling from scheduled time not wall-clock — accumulates lag (Ops specialist) **NEW**
- DST/clock skew in reschedule_job (Adversarial) **NEW**
- _flush_queue has no timeout — stalled DB means process never exits (Ops specialist) **NEW**
- ScheduledJob mutation elevated to CRITICAL with detailed concurrent task analysis (Async) — more specific than Opus

### Python Specialist Advantage — Model Comparison

| Specialist | Opus unique findings | Sonnet unique findings |
|-----------|---------------------|----------------------|
| Data Integrity | 3 | 2 |
| Ops Resilience | 3 | 3 |
| Async & Concurrency | 1 | 2 |

**Verdict**: Similar specialist advantage across models. Sonnet Ops found different unique things than Opus Ops but the same count. The Data Integrity specialist was slightly stronger on Opus (found one-shot job persistence gap that Sonnet missed).

---

## Cross-Model Patterns

### 1. Finding overlap is high
Both models catch the same core issues. The "big 5" findings (unbounded queue, race condition, wakeup clear, reschedule loop, flush no error handling) appeared in BOTH models across BOTH targets. These are high-confidence real issues.

### 2. Each model finds novel things the other misses
- **Opus strengths**: More architectural/structural findings (HeapQueue API issues, SQL coupling, 4-level nesting, TENSION overloading severity). Opus seems to think more about system shape.
- **Sonnet strengths**: More operational/edge-case findings (mixed clocks, no shutdown guard, no timeout on flush, DST handling, contract versioning). Sonnet seems to think more about runtime failure modes.

### 3. Specialist advantage is MODEL-INDEPENDENT
This is the key finding. The specialist lens (Contract & Caller, Data Integrity, etc.) produces unique findings regardless of whether Opus or Sonnet runs. The persona matters more than the model for finding diversity.

### 4. Running both models would catch more
Combined unique findings across both runs:
- SKILL.md: Opus found 5 unique, Sonnet found 8 unique = 13 findings neither model's generics caught
- Python: Opus found 5 unique, Sonnet found 7 unique = 12 findings neither model's generics caught

### 5. Sonnet is competitive with Opus for this task
Sonnet found comparable or slightly more unique findings than Opus across both targets. For the cost profile of mine.challenge (launching 3-5 subagent critics), Sonnet may be the better value proposition — similar finding quality at lower cost per invocation.

---

## Implications for Issue #130

1. **Specialist personas work regardless of model** — the augmentation model is validated on both Opus and Sonnet. No need to mandate a specific model for critics.

2. **Consider model diversity as a future axis** — running Critic 1 on Opus and Critic 2 on Sonnet would maximize finding diversity (each model has different blind spots). This is a phase 2+ idea, not phase 1.

3. **Sonnet is viable for critic subagents** — the current mine.challenge uses `general-purpose` subagents which inherit the parent model. If cost is a concern, explicitly setting `model: sonnet` for critics would maintain quality while reducing cost. The specialist lens compensates for any model capability gap.

4. **Two-model runs as a premium mode** — a `--thorough` flag that runs all critics on both models and deduplicates would catch the most issues, at ~2x cost. Not for phase 1, but the data shows it has value.
