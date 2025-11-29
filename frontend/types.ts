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
  amount: number;
  balance: number;
  bank_peer: string | null;
  category: string[];
  confidence_score: number;
  merchant: string | null;
  narration: string;
  payment_gateway: string | null;
  payment_method: string | null; // e.g., "IMPS", "CHEQUE"
  receiver_details: ReceiverDetails;
  remarks: string[];
  transaction_date: string;
  transaction_reference: string | null;
  transaction_type: "CREDIT" | "DEBIT";
  upi_id: string | null;
}

export interface AnalysisResult {
  account_info: AccountInfo;
  confidence_summary: ConfidenceSummary;
  merchant_insights: Record<string, MerchantInsight>;
  transactions: Transaction[];
}

export interface ApiResponse {
  message: string;
  result: AnalysisResult;
  status_code: number;
  success: number;
}