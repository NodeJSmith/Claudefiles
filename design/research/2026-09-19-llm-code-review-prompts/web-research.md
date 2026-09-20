## Sources Found

### How to Prompt for a Genuinely Useful Code Review (Prompt Architects)
- **URL**: https://prompt-architects.com/blog/106-how-to-prompt-for-a-genuinely-useful-code-review
- **Type**: blog post / practitioner guide
- **Key takeaway**: Defines a full concrete framework — a three-tier severity ladder anchored to observable consequences (BLOCKING/SHOULD-FIX/NOTE), a mandatory evidence shape per finding (trigger, falsifier, confidence, repro), and six required context inputs (diff + surrounding lines, stated intent, explicit non-goals, unstated invariants, call-site knowledge, already-covered concerns). Cites Google's AutoCommenter going from 54% to 80% "useful" ratio by narrowing scope to one review lens per pass.
- **Relevance**: Directly on-topic — the single richest source found for structuring a code-review prompt that produces verifiable, non-noisy findings rather than pattern-matched guesses.

### Building a code review tool: The LLM patterns that actually work (G-Research)
- **URL**: https://www.gresearch.com/news/building-a-code-review-tool-the-llm-patterns-that-actually-work/
- **Type**: blog post / experience report
- **Key takeaway**: Splitting recall and precision into two separate prompts (first pass captures everything broadly, second pass filters for genuine violations with false-positive examples) outperformed one complex do-everything prompt. Structured, explicitly-scoped prompts (what to review vs. skip) cut noise roughly in half versus open-ended prompts.
- **Relevance**: Concrete two-pass architecture pattern directly applicable to review-prompt design; also documents that adding explicit "explain + suggest a fix" instructions can *increase* false positives by biasing the model toward finding something.

### Using LLMs to filter out false positives from static code analysis (Datadog)
- **URL**: https://www.datadoghq.com/blog/using-llms-to-filter-out-false-positives/
- **Type**: blog post / production experience report
- **Key takeaway**: Uses an LLM as a secondary filter on top of traditional static analysis findings rather than as the primary detector, and uses lightweight static analysis to pre-filter what's even sent to the LLM (avoiding queries about inapplicable issue classes).
- **Relevance**: Shows a hybrid architecture — LLM as filter/verifier layered on deterministic tools, not a from-scratch bug hunter — that reduces false positives structurally rather than through prompt wording alone.

### CodeRabbit Documentation — Architecture
- **URL**: https://docs.coderabbit.ai/overview/architecture
- **Type**: official documentation
- **Key takeaway**: Pipeline is preprocess PR → build cross-file context (clone repo, understand connections across files/functions/APIs/dependencies) → run 20+ linters/static analyzers in an isolated microVM → LLM analysis → post-processing/verification layer that checks suggested comments against the actual code and repo config before posting.
- **Relevance**: Real-world commercial architecture combining static analysis with LLM review and an explicit post-hoc verification step — directly informs the "verify before surfacing" pattern.

### How CodeRabbit Works: Inside Its AI Code Review Pipeline (The AI Engineer / Substack)
- **URL**: https://theaiengineer.substack.com/p/how-coderabbit-actually-works
- **Type**: blog post / technical writeup
- **Key takeaway**: Subtask-specific context is isolated per sub-agent so it doesn't pollute the main review thread; findings go through a deliberate selection pass based on what earlier specialized agents found relevant, then a separate verification layer checks each comment against code and repo config before it reaches the PR.
- **Relevance**: Multi-stage agent pipeline with isolated context windows per concern and a final verification gate — a pattern for avoiding both context bleed and unverified claims.

### Explainable AI Code Review: How CodeRabbit Review Works (CodeRabbit blog)
- **URL**: https://www.coderabbit.ai/blog/coderabbit-review-reads-a-pr-how-author-would-explain-it
- **Type**: blog post / vendor documentation
- **Key takeaway**: Frames review generation as "explain the PR the way its author would" — building author-intent understanding before critiquing, rather than pattern-matching diffs in isolation.
- **Relevance**: Supports the "intent statement" context requirement echoed across other sources (Prompt Architects, G-Research).

