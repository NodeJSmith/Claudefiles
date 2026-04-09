# Findings Anti-Pattern Catalog

## Anti-Patterns (CRITICAL)

These are failure modes that recur across skill implementations. Each is named so it can be cited. Do not repeat any of them.

1. **Bundling N findings into one `Accept all?` AskUserQuestion** — Do not bundle multiple findings into a single AskUserQuestion. Emit one AskUserQuestion per `ask` row during manifest execution, with `(N/M)` position in the header.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "I found 9 findings. How would you like to handle them?"
     options:
       - label: "Yes — accept all recommendations"
       - label: "No — I want to discuss some"
   ```
   **Instead:** Write the manifest, present the Consent Gate, open the editor. The user sets verbs in the editor, not in one bundled AskUserQuestion.

2. **Multi-select as verb selector** — Do not use `multiSelect: true` to mean "fix some, file others." Multi-select is for "which items match this single decision," not "which verb applies to which item." Verbs belong to the manifest's Verb column.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "Which findings should be filed as issues?"
     multiSelect: true
     options:
       - label: "F1: Missing timeout"
       - label: "F3: No retry logic"
   ```
   **Instead:** The user sets `file` in the Verb column of each finding's manifest section. No AskUserQuestion needed for this decision.

3. **Double-gate after 'Yes'** — Do not re-prompt "Which findings?" after the commit gate. The commit gate's contract is "execute the manifest as written."

   **Looks like this:**
   ```
   # User clicks "Yes" at commit gate
   AskUserQuestion:
     question: "Which issues should I address first?"
     options:
       - label: "CRITICAL findings first"
       - label: "Quick wins first"
   ```
   **Instead:** After "Yes" at the commit gate, iterate the manifest in order. No additional triage gates.

4. **Meta-gates with relabeled Proceed Gate** — Do not rename the consent/commit gates and re-implement their logic under new labels.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "How would you like to handle these findings?"
     options:
       - label: "Full review — go through each finding"
       - label: "Auto-accept — apply all recommendations"
       - label: "Skip revisions — continue without changes"
   ```
   **Instead:** Use the Consent Gate (before editor) and Commit Gate (after editor) exactly as defined. No additional meta-gates.

5. **Option labels showing actions instead of findings** — In execution-phase `ask` prompts, labels describe the finding's alternative fixes, not generic verbs.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "How should I handle F3?"
     options:
       - label: "Fix it"
       - label: "File it"
       - label: "Skip it"
   ```
   **Instead:** Labels are the finding's actual option text: "Add exponential backoff (Option A)", "Use circuit breaker pattern (Option B)", "File as issue", "Skip".

6. **Auto-apply mixed with judgment calls in one prompt** — Auto-apply findings MUST execute silently during manifest iteration. They do not appear as options in `ask` prompts.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "Ready to fix these findings?"
     options:
       - label: "Fix F1 (auto) and decide on F2, F3"
       - label: "Review each one manually"
   ```
   **Instead:** `fix` verbs execute silently. `ask` verbs emit their own individual AskUserQuestion. They do not share a prompt.

7. **Permissive defaults that collapse to 'accept all'** — Default verbs must reflect the finding's actual classification. User-directed findings without a clear recommendation default to `ask`, not `fix`.

   **Looks like this:**
   ```
   # Manifest generated with all verbs defaulted to "fix" regardless of finding type
   **Verb:** fix  ← (applied to a finding with no recommendation field and two valid options)
   ```
   **Instead:** Follow the Default Verb Selection table. `User-directed` + no recommendation → `ask`. `Auto-apply` only → `fix`.

8. **Bail-out options violating 'all findings must be resolved'** — Do not offer `Skip revisions` / `Enough — approve as-is` options at any gate. Explicit deferral is valid, but it must be recorded per finding via `defer` or `skip` verbs in the manifest.

   **Looks like this:**
   ```
   AskUserQuestion:
     question: "What would you like to do with these findings?"
     options:
       - label: "Fix issues now"
       - label: "Skip revisions"
       - label: "Enough challenges — approve as-is"
   ```
   **Instead:** Every finding must be resolved. Use `defer` or `skip` verbs in the manifest for findings the user wants to punt. Do not offer session-level bail-outs.
