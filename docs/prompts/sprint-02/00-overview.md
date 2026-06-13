# Sprint-02 Prompt Files — Overview

These files contain structured prompts for Claude Code to implement Sprint-02 tasks.

**How to use:**
1. Open a Claude Code session in the project root
2. Say: "Read `CLAUDE.md` first, then read `docs/prompts/sprint-02/<file>.md` and implement the task exactly as described."
3. Claude Code will read the context files listed in each prompt before making any changes.
4. Review each patch before Claude Code moves to the next file.

**Order of execution — follow this sequence:**

| Step | File | Task | Est. |
|------|------|------|------|
| 1 | `01-fastapi-housekeeping.md` | Fix TD-028, 029, 030, 032 | 30 min |
| 2 | `02-fastapi-tests.md` | FastAPI integration tests (BSA-10) | 3-4h |
| 3 | `03-flask-cutover.md` | Point frontend at FastAPI, retire Flask (BSA-09) | 1h |
| 4 | `04-llm-categorization.md` | Claude Haiku fallback for null categories (BSA-04) | 2-3h |
| 5 | `05-financial-summary.md` | Financial summary endpoint (BSA-05) | 1.5h |
| 6 | `06-multipage-pdf.md` | Multi-page PDF row stitching (TD-021) | 3h |

Steps 1-3 must be done in order. Steps 4-6 can be done independently after step 3.

**Dev process reminder:**
- Read before writing — always read the context files listed in each prompt
- Small patches — one logical change per edit, explain each before applying
- Never `git commit` or `git push` — generate commit message text and hand it over
- After implementing: update `docs/changelog.md` with what changed and why