### Using custom instructions to unlock the power of Copilot code review (GitHub Docs)
- **URL**: https://docs.github.com/en/copilot/tutorials/customize-code-review
- **Type**: official documentation
- **Key takeaway**: Repository-wide guidance goes in `.github/copilot-instructions.md`; Copilot code review only reads the first 4,000 characters of any custom instruction file — instructions beyond that limit are silently ignored. Recommends starting with a minimal instruction set and iterating based on what actually improves reviews, rather than front-loading exhaustive rules.
- **Relevance**: Concrete constraint on prompt length for a shipping commercial tool, and validates "start minimal, iterate empirically" over comprehensive upfront rule-writing.

### Copilot code review and coding agent now support agent-specific instructions (GitHub Changelog)
- **URL**: https://github.blog/changelog/2025-11-12-copilot-code-review-and-coding-agent-now-support-agent-specific-instructions/
- **Type**: official documentation / changelog
- **Key takeaway**: New `excludeAgent` property lets teams scope specific `.instructions.md` files so they apply to coding agents but not review agents (or vice versa) — acknowledging that a single instruction file that's good for code generation is often wrong for review.
- **Relevance**: Evidence that generation prompts and review prompts need to diverge, not share one instruction file.

### Reducing False Positives in Static Bug Detection with LLMs: An Empirical Study in Industry
- **URL**: https://arxiv.org/pdf/2601.18844
- **Type**: academic paper (industry study)
- **Key takeaway**: Empirical industrial study specifically targeting false-positive reduction when LLMs sit downstream of static bug detectors.
- **Relevance**: Academic backing for the "LLM as filter after static analysis" pattern seen at Datadog.

### Are LLMs Reliable Code Reviewers? Systematic Overcorrection in Requirement Conformance Judgement
- **URL**: https://arxiv.org/pdf/2603.00539
- **Type**: academic paper
- **Key takeaway**: Documents a systematic bias where LLMs "overcorrect" — flagging correct implementations as non-conformant to requirements — when asked to judge requirement conformance, i.e., a structural tendency to manufacture findings rather than report "no issue."
- **Relevance**: Names a specific, citable failure mode (overcorrection / manufactured findings) relevant to designing prompts that don't force a finding when none exists.

### Meta's new structured prompting technique makes LLMs significantly better at code review (VentureBeat, covering Meta research)
- **URL**: https://venturebeat.com/orchestration/metas-new-structured-prompting-technique-makes-llms-significantly-better-at
- **Type**: press coverage of industry research
- **Key takeaway**: Meta's "semi-formal reasoning" technique requires the model to state explicit premises, trace concrete execution paths, and derive formal conclusions before answering — reaching 93% accuracy on patch-equivalence judgments, far above unstructured prompting.
- **Relevance**: Strong evidence that requiring explicit, traceable reasoning steps (not just "look for bugs") materially improves correctness of LLM code judgments.

### AI-Assisted Fixes to Code Review Comments at Scale (Meta / MetaMateCR)
- **URL**: https://arxiv.org/pdf/2507.13499
- **Type**: academic paper (industry, Meta)
- **Key takeaway**: Meta fine-tuned Llama models on a 64k-example internal benchmark of ⟨review comment, patch⟩ pairs; their largest fine-tuned model beat GPT-4o on their internal eval; validated via randomized controlled trials in production, not just offline benchmarks, before shipping to avoid slowing down real code review.
- **Relevance**: Shows the gold-standard evaluation bar (RCTs measuring actual review-time impact, not accuracy alone) that separates production-viable review tooling from a demo.

### BitsAI-CR: Automated Code Review via LLM in Practice (ByteDance, FSE 2025 Industry Track)
- **URL**: https://arxiv.org/pdf/2501.15134
- **Type**: academic paper (industry, ByteDance)
- **Key takeaway**: Two-stage pipeline — RuleChecker (initial issue detection against a curated taxonomy of review rules) feeding into ReviewFilter (precision verification pass) — plus a "data flywheel" that continuously retrains on developer feedback. Introduces an "Outdated Rate" metric measuring whether developers actually acted on a comment (adoption), as a better signal than raw precision/recall. Deployed to 12,000+ weekly active engineers.
- **Relevance**: A second independent confirmation (after G-Research and CodeRabbit) of the detect-then-filter two-stage pattern, plus a genuinely useful evaluation metric (adoption/outdated-rate) for judging whether findings are actually useful rather than merely plausible.

