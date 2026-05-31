# Technical Debt Report — Bank Statement Analyzer

**Original:** 2026-05-29 · **Updated:** 2026-05-30
**Reviewed by:** Claude (Cowork)
**Project:** Bank Statement Analyzer (Flask + React/TypeScript)

Severity scale: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low
Status: ✅ Resolved · ⚠️ Reopened · ⬜ Open

> Updated after the Sprint-01 fixes. IDs are preserved so cross-references (sprint plan, ADR) stay valid. **TD-001 is reopened** — it was marked done but the fix never landed on disk.

---

## Status snapshot

| Resolved ✅ | Still open ⬜ | Reopened ⚠️ |
|------------|--------------|-------------|
| TD-002, TD-003, TD-004, TD-005, TD-006, TD-009, TD-010, TD-011, TD-012, TD-013, TD-014, TD-015, TD-017 | TD-007, TD-008, TD-016, TD-018, TD-019, TD-020, TD-021 → TD-027 | **TD-001** |

13 resolved, 1 reopened, 13 open (6 carried + 7 new).

---

## Priority 1 — Fix Before Any Production Use

### TD-001 ⚠️ 🔴 `requirements.txt` is STILL UTF-16 encoded — REOPENED
**File:** `backend/requirements.txt`
**Status:** Marked resolved on 2026-05-29; **the fix never landed.** The file on disk is still UTF-16-LE — `hexdump` shows `46 00 6c 00 61 00 73 00` (null byte after every char). `pip install -r requirements.txt` fails on any clean environment, blocking onboarding, CI, and Docker.
**Likely cause:** re-saved via PowerShell `>` (writes UTF-16 by default) or an editor that kept the original encoding.
**Fix:** rewrite as UTF-8 without BOM from a normal shell:
```bash
printf '%s\n' "Flask==3.1.2" "flask-cors==6.0.1" "python-dotenv==1.2.1" \
  "pdfplumber==0.11.8" "pandas==2.3.3" "openpyxl==3.1.5" "requests==2.32.5" \
  > backend/requirements.txt
file backend/requirements.txt   # must print: ASCII text
```
**Add a regression guard:** CI step `file backend/requirements.txt | grep -q 'ASCII\|UTF-8'` or a pre-commit hook. This is the single most important open item.

---

## Resolved in Sprint 01 ✅ (kept for the record)

| ID | Sev | What it was | Verified fix |
|----|-----|-------------|--------------|
| TD-002 | 🔴 | `Config.INTEGRATION_URL/AUTH` undefined | Defined in `Config` with env defaults |
| TD-003 | 🔴 | No `.env.example` | `backend/.env.example` present |
| TD-004 | 🔴 | `debug=True` hardcoded | `run.py` reads `FLASK_DEBUG`, defaults false |
| TD-005 | 🔴 | Uploaded files never deleted | `finally` block removes file in controller |
| TD-006 | 🟠 | 4 dead classes in model | Removed; tracking comment left |
| TD-009 | 🟠 | `sklearn` imported, unused | Imports removed |
| TD-010 | 🟠 | Frontend API URL hardcoded | `api.ts` uses `VITE_API_URL` |
| TD-011 | 🟠 | No file size/MIME validation | Ext whitelist + `MAX_UPLOAD_SIZE` in controller |
| TD-012 | 🟡 | `print()` instead of logging | `logger.*` throughout |
| TD-013 | 🟡 | Double-assignment typo | Single assignment |
| TD-014 | 🟡 | Dead vars `txn_peer_map`, `verification_tasks` | Removed |
| TD-015 | 🟡 | `confidence_score` missing on PDF path | Scoring loop added |
| TD-017 | 🟡 | CORS default `*` | Defaults to `http://localhost:3000` |

> Note on TD-011: validation is by **file extension only** — bytes aren't checked. Hardening tracked as TD-023.

---

## Priority 2 — Fix Soon (carried open)

### TD-007 ⬜ 🟠 `BankStatementAnalyzer` is one ~1,280-line class
File-type routing, Excel/PDF parsing, date normalization, narration enrichment, metadata extraction and scoring all in one class. Hard to unit-test in isolation. Split into `parsers/`, `enrichers/`, `scorers/`, `analyzers/`. Best done as part of the FastAPI port.

### TD-008 ⬜ 🟠 Column-detection logic duplicated across Excel and PDF paths
Identical `find_column([...])` sequences and the credit/debit/amount → `(amount, type)` resolution appear in both processors. Extract `_detect_columns(df) -> ColumnMap` and `_resolve_amount(row, cols)`. Removes ~80 lines and a drift risk.

### TD-016 ⬜ 🟠 No automated tests (raised priority)
Zero pytest/Vitest. This is now the **highest-leverage** open item after TD-001 — it's a prerequisite for safely doing the FastAPI migration and the ML work, and it would have caught TD-001 regressing.
Starting points: unit-test `parse_amount`, `normalize_date`, `find_column`, `analyze_narration_details` with edge cases; one integration test hitting `/api/analyze/bank/statement` with a fixture CSV and a fixture PDF; snapshot/build test on the frontend.

---

## Priority 3 — Improve When Possible (carried open)

### TD-018 ⬜ 🟡 `TransactionTable` renders all rows at once
No pagination/virtualization. Add page controls or `@tanstack/react-virtual` before multi-statement/history features increase row counts.

### TD-019 ⬜ 🟢 No Dockerfile / docker-compose
Manual venv + npm setup. Add a backend `Dockerfile` and a `docker-compose.yml`. **Blocked by TD-001** — a Docker build will fail on the UTF-16 requirements file.

