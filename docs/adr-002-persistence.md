# ADR-002: Persistence Layer

**Status:** Accepted  
**Date:** 2026-06-20  
**Deciders:** Ronit Jain  
**Context project:** Bank Statement Analyzer  
**Implementation ticket:** BSA-19 (Sprint-04)

---

## Context

The backend is fully stateless. Every upload is parsed from scratch and nothing is retained across requests. This design was intentional in early sprints — it kept the system simple while the core parser was being built and stabilized.

The consequence is that almost every high-value future feature is blocked:

| Feature                                  | Ticket | Why it needs storage                                        |
| ---------------------------------------- | ------ | ----------------------------------------------------------- |
| Month-over-month spending comparison     | BSA-17 | Must know prior months                                      |
| True cross-statement recurring detection | BSA-07 | Single-statement is weak signal; confidence requires months |
| Natural-language Q&A over history        | BSA-06 | Must query a stored corpus of transactions                  |
| Category-correction learning loop        | BSA-16 | User corrections must survive across sessions               |
| Statement deduplication                  | TD-024 | Requires knowing which files were already processed         |

These features represent the longitudinal roadmap — the difference between a one-shot parser and a financial picture. They all share a single prerequisite: somewhere to store data between uploads.

**Current constraints:**

- Single-user personal project. There is no authentication layer and no multi-tenancy requirement today.
- Maintained on evenings and weekends. Infrastructure overhead is a real cost.
- "Multi-user someday" is imaginable but has no concrete requirement, no committed timeline, and no second user.
- FastAPI (Pydantic v2) is already the backend framework. The ORM should integrate naturally.
- No cloud deployment yet. The backend runs on a developer's local machine.

---

## Options Considered

### Option 1: SQLite via SQLModel

SQLite is an embedded relational database — a single file on disk, no separate server process. SQLModel is the ORM written by FastAPI's author (Sebastián Ramírez); it is a thin layer over SQLAlchemy that reuses Pydantic models directly.

| Dimension                  | Assessment                                                                                      |
| -------------------------- | ----------------------------------------------------------------------------------------------- |
| Infrastructure             | ✅ Zero — no server, no Docker, one `.db` file                                                  |
| FastAPI integration        | ✅ Native — SQLModel shares Pydantic's model syntax                                             |
| Pydantic reuse             | ✅ `Transaction`, `AccountInfo` schemas map almost directly to table models                     |
| Concurrency                | 🟡 WAL mode handles multiple readers; single-writer limit only matters under concurrent uploads |
| Scale                      | ✅ Sufficient — SQLite handles millions of rows comfortably for one user                        |
| Backup                     | ✅ `cp statements.db statements.db.bak` is the backup story                                     |
| Migration path to Postgres | ✅ SQLAlchemy underneath; swap the connection string and engine, keep the models                |
| Learning curve             | Low — SQLModel is close to Pydantic                                                             |

**Cons:**

- Not suitable for true multi-user concurrency (write lock contention under load).
- No network access — the DB lives on the same machine as the backend (fine for local development, needs revisiting for cloud deployment).
- Migration story (Alembic) must be added once the schema needs changes.

---

### Option 2: PostgreSQL

A production-grade relational database. Handles real concurrency, runs as a separate process, supports network clients.

| Dimension           | Assessment                                                                       |
| ------------------- | -------------------------------------------------------------------------------- |
| Infrastructure      | ❌ Requires a running server (local install or Docker)                           |
| FastAPI integration | ✅ Well-supported via SQLAlchemy / asyncpg                                       |
| Concurrency         | ✅ MVCC — multiple simultaneous writers, no lock contention                      |
| Scale               | ✅ Production-grade                                                              |
| Operational cost    | ❌ High for a personal project — process management, backups, connection pooling |
| Backup              | 🟡 `pg_dump` works; needs automation                                             |

**Assessment:** PostgreSQL is the right answer for a multi-user application. For a single-user personal project it is infrastructure-for-users-who-don't-exist. The complexity is a maintenance tax with no current payoff.

---

### Option 3: File-based JSON keyed by statement hash

Store each statement's analysis as a JSON file on disk, keyed by the SHA-256 of the uploaded file. No ORM, no SQL, no dependencies.

| Dimension             | Assessment                                                                                                                |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Infrastructure        | ✅ Zero — just the filesystem                                                                                             |
| Simplicity            | ✅ Dead simple to implement                                                                                               |
| Querying              | ❌ No relational queries — "how much did I spend on food last quarter?" requires loading all files and reducing in Python |
| Cross-statement joins | ❌ No relations — month-over-month comparison is painful to implement correctly                                           |
| Dedup                 | ✅ The hash key naturally deduplicates                                                                                    |
| Data integrity        | ❌ No schema enforcement; JSON format can drift silently                                                                  |

