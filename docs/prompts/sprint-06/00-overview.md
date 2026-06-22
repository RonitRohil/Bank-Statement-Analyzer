# Sprint-06 Overview — Claude Code Context

**Sprint goal:** Natural-language Q&A over transaction history, statement history UI, and category-correction learning loop.

**Run prompts in this order:**

1. `01-housekeeping.md` — CR-S5-01/04/05 quick fixes (first commit, ~30 min)
2. `02-nl-qa.md` — BSA-06 NL Q&A service + endpoint + frontend chat widget
3. `03-history-ui.md` — BSA-20 DELETE endpoint + HistoryPanel.tsx
4. `04-corrections.md` — BSA-16 category-correction POST endpoint + re-parse override + frontend button
5. `05-virtualization.md` — TD-018 client-side pagination for TransactionTable (P1, if capacity allows)
6. `06-magic-bytes.md` — TD-023 magic-byte upload validation (P1, if capacity allows)

Each prompt is self-contained. Read it fully before starting. Read every file listed in "Files to read first" before writing any code.

---

## Architecture at Sprint-06 Start

```
backend/app/
  main.py              ← FastAPI app, CORS, lifespan (DB startup), router registration
  config/settings.py   ← pydantic-settings; ollama_base_url, ollama_model, database_url
  db/
    models.py          ← StatementDB, TransactionDB, CorrectionDB (SQLModel)
    database.py        ← engine, get_session, create_db_and_tables
    crud.py            ← hash_file, find/save statement, get_monthly_summary, get_cross_statement_recurring
  models/
    analyzer.py        ← BankStatementAnalyzer (thin orchestrator, 299 lines) + TransactionPatternTrainer
    schemas.py         ← all Pydantic v2 schemas
  parsers/
    excel_parser.py    ← process_excel_csv, parse_amount, normalize_date, find_column, deduplicate_transactions
    pdf_parser.py      ← process_pdf_transactions, looks_like_header
  enrichers/
    narration_enricher.py  ← analyze_narration_details
  scorers/
    confidence_scorer.py   ← calculate_confidence_score
  services/
    categories.py      ← CANONICAL_CATEGORIES, REGEX_TO_CANONICAL
    insights.py        ← generate_insights, detect_recurring
    llm_enricher.py    ← enrich_with_llm (Ollama, bounded with Semaphore + wait_for)
  routers/
    analyze.py         ← POST /api/analyze/bank/statement (persist=true optional)
    export.py          ← POST /api/export/transactions (CSV/XLSX StreamingResponse)
    health.py          ← GET /api/health
    statements.py      ← GET /api/statements, GET /api/statements/compare, GET /api/statements/recurring, GET /api/statements/{id}/transactions
    summary.py         ← POST /api/analyze/bank/summary

frontend/
  App.tsx              ← root component; all state; orchestrates layout
  types.ts             ← TypeScript interfaces
  services/api.ts      ← uploadBankStatement, exportTransactions, compareStatements, getConfirmedRecurring, getSummary
  components/
    FileUpload.tsx, AccountOverview.tsx, AnalyticsCharts.tsx
    MerchantInsights.tsx, TransactionTable.tsx, InsightsStrip.tsx
    SpendingSummary.tsx, MonthlyComparison.tsx, SubscriptionsCard.tsx
```

**Test suite:** 46 tests, all in `backend/tests/`. Run with `pytest` from `backend/` (activate venv first).

**Key patterns to follow:**

- All new backend services go in `backend/app/services/`
- All new routers go in `backend/app/routers/` and must be registered in `main.py`
- All new Pydantic schemas go in `backend/app/models/schemas.py`
- All new CRUD functions go in `backend/app/db/crud.py`
- Every new router gets at least 3 tests in `backend/tests/`
- Changelog entry mandatory for every shipped item
- Study doc mandatory at sprint close