### TD-020 ⬜ 🟢 `.gitIgnore` capitalized
Still `.gitIgnore` (capital I). Not recognized by git on case-sensitive filesystems → `__pycache__`, `.pyc`, `venv/`, and possibly `.env` get tracked. Rename to `.gitignore`; confirm it ignores `**/__pycache__/`, `*.pyc`, `venv/`, `.env`. Low effort, real secret-leak risk.

---

## New debt found on 2026-05-30

### TD-021 ⬜ 🟠 Multi-page PDF tables drop continuation rows
`_process_pdf_transactions` treats `table[0]` as the header for every extracted table. When a transaction table continues onto the next page without repeating its header, that page's first data row is consumed as headers and the whole table is then skipped — silent data loss with no error surfaced. Carry the last good header forward, or stitch rows across pages via coordinate-based extraction. (See code-review CR-C-01.) Directly affects the PDF-compatibility goal.

### TD-022 ⬜ 🟠 Dead `verify_bank_account_with_pennyless` ships hardcoded identity data
Never called, but still present with `name="stco"`, `mobile="9999999999"`. Delete until the integration is real, or gate behind a flag and source the values from the request. (code-review CR-S-02.)

### TD-023 ⬜ 🟡 Upload validation trusts the extension, not the bytes
A non-PDF renamed to `.pdf` passes the gate. Low blast radius (parsers fail safely) but verify magic bytes (`%PDF`, `PK\x03\x04`) for defense in depth. (code-review CR-S-03.)

### TD-024 ⬜ 🟡 No transaction de-duplication
Overlapping/ repeated table extraction can inject duplicate transactions, skewing totals and `merchant_insights`. Dedupe on `(date, amount, narration, balance)` before scoring. (code-review CR-C-05.)

### TD-025 ⬜ 🟡 `transaction_reference` fallback regex grabs any 10+ digit run
Can capture beneficiary account or mobile numbers instead of the real reference. Require a labeled prefix (RRN/UTR/REF/TXN) or prefer UTR-shaped 12/16-digit candidates. (code-review CR-C-02.)

### TD-026 ⬜ 🟡 Confidence score penalizes balance-less formats systematically
The unconditional `-0.05` for missing `balance` drags down every transaction from formats that legitimately lack a running balance (many credit-card/CSV exports). Make the penalty conditional on whether the format carries balances at all. (code-review CR-C-04.)

### TD-027 ⬜ 🟡 No `GET /api/health` endpoint
Blocks container/orchestrator/uptime monitoring. 3-line add in the current Flask app; also an action item in the FastAPI ADR. Do it now rather than waiting for the migration. (code-review CR-M-01.)

---

## Updated Summary Table

| ID | Status | Sev | Area | Description |
|----|--------|-----|------|-------------|
| TD-001 | ⚠️ Reopened | 🔴 | Backend | requirements.txt still UTF-16 — pip install fails |
| TD-002 | ✅ | 🔴 | Backend | Config integration vars defined |
| TD-003 | ✅ | 🔴 | Backend | .env.example added |
| TD-004 | ✅ | 🔴 | Backend | debug env-controlled |
| TD-005 | ✅ | 🔴 | Backend | uploaded files cleaned up |
| TD-006 | ✅ | 🟠 | Backend | dead classes removed |
| TD-007 | ⬜ | 🟠 | Backend | monolithic 1,280-line model |
| TD-008 | ⬜ | 🟠 | Backend | column detection duplicated |
| TD-009 | ✅ | 🟠 | Backend | sklearn imports removed |
| TD-010 | ✅ | 🟠 | Frontend | API URL via env var |
| TD-011 | ✅ | 🟠 | Backend | file size/ext validation (ext-only) |
| TD-012 | ✅ | 🟡 | Backend | logging replaces print |
| TD-013 | ✅ | 🟡 | Backend | double assignment fixed |
| TD-014 | ✅ | 🟡 | Backend | dead vars removed |
| TD-015 | ✅ | 🟡 | Backend | PDF confidence_score added |
| TD-016 | ⬜ | 🟠 | Testing | zero test coverage (raised) |
| TD-017 | ✅ | 🟡 | Backend | CORS default tightened |
| TD-018 | ⬜ | 🟡 | Frontend | table renders all rows |
| TD-019 | ⬜ | 🟢 | Infra | no Docker (blocked by TD-001) |
| TD-020 | ⬜ | 🟢 | Repo | .gitIgnore capitalized |
| TD-021 | ⬜ | 🟠 | Backend | multi-page PDF rows dropped |
| TD-022 | ⬜ | 🟠 | Backend | dead Pennyless fn + hardcoded identity |
| TD-023 | ⬜ | 🟡 | Backend | validation trusts extension not bytes |
| TD-024 | ⬜ | 🟡 | Backend | no transaction dedupe |
| TD-025 | ⬜ | 🟡 | Backend | txn_reference regex over-greedy |
| TD-026 | ⬜ | 🟡 | Backend | confidence penalizes balance-less formats |
| TD-027 | ⬜ | 🟡 | Backend | no /api/health endpoint |

---

## Recommended next-sprint slice (low effort, high value)

1. TD-001 (re-encode + CI guard) — unblocks everything
2. TD-020 (`.gitignore` rename) — secret-leak prevention, 1 command
3. TD-027 (`/api/health`) — unblocks monitoring, 3 lines
4. TD-022 (delete dead Pennyless fn) — removes hardcoded data
5. TD-016 (stand up pytest) — before the FastAPI port, not after
6. TD-021 (multi-page PDF stitching) — real data-loss bug on the PDF goal

---

*Line-level findings in `code-review.md`. Forward-looking feature analysis in `improvement-analysis.md`.*