### How Many False Positives Are Too Many in AI Code Review (CodeAnt)
- **URL**: https://www.codeant.ai/blogs/ai-code-review-false-positives
- **Type**: blog post / vendor content
- **Key takeaway**: Documents the "alert fatigue" mechanism directly: each dismissed false positive lowers reviewer attention to the *next* comment, so genuine catches get the same reflexive skim as nonsense; a 15% false-positive rate on a 10-person team was estimated to cost ~2.5 eng-hours/week in triage.
- **Relevance**: Quantifies the cost of noisy review prompts and names the retraining-of-reviewer-attention dynamic — a strong argument for the severity-ladder / falsifier-gated approach.

### cubic blog: The false positive problem — why most AI code reviewers fail and how cubic solved it
- **URL**: https://www.cubic.dev/blog/the-false-positive-problem-why-most-ai-code-reviewers-fail-and-how-cubic-solved-it
- **Type**: blog post / vendor engineering writeup
- **Key takeaway**: Advocates separating mechanical verification (fully automatable — lint/type/format-level issues) from architectural review (needs human-level judgment), and having the AI focus its attention on architecture, invariants, and risk rather than formatting/style, which linters already cover better and more cheaply.
- **Relevance**: Reinforces "don't have the LLM re-derive what deterministic tools already catch" — a scoping principle for what the review prompt should even be asking about.