**Assessment:** Sufficient for a cache layer or a "don't reprocess the same file" optimization, but it cannot support relational queries or the correction-learning loop. It does not scale to the features that justify adding persistence in the first place.

---

## Decision

**SQLite via SQLModel.**

### Reasoning

The only user who exists today is one person running this on a local machine. For that user, SQLite's constraints (single writer, local-only, no server) are not constraints at all — they are advantages. Zero infrastructure cost, one file to back up, and the ORM (SQLModel) is built by the same author as FastAPI and shares Pydantic's model syntax. The `Transaction` and `AccountInfo` Pydantic models already in `app/models/schemas.py` map directly to SQLModel table models with minimal changes.

PostgreSQL is the right call if a second user ever appears. The migration path is: swap the SQLAlchemy engine URL from `sqlite:///...` to `postgresql+asyncpg://...` and run `alembic upgrade head`. The model definitions do not change.

File-based JSON is not chosen because it cannot support the relational queries that justify adding persistence at all.

---

## Data Model

Three tables. The model is deliberately minimal — it covers the confirmed features (BSA-06/07/16/17, TD-024) and nothing else.

### `statements`

One row per uploaded file. The `file_hash` column is the deduplication key (TD-024): before parsing, compute SHA-256 of the uploaded bytes. If a matching hash already exists, skip re-parsing and return the stored result.

| Column               | Type                 | Notes                                               |
| -------------------- | -------------------- | --------------------------------------------------- |
| `id`                 | INTEGER PK           | Auto-increment                                      |
| `file_hash`          | TEXT UNIQUE NOT NULL | SHA-256 of uploaded file bytes — dedup key (TD-024) |
| `original_filename`  | TEXT                 | Original name from the upload request               |
| `account_number`     | TEXT                 | From `AccountInfo.account_number`                   |
| `bank_name`          | TEXT                 | From `AccountInfo.bank_name`                        |
| `account_holder`     | TEXT                 | From `AccountInfo.account_holder`                   |
| `period_from`        | TEXT                 | ISO date — `AccountInfo.statement_period.from`      |
| `period_to`          | TEXT                 | ISO date — `AccountInfo.statement_period.to`        |
| `uploaded_at`        | DATETIME             | UTC timestamp of upload                             |
| `confidence_overall` | FLOAT                | `AnalysisResult.confidence_summary.overall_score`   |

### `transactions`

One row per transaction. Foreign key to `statements`. This is the queryable corpus for BSA-06 (Q&A), BSA-07 (recurring), and BSA-17 (month-over-month).

| Column                  | Type                         | Notes                                              |
| ----------------------- | ---------------------------- | -------------------------------------------------- |
| `id`                    | INTEGER PK                   | Auto-increment                                     |
| `statement_id`          | INTEGER FK → `statements.id` | Cascades on delete                                 |
| `transaction_date`      | TEXT                         | ISO date                                           |
| `amount`                | FLOAT                        |                                                    |
| `transaction_type`      | TEXT                         | `CREDIT` or `DEBIT`                                |
| `narration`             | TEXT                         | Raw narration string                               |
| `balance`               | FLOAT                        | Running balance (nullable)                         |
| `payment_method`        | TEXT                         | UPI, IMPS, NEFT, etc.                              |
| `merchant`              | TEXT                         | Normalized merchant name (nullable)                |
| `category`              | TEXT                         | JSON-encoded list — `["FOOD_DELIVERY"]` (nullable) |
| `payment_gateway`       | TEXT                         | PAYTM, PHONEPE, etc. (nullable)                    |
| `transaction_reference` | TEXT                         | RRN/UTR/TXN ref (nullable)                         |
| `confidence_score`      | FLOAT                        | Per-transaction confidence score                   |
| `llm_enriched`          | BOOLEAN                      | True if category came from LLM enrichment          |

_Note: `category` is stored as a JSON-encoded list rather than a separate junction table to keep the model simple. If querying by category becomes frequent, this can be normalized in a later migration._

### `corrections`

One row per user-submitted correction. The `fingerprint` is a deterministic hash of `(date, amount, narration)` — it identifies the logical transaction across re-uploads without requiring a foreign key to a specific `transactions.id`. This feeds the BSA-16 category-correction learning loop: when enriching future transactions, check corrections first.

