# Development Process — Bank Statement Analyzer

**Established:** 2026-05-29  
**Owner:** Ronit Jain  

This document defines how all development on this project is done. Every contributor (human or AI) follows this process.

---

## The Two-Layer AI Workflow

```
┌─────────────────────────────────────────────────────┐
│  COWORK CLAUDE (planning layer)                      │
│                                                      │
│  - Reads codebase and docs                           │
│  - Writes prompts for Claude Code                    │
│  - Makes architecture decisions                      │
│  - Writes study docs + changelog entries             │
│  - Updates requirements.md on scope changes          │
│  - Plans sprints                                     │
└─────────────────────┬───────────────────────────────┘
                      │ generates prompts
                      ▼
┌─────────────────────────────────────────────────────┐
│  CLAUDE CODE (implementation layer)                  │
│                                                      │
│  - Reads files before editing                        │
│  - Makes changes in small, explained patches         │
│  - Follows existing code style                       │
│  - Never silently deletes code                       │
│  - Verifies changes work after applying              │
└─────────────────────────────────────────────────────┘
```

---

## Prompt Template (Cowork → Claude Code)

Every implementation prompt uses this structure. Do not skip sections.

```markdown
## Task: [Short imperative title — e.g., "Add file size validation to analyzeController"]

**Sprint / ADR reference:** [e.g., Sprint 01, BSA-02 | ADR-001]

**Why this change:**
[One paragraph explaining the problem this solves. Link to tech-debt item or ADR if relevant.]

**Read these files first:**
- `path/to/file1.py` — [what to understand from it]
- `path/to/file2.py` — [what to understand from it]

**Exact change to make:**
[Precise description. Not "improve validation" but "in analyzeController.py, after line 23 where the file is saved, add a check that raises a 400 if the file extension is not in {.pdf, .csv, .xlsx, .xls}"]

**Constraints:**
- Do NOT rewrite the whole function — only add the validation block
- Match the existing return style: `return jsonify({...}), 400`
- Do not add new imports unless necessary

**How to verify:**
[Exact test command or manual check — e.g., "curl -X POST ... with a .txt file should return 400 with message 'Unsupported file type'"]

**Doc update required:**
- Add entry to `docs/changelog.md` under [date]
- [Any other doc to update]
```

---

## Change Process (step by step)

```
1. Cowork writes prompt using the template above
2. Claude Code reads all listed files
3. Claude Code explains the proposed change in plain English before making it
4. Claude Code applies the change as a small, focused patch
5. Claude Code verifies the change
6. Claude Code updates changelog.md with the change
7. If the change is a new feature → Claude Code creates docs/study/[feature].md
8. Cowork reviews; if satisfied, sprint item is marked done
```

---

## Patch Size Guidelines

| Change type | Acceptable patch size |
|-------------|----------------------|
| Bug fix | 1–10 lines changed |
| New validation | 5–20 lines added |
| New endpoint | New file + small edits to routes |
| Refactor | One method or one class at a time |
| New feature | Split into multiple prompts if >50 lines |

**Rule of thumb:** If you can't describe the patch in one sentence, it's too big. Split it.

---

## Study Document Template

After every sprint or significant feature, create `docs/study/[name].md`:

```markdown
# Study: [Feature / Sprint Name]

**Date:** YYYY-MM-DD  
**Sprint:** Sprint N  
**Author:** Claude (Cowork + Code)

---

## 1. What was built

[Plain language description — what the feature does, what the user sees]

## 2. Why it was built

[The problem it solves. Link to requirement or tech-debt item.]

## 3. How it works (code walkthrough)

### Step 1: [Entry point]
[File + function name + what happens here]

### Step 2: [Next step]
...

## 4. Key decisions

| Decision | Alternatives considered | Why this choice |
|----------|------------------------|-----------------|
| [decision] | [what else was possible] | [reasoning] |

## 5. Gotchas and edge cases

- [Thing that might surprise you when reading this code]
- [Edge case that's handled non-obviously]

## 6. What's next

- [ ] [Follow-up work item]
```

---

## Documentation Folder Map

```
docs/
  architecture.md        ← System overview — update when architecture changes
  system-design.md       ← Design recommendations — update when design evolves
  tech-debt.md           ← Backlog — mark ✅ done as items ship
  code-review.md         ← Code review findings — archive old items as resolved
  requirements.md        ← Living requirements — update on every scope change
  changelog.md           ← Running change log — entry for EVERY change
  dev-process.md         ← This file
  adr-XXX-*.md           ← Architecture Decision Records — one per decision
  ml-ai-brainstorm.md    ← ML/AI roadmap — update as features are spec'd
  sprint-NN-plan.md      ← Sprint plans — one per sprint
  study/
    sprint-01-learnings.md
    [feature-name].md
    ...
```

---

## Git Rules

**Never run `git commit`, `git push`, or any git write command.**  
Always generate the commit message and hand it to the developer to commit and push manually.

---

## Commit Message Convention

```
[type]: short description

type: feat | fix | refactor | docs | test | chore | security
```

Examples:
```
feat: add LLM categorization fallback for null-category narrations
fix: delete uploaded file after analysis to prevent disk accumulation
security: enforce 20MB file size limit and extension whitelist
docs: add study doc for FastAPI migration
refactor: replace print() with logging module throughout analyzeModel
```

---

## What Never Gets Done Without a Prompt

Claude Code should **never** make changes without a structured prompt from Cowork. This includes:
- "Improvement" suggestions it decides on its own
- Refactoring files that weren't asked about
- Changing behavior silently

If Claude Code notices something worth fixing during an implementation, it **flags it as a suggestion** — it does not fix it without a prompt.

---

## Decision Log Protocol

Any time a decision is made — about requirements, architecture, tools, or approach — log it in `changelog.md` immediately:

```markdown
## [Date] — [Short title]
**Type:** Requirement change | Architecture decision | Design decision | Process change
**Decision:** [What was decided]
**Reason:** [Why — the specific constraint, insight, or tradeoff that drove it]
**Impact:** [What changes as a result — files, behavior, next steps]
**Alternatives rejected:** [What else was considered and why it was ruled out]
```

This creates an audit trail so that future developers (and future AI agents) can understand not just what was built, but why every choice was made.
