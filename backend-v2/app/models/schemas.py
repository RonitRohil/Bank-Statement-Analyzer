from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class StatementPeriod(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)

    from_date: Optional[str] = Field(None, alias="from")
    to_date: Optional[str] = Field(None, alias="to")


class AccountInfo(BaseModel):
    account_holder: Optional[str] = None
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
    branch: Optional[str] = None
    ifsc_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    statement_period: Optional[StatementPeriod] = None


class ReceiverDetails(BaseModel):
    name: Optional[str] = None
    account: Optional[str] = None
    vpa: Optional[str] = None


class Transaction(BaseModel):
    transaction_date: Optional[str] = None
    narration: Optional[str] = None
    payment_method: Optional[str] = None
    upi_id: Optional[str] = None
    transaction_reference: Optional[str] = None
    bank_peer: Optional[str] = None
    merchant: Optional[str] = None
    category: List[str] = []
    remarks: List[str] = []
    payment_gateway: Optional[str] = None
    amount: Optional[float] = None
    balance: Optional[float] = None
    confidence_score: Optional[float] = None
    transaction_type: Optional[str] = None
    receiver_details: Optional[ReceiverDetails] = None
    account: Optional[str] = None
    llm_enriched: bool = False


class ConfidenceSummary(BaseModel):
    overall_score: float
    total_transactions: int
    high_confidence_txns: int


class MerchantInsight(BaseModel):
    count: int
    avg_amount: float
    median_amount: float
    std_amount: Optional[float] = None
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    common_days: List[Any] = []


class AnalysisResult(BaseModel):
    account_info: AccountInfo
    transactions: List[Transaction]
    confidence_summary: ConfidenceSummary
    merchant_insights: Dict[str, Any]


class AnalyzeResponse(BaseModel):
    success: int
    status_code: int
    message: str
    result: AnalysisResult


class ErrorResponse(BaseModel):
    success: int = 0
    status_code: int
    message: str
    details: Optional[str] = None


class CategoryBreakdown(BaseModel):
    category: str
    total: float
    count: int
    percentage: float


class TopMerchant(BaseModel):
    merchant: str
    total: float
    count: int


class SummaryResponse(BaseModel):
    total_income: float
    total_expenses: float
    net: float
    currency: str = "INR"
    date_range: Optional[StatementPeriod] = None
    by_category: list[CategoryBreakdown]
    top_merchants: list[TopMerchant]
    transaction_count: int
    avg_transaction_amount: float
