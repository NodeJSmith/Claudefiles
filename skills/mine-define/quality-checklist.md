# Design Document Quality Checklist

Validate the design doc against this checklist. For any item that fails: **FAIL** — block and revise before proceeding. Report results as a compact list.

1. Requirements sections describe observable behaviors — domain terms are fine; implementation steps (specific libraries, internal APIs, database operations) are a FAIL
2. All requirements are testable and unambiguous
3. Success criteria are measurable and framed as outcomes, not implementation
4. No `[NEEDS CLARIFICATION]` markers remain
5. Edge cases are identified (at least one)
6. Scope is clearly bounded
7. Acceptance scenarios are defined
8. Dependencies and assumptions are identified
9. All mandatory sections are completed (none empty)
10. User scenarios cover the primary flow with named actors and step-by-step task flows (for moderate+ features)
11. Functional requirements have clear acceptance criteria
12. Requirements sections describe what the system does from the outside — a developer unfamiliar with the codebase can understand the requirement without reading the implementation
13. All Functional Requirements have unique `FR#N` identifiers matching the format `FR#<positive integer>` — duplicate or missing identifiers are a FAIL
14. All Acceptance Criteria have unique `AC#N` identifiers matching the format `AC#<positive integer>` — duplicate or missing identifiers are a FAIL
15. Each Functional Requirement describes exactly one testable behavior — compound requirements bundling multiple behaviors into a single FR are a FAIL
16. Section presence and content rules match the template annotations (re-read them and verify each): Key Constraints, Visual Artifacts, Replacement Targets, and Migration follow the include/omit conditions stated in the template — a section present when it should be omitted (or omitted when required) is a FAIL
17. Test Strategy identifies existing tests to adapt (with file paths), new coverage needed (mapped to FR#N), and tests to remove — or states N/A for repos with no test infrastructure
18. Documentation Updates lists specific artifacts with specific changes needed, or explicitly states none are required — a vague "update docs" without naming artifacts is a FAIL
19. Implementation Preferences contains only decisions explicitly surfaced during discovery — speculatively filled entries (not traceable to a user answer or codebase finding) are a FAIL. Section states "No specific implementation preferences — follow codebase conventions." when none were identified
20. Every Acceptance Criterion is verifiable by running a local command (test, lint, grep, script, or hitting a locally-reachable service). Criteria requiring CI pipeline status, GitHub Actions output, post-merge observation, or PR review state are a FAIL (move to Dependencies and Assumptions)
