import {
  ApiResponse,
  ComparisonResponse,
  StoredStatement,
  SummaryResponse,
  Transaction,
} from "../types";

export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const uploadBankStatement = async (
  file: File,
  persist = false,
): Promise<ApiResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  const url = persist
    ? `${API_BASE}/api/analyze/bank/statement?persist=true`
    : `${API_BASE}/api/analyze/bank/statement`;

  let response: Response;

  // 1. Attempt the network request
  try {
    response = await fetch(url, {
      method: "POST",
      body: formData,
    });
  } catch (networkError) {
    // This catches DNS errors, connection refused, or CORS issues
    console.error("Network request failed:", networkError);
    throw new Error(
      `Network Error: Unable to connect to the backend server. Please ensure the API is running at ${API_BASE}.`,
      { cause: networkError },
    );
  }

  // 2. Handle HTTP Errors (4xx, 5xx)
  if (!response.ok) {
    let errorMsg = `Upload failed with status ${response.status}`;

    try {
      const errorData = await response.json();

      // Check for specific deep-nested error from backend logic (e.g., missing python dependency)
      if (errorData?.result?.error) {
        errorMsg = errorData.result.error;
      }
      // Check for standard API message
      else if (errorData?.message) {
        errorMsg = errorData.message;
      }
      // Fallback for generic details
      else if (errorData?.detail) {
        errorMsg =
          typeof errorData.detail === "string"
            ? errorData.detail
            : JSON.stringify(errorData.detail);
      }
    } catch {
      // Response was not JSON (e.g., raw 500 HTML page or Nginx error)
      if (response.statusText) {
        errorMsg = `Server Error: ${response.status} ${response.statusText}`;
      }
    }

    throw new Error(errorMsg);
  }

  // 3. Parse success response
  const data: ApiResponse = await response.json();
  return data;
};

export async function exportTransactions(
  transactions: Transaction[],
  format: "csv" | "xlsx",
  filename: string = "transactions",
): Promise<void> {
  const response = await fetch(`${API_BASE}/api/export/transactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transactions, format, filename }),
  });

  if (!response.ok) {
    throw new Error(`Export failed: ${response.statusText}`);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${filename}.${format}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export async function compareStatements(
  accountNumber: string,
): Promise<ComparisonResponse> {
  const res = await fetch(
    `${API_BASE}/api/statements/compare?account_number=${encodeURIComponent(accountNumber)}`,
  );
  if (!res.ok) throw new Error(`Compare failed: ${res.status}`);
  return res.json();
}

export async function getConfirmedRecurring(
  accountNumber: string,
): Promise<{
  confirmed_recurring: {
    merchant: string;
    statement_count: number;
    avg_amount: number;
    last_seen: string | null;
  }[];
}> {
  const res = await fetch(
    `${API_BASE}/api/statements/recurring?account_number=${encodeURIComponent(accountNumber)}`,
  );
  if (!res.ok) return { confirmed_recurring: [] };
  return res.json();
}

export async function askQuestion(question: string, accountNumber?: string) {
  const res = await fetch(`${API_BASE}/api/qa/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, account_number: accountNumber ?? null }),
  });
  if (!res.ok) throw new Error(`Q&A failed: ${res.status}`);
  return res.json() as Promise<{
    answer: string;
    tool_used: string;
    data_points: number;
  }>;
}

export async function deleteStatement(id: number): Promise<void> {
  const res = await fetch(`${API_BASE}/api/statements/${id}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
}

export async function getStatementTransactions(id: number) {
  const res = await fetch(
    `${API_BASE}/api/statements/${id}/transactions?limit=500`,
  );
  if (!res.ok) throw new Error(`Failed to load transactions: ${res.status}`);
  return res.json() as Promise<{
    statement_id: number;
    transactions: Transaction[];
  }>;
}

export async function listStatements(limit = 50): Promise<StoredStatement[]> {
  const res = await fetch(`${API_BASE}/api/statements?limit=${limit}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.statements ?? [];
}

export async function submitCorrection(
  transactionDate: string,
  amount: number,
  narration: string,
  correctedCategory: string,
  correctedMerchant?: string,
) {
  const res = await fetch(`${API_BASE}/api/corrections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      transaction_date: transactionDate,
      amount,
      narration,
      corrected_category: correctedCategory,
      corrected_merchant: correctedMerchant ?? null,
    }),
  });
  if (!res.ok) throw new Error(`Correction failed: ${res.status}`);
  return res.json();
}

export const getSummary = async (
  transactions: Transaction[],
): Promise<SummaryResponse> => {
  const res = await fetch(`${API_BASE}/api/analyze/bank/summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transactions }),
  });
  if (!res.ok) throw new Error(`Summary failed: ${res.status}`);
  return res.json();
};