| Column               | Type                 | Notes                                                |
| -------------------- | -------------------- | ---------------------------------------------------- |
| `id`                 | INTEGER PK           | Auto-increment                                       |
| `fingerprint`        | TEXT UNIQUE NOT NULL | SHA-256 of `(transaction_date + amount + narration)` |
| `corrected_category` | TEXT                 | The user-supplied correct category                   |
| `corrected_merchant` | TEXT                 | The user-supplied merchant name (nullable)           |
| `created_at`         | DATETIME             | UTC timestamp                                        |

---

## Notes on Security and Privacy

This schema stores real financial data on disk — account numbers, transaction amounts, merchant names, narrations that may contain names and UPI IDs.

**PII at rest is an open question for the implementation prompt (BSA-19).** At minimum, the implementation should consider:

- Encrypting the SQLite file at rest (SQLCipher, or full-disk encryption at the OS level).
- A data-retention policy — automatic deletion of statements older than N months.
- Whether `account_holder`, `account_number`, and narrations should be stored verbatim or masked.

This ADR records the decision not to mandate a specific encryption scheme at design time. BSA-19 must revisit this before writing the first `INSERT`.

---

## Consequences

**What becomes possible (directly unlocked):**

- BSA-17 — month-over-month comparison: query `transactions` grouped by `statement_id` and month.
- BSA-07 — true recurring detection: look for same merchant + similar amount across multiple `statement_id` values.
- BSA-06 — natural-language Q&A: the transaction corpus is now queryable.
- BSA-16 — category-correction learning: `corrections` table stores user feedback; enrichment checks it before calling LLM.
- TD-024 — statement deduplication: `file_hash` on `statements` prevents double-processing.

**What changes in the existing flow:**

- `POST /api/analyze/bank/statement` gains an optional `persist=true` query parameter (or a config toggle). When enabled, it writes to `statements` + `transactions` after a successful parse. When disabled (default), behaviour is identical to today — **the stateless path still works**. Storage is additive, not required.
- A dedup check runs before parsing when persistence is active: if `file_hash` already exists in `statements`, return the stored result immediately.

**New obligations introduced:**

- **Migration story:** Schema changes require Alembic migrations. The first `alembic init` is part of BSA-19.
- **Backup story:** The `.db` file must be included in any backup strategy. Document the backup command in `CLAUDE.md`.
- **Data-retention / privacy obligation:** Real financial data on disk. BSA-19 must decide on encryption and retention before the first write.
- **Postgres migration path:** If multi-user is ever required, the migration is: new Postgres connection string, `alembic upgrade head`, data migration script. SQLModel models are unchanged. Document this in BSA-19.

---

## Action Items

- [x] BSA-19 (Sprint-04): Implement SQLite store — `sqlmodel` dependency, `statements`/`transactions`/`corrections` table models, `alembic init`, dedup check in `analyze.py`, optional `persist` toggle, encryption-at-rest decision. **Done 2026-06-21.**
- [x] BSA-19: Write Alembic migration for the initial schema. **Done — revision `9670b8f28c89`.**
- [x] BSA-19: Add pytest fixtures for DB state (in-memory SQLite for tests). **Done — `tests/test_persistence.py`, 6 tests.**
- [x] BSA-19: Document backup command and retention policy in `CLAUDE.md`. **Done.**

---

## Footnote — Encryption at Rest (BSA-19 decision, 2026-06-21)

`statements.db` is stored as a plain SQLite file with no encryption. It contains real financial data: account numbers, transaction amounts, merchant names, narrations that may include names and UPI IDs.

**Decision for Sprint-04:** No encryption at the application layer. Rationale: this is a single-user project running on a developer's local machine; OS-level full-disk encryption (BitLocker / FileVault) is the appropriate control, and it is already available. Adding SQLCipher or application-layer encryption would add complexity with no net security gain for a local deployment.

**What MUST change before networked/multi-user deployment:**

- Evaluate SQLCipher (encrypted SQLite) or migrate to PostgreSQL with encrypted storage.
- Apply a data-retention policy: auto-delete statements older than N months.
- Decide whether `account_number` and narrations should be stored verbatim or masked/hashed.
- Revisit as part of the auth + multi-user planning session (BSA-17 dependency).

---

_Related: `docs/feature-brainstorm.md` §Tier 3 · `docs/improvement-analysis.md` · `docs/sprint-03-plan.md` ADR-002 entry · Implementation: BSA-19 (Sprint-04)_