### Rethinking Code Review Workflows with LLM Assistance: An Empirical Study
- **URL**: https://arxiv.org/pdf/2505.16339
- **Type**: academic paper (industry field study, WirelessCar Sweden AB)
- **Key takeaway**: Field experiment found AI-led reviews were generally preferred by developers, but preference was conditional on the reviewer's own familiarity with the codebase and the severity/risk of the PR — i.e., trust in AI review is context-dependent, not uniform. Also names insufficient contextual information and false-positive concerns as the top blockers to adoption.
- **Relevance**: Grounds the "context injection" requirement (seen in Prompt Architects' six mandatory inputs) in an empirical field study rather than just vendor opinion.

### Trust-Calibrated Code Review: A Participatory Design Study of Review Workflows for LLM-Generated Multi-File Changes
- **URL**: https://arxiv.org/html/2606.01969
- **Type**: academic paper (participatory design study, 17 practitioners + 43-developer survey)
- **Key takeaway**: Identifies "trust calibration" — helping the reviewer know when to trust vs. double-check an AI finding — as the dominant practical challenge, ahead of raw accuracy. Proposes a three-level IDE review workflow as a structural response.
- **Relevance**: Supports designing review output with explicit confidence/evidence fields (as in the falsifier/confidence pattern) specifically to help the human calibrate trust per-finding rather than trust the tool uniformly.

## Patterns Found

### Pattern 1: Two-Stage Generate-Then-Filter Pipeline

**Used by**: G-Research (internal tool), ByteDance's BitsAI-CR (RuleChecker → ReviewFilter), Datadog (LLM as a filter atop static analysis), CodeRabbit (generation agents → verification layer)
**How it works**: Rather than a single prompt asked to both find and validate issues in one pass, the pipeline is split into two distinct stages with different objectives. Stage one optimizes for recall — it's encouraged to surface anything that might be an issue, cast broadly, over-generate. Stage two takes those candidate findings and re-examines them against the actual code/repo config with an objective of precision — discard, downgrade, or confirm each candidate. G-Research reports this mirrors how human reviewers naturally work (skim broadly, then double-check before commenting) and found it simpler and more effective than trying to get one prompt to be simultaneously thorough and precise.
**Strengths**: Decouples two objectives (recall vs. precision) that pull against each other in a single prompt; each stage can use different models/temperatures/context tuned to its narrower job; produces an auditable intermediate artifact (the candidate list) that can be logged and used for false-positive training data (as BitsAI-CR does with its "Outdated Rate" adoption metric).
**Weaknesses**: Doubles inference cost and latency; the filter stage is only as good as its own calibration — a filter that's too aggressive silently drops real findings, and there's no way to know without a labeled adoption/feedback loop like BitsAI-CR's.
**Example**: https://www.gresearch.com/news/building-a-code-review-tool-the-llm-patterns-that-actually-work/ ; https://arxiv.org/pdf/2501.15134

### Pattern 2: Fixed Evidence Shape with a Falsifier Field

**Used by**: Prompt Architects' methodology (explicit framework); implicitly required by BitsAI-CR's "Outdated Rate" adoption tracking and CodeRabbit's verification layer
**How it works**: Every finding a review agent produces must fill a fixed schema — not free text. The schema includes a concrete `trigger` (the specific input/state/call sequence that reaches the flagged code), a `falsifier` (what evidence would prove this specific finding wrong), a `confidence` rating, and ideally a `repro` (a test or command that goes green once fixed). If the model cannot fill in `trigger` and `falsifier` for a candidate finding, the rule is to downgrade it automatically to a low-severity "unverified pattern match" rather than presenting it as an equal-weight finding. This forces the model to justify a claim with something checkable instead of a plausible-sounding narrative, which is exactly the mode where LLMs are shown (arxiv 2603.00539) to systematically overcorrect and manufacture findings.
**Strengths**: Makes each finding independently checkable by a human in seconds (rerun the trigger, does it reproduce?) rather than requiring the reviewer to reconstruct the reasoning themselves; naturally suppresses vague, pattern-matched noise because vague findings can't fill the schema; gives calibration data for the trust problem identified in the participatory design study (arxiv 2606.01969).
**Weaknesses**: Adds prompt complexity and token overhead per finding; a model can still fabricate a plausible-looking but wrong trigger/falsifier if not cross-checked against actual code; doesn't eliminate the need for a verification pass — it's complementary to Pattern 1, not a replacement.
**Example**: https://prompt-architects.com/blog/106-how-to-prompt-for-a-genuinely-useful-code-review

### Pattern 3: Consequence-Anchored Severity Ladder (Not Adjective-Based)

**Used by**: Prompt Architects methodology; implicit in most vendor tools (CodeRabbit, CodeAnt) that gate what surfaces vs. what's suppressed
**How it works**: Instead of severity labels like "critical/major/minor" that are subjective and drift per-model, the ladder is defined by observable, falsifiable consequence: BLOCKING means unrecoverable or silent damage (data loss, wrong money moved, auth bypass) if shipped as-is; SHOULD-FIX means something breaks *visibly* and can be fixed forward later (a 500 on a real input path, a swallowed error); NOTE means no runtime consequence, just future maintenance cost. A hard cap (e.g., "maximum three BLOCKING findings; if you have more, name the one you're least confident about and demote it") forces the model to actually rank rather than inflate everything to maximum severity — directly countering the overcorrection bias documented academically.
**Strengths**: Ties severity to something checkable (would this actually cause the stated harm?) rather than a vibe; the hard cap on top-severity findings forces genuine triage instead of alarm-fatigue-inducing "everything is critical" output; maps cleanly onto how humans already prioritize PR feedback.
**Weaknesses**: Requires the prompt author to correctly anticipate the domain's actual failure modes (what "silent damage" even means differs by codebase); a cap on BLOCKING findings can suppress a genuinely bug-dense PR if applied too rigidly.
**Example**: https://prompt-architects.com/blog/106-how-to-prompt-for-a-genuinely-useful-code-review

### Pattern 4: Deterministic-Tool-First Scoping (LLM Reviews What Linters Can't)

**Used by**: cubic (explicit design principle), CodeRabbit (runs 20+ linters/static analyzers before any LLM pass), Datadog (LLM filters static analysis output rather than generating findings from scratch)
**How it works**: The review prompt explicitly excludes concerns that a deterministic tool already covers better and cheaper — formatting, style, simple type errors, known lint rules — and instructs the LLM to focus attention on architecture, invariants, cross-file consistency, and risk categories that require judgment a linter structurally cannot apply. In CodeRabbit's pipeline this is literal: static analysis runs first inside an isolated microVM, and its output becomes part of the context the LLM review builds on rather than something the LLM re-derives.
**Strengths**: Removes the largest and lowest-value source of LLM findings (style nitpicks), which is also documented as the primary driver of the 80%-irrelevant / alert-fatigue dynamic (CodeAnt); lets the LLM's limited attention budget go to genuinely hard-to-automate judgment calls.
**Weaknesses**: Requires the review pipeline to actually have working linters/static analysis wired in as a precondition — a prompt-only fix without that infrastructure can't enforce this boundary; the LLM must be explicitly told what's "already covered" (one of Prompt Architects' six required context inputs) or it will re-flag lint-level issues anyway.
**Example**: https://www.cubic.dev/blog/the-false-positive-problem-why-most-ai-code-reviewers-fail-and-how-cubic-solved-it ; https://docs.coderabbit.ai/overview/architecture

### Pattern 5: Structured Reasoning Before Verdict (Semi-Formal Reasoning)

**Used by**: Meta (internal patch-equivalence judging research)
**How it works**: Rather than asking the model to jump straight to "is this correct / is this a bug," the prompt requires it to fill out an explicit intermediate structure first: state the premises (what must be true for the code to be correct), trace a concrete execution path through the code showing what actually happens, and only then derive a formal conclusion from that trace. This is a heavier-weight version of chain-of-thought that forces the reasoning to reference the actual code path rather than free-associate about the diff.
**Strengths**: Measured to jump accuracy on patch-equivalence judgment to 93% in Meta's internal evaluation, well above unstructured prompting; the intermediate trace is itself inspectable, giving a human reviewer something concrete to check disagree with, similar in spirit to the falsifier field in Pattern 2.
**Weaknesses**: Meta's reported gains are specific to patch-equivalence judgment, not general bug-finding — unclear how directly it generalizes; significantly increases prompt/output length and inference cost per finding, similar to the "detailed prompts increase false-positive bias" caveat found in the false-positive-reduction literature.
**Example**: https://venturebeat.com/orchestration/metas-new-structured-prompting-technique-makes-llms-significantly-better-at

## Anti-Patterns

- **Requiring explicit explanations/fixes inflates false positives.** Research on secure code review prompting found that increasing prompt complexity — specifically requiring the model to explain itself and propose a fix for every flagged issue — counterintuitively increases misjudgment rates, biasing the model toward "excessive fault finding" (flagging correct code as buggy) because it has to produce *something* to justify the elaborated output format. Source: search summary of arXiv literature on secure code review prompting (see "iCodeReviewer" search results, https://arxiv.org/pdf/2510.12186 and related).
- **Unstructured "here's some context" doesn't help; only structured, paired context does.** Cited in the Prompt Architects piece: "unstructured context on its own degraded performance. Gains only appeared when the context was processed and paired with structured reasoning" — dumping the whole repo or ticket text into the prompt is not equivalent to giving the model an intent statement, non-goals, and invariants in a structured form. Source: https://prompt-architects.com/blog/106-how-to-prompt-for-a-genuinely-useful-code-review
- **Alert fatigue silently degrades genuine findings, not just noise.** CodeAnt documents that reviewers apply a "probably nothing" mental filter to *all* AI comments once false-positive rates get high enough, meaning the cost of noisy findings isn't just wasted triage time on the bad ones — it's degraded attention on the good ones too. This means false-positive rate isn't a side metric; it's the primary lever controlling whether the tool's genuine catches even get read. Source: https://www.codeant.ai/blogs/ai-code-review-false-positives
- **Systematic overcorrection: LLMs are biased toward flagging correct code as non-conformant.** An arXiv study specifically documents this as a *systematic*, not occasional, bias when LLMs judge requirement conformance — worth designing prompts (severity caps, falsifier requirements) specifically to counteract, not just something to catch in spot-checks. Source: https://arxiv.org/pdf/2603.00539

## Emerging Trends

- **Adoption-rate / "outdated rate" as the real success metric**, replacing raw precision/recall. BitsAI-CR's "Outdated Rate" tracks whether developers actually acted on a finding, treating dismissed-but-technically-correct comments the same as false positives for practical purposes — because a comment nobody acts on has the same team-level cost either way. Source: https://arxiv.org/pdf/2501.15134
- **Trust calibration is emerging as its own design problem, separate from accuracy.** The 2026 participatory-design study (arxiv 2606.01969) and the field study at WirelessCar (arxiv 2505.16339) both independently name "helping the human know when to double-check vs. trust a given finding" as the dominant unsolved challenge — more central to adoption than raw detection accuracy. This is pushing tool design toward per-finding confidence/evidence output (Pattern 2) rather than a single aggregate accuracy number.
- **Agent-specific instruction files are becoming standard.** GitHub's November 2025 change letting `.instructions.md` files exclude themselves from either the coding agent or the review agent (`excludeAgent`) formalizes something the vendor landscape already converged on structurally: a generation prompt and a review prompt are different jobs and increasingly get separate instruction surfaces rather than one shared "house style" document. Source: https://github.blog/changelog/2025-11-12-copilot-code-review-and-coding-agent-now-support-agent-specific-instructions/
