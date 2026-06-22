export interface AccountInfo {
  account_holder: string | null;
  account_number: string | null;
  bank_name: string | null;
  branch: string | null;
  email: string | null;
  ifsc_code: string | null;
  phone: string | null;
  statement_period?: {
    from: string | null;
    to: string | null;
  };
}

export interface ConfidenceSummary {
  high_confidence_txns: number;
  overall_score: number;
  total_transactions: number;
}

export interface MerchantInsight {
  avg_amount: number;
  common_days: string[];
  count: number;
  first_seen: string | null;
  last_seen: string | null;
  median_amount: number;
  std_amount: number | null;
}

export interface ReceiverDetails {
  account: string | null;
  name: string | null;
  vpa: string | null;
}

export interface Transaction {
  account: string | null;
  amount: number | null;
  balance: number | null;
  bank_peer: string | null;
  category: string[];
  confidence_score: number;
  llm_enriched?: boolean;
  merchant: string | null;
  narration: string;
  payment_gateway: string | null;
  payment_method: string | null;
  receiver_details: ReceiverDetails;
  remarks: string[];
  transaction_date: string;
  transaction_reference: string | null;
  transaction_type: "CREDIT" | "DEBIT";
  upi_id: string | null;
}

export interface RecurringCandidate {
  merchant: string;
  count: number;
  avg_amount: number;
  std_amount: number;
  cv: number;
  first_seen: string | null;
  last_seen: string | null;
  common_days: number[];
}

export interface AnalysisResult {
  account_info: AccountInfo;
  confidence_summary: ConfidenceSummary;
  insights: string[];
  merchant_insights: Record<string, MerchantInsight>;
  recurring_candidates?: RecurringCandidate[];
  transactions: Transaction[];
}

export interface ApiResponse {
  message: string;
  result: AnalysisResult;
  status_code: number;
  success: number;
}

export interface CategoryBreakdown {
  category: string;
  count: number;
  percentage: number;
  total: number;
}

export interface TopMerchant {
  count: number;
  merchant: string;
  total: number;
}

export interface MonthSummary {
  month: string; // "YYYY-MM"
  income: number;
  expenses: number;
  net: number;
  transaction_count: number;
  top_category: string | null;
  delta_expenses_pct: number | null;
}

export interface ComparisonResponse {
  account_number: string;
  months: MonthSummary[];
  total_months: number;
}

export interface StoredStatement {
  id: number;
  bank_name: string | null;
  account_holder: string | null;
  account_number: string | null;
  period_from: string | null;
  period_to: string | null;
  uploaded_at: string;
  confidence_overall: number | null;
}

export interface SummaryResponse {
  avg_transaction_amount: number;
  by_category: CategoryBreakdown[];
  currency: string;
  date_range?: { from: string | null; to: string | null };
  net: number;
  top_merchants: TopMerchant[];
  total_expenses: number;
  total_income: number;
  transaction_count: number;
}
