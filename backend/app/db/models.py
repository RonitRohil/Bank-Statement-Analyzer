from datetime import datetime, UTC
from typing import Optional
from sqlmodel import SQLModel, Field


class StatementDB(SQLModel, table=True):
    __tablename__ = "statements"
    id: Optional[int] = Field(default=None, primary_key=True)
    file_hash: str = Field(unique=True, index=True)  # SHA-256 of file bytes — dedup key
    original_filename: str
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    period_from: Optional[str] = None  # ISO date
    period_to: Optional[str] = None  # ISO date
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence_overall: Optional[float] = None


class TransactionDB(SQLModel, table=True):
    __tablename__ = "transactions"
    id: Optional[int] = Field(default=None, primary_key=True)
    statement_id: int = Field(foreign_key="statements.id")
    transaction_date: Optional[str] = None
    amount: Optional[float] = None
    transaction_type: Optional[str] = None
    narration: Optional[str] = None
    balance: Optional[float] = None
    payment_method: Optional[str] = None
    merchant: Optional[str] = None
    category: Optional[str] = None  # JSON-encoded list: '["Food & Dining"]'
    payment_gateway: Optional[str] = None
    transaction_reference: Optional[str] = None
    confidence_score: Optional[float] = None
    llm_enriched: bool = False


class CorrectionDB(SQLModel, table=True):
    __tablename__ = "corrections"
    id: Optional[int] = Field(default=None, primary_key=True)
    fingerprint: str = Field(
        unique=True, index=True
    )  # SHA-256 of (date+amount+narration)
    corrected_category: str
    corrected_merchant: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
