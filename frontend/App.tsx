import React, { useState, useEffect } from "react";
import {
  AnalysisResult,
  ApiResponse,
  ComparisonResponse,
  StoredStatement,
  StoredTransactionRaw,
  Transaction,
} from "./types";
import {
  uploadBankStatement,
  compareStatements,
  getConfirmedRecurring,
  deleteStatement,
  getStatementTransactions,
  listStatements,
  API_BASE,
} from "./services/api";
import { FileUpload } from "./components/FileUpload";
import { AccountOverview } from "./components/AccountOverview";
import { TransactionTable } from "./components/TransactionTable";
import { MerchantInsights } from "./components/MerchantInsights";
import { AnalyticsCharts } from "./components/AnalyticsCharts";
import { SpendingSummary } from "./components/SpendingSummary";
import { InsightsStrip } from "./components/InsightsStrip";
import { ErrorBoundary } from "./components/ErrorBoundary";
import MonthlyComparison from "./components/MonthlyComparison";
import SubscriptionsCard from "./components/SubscriptionsCard";
import QAChat from "./components/QAChat";
import HistoryPanel from "./components/HistoryPanel";
import { LayoutDashboard, RefreshCw } from "lucide-react";

const App: React.FC = () => {
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [persist, setPersist] = useState<boolean>(false);
  const [comparisonData, setComparisonData] =
    useState<ComparisonResponse | null>(null);
  const [confirmedRecurring, setConfirmedRecurring] = useState<
    {
      merchant: string;
      statement_count: number;
      avg_amount: number;
      last_seen: string | null;
    }[]
  >([]);
  const [storedStatements, setStoredStatements] = useState<StoredStatement[]>(
    [],
  );
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);

  const fetchStatements = () => {
    listStatements(50)
      .then(setStoredStatements)
      .catch(() => {});
  };

  useEffect(() => {
    fetchStatements();
  }, []);

  const handleHistoryLoad = (id: number) => {
    setHistoryLoading(true);
    setError(null);
    setComparisonData(null);
    const statement = storedStatements.find((s) => s.id === id);
    getStatementTransactions(id)
      .then((res) => {
        const txns = res.transactions.map((t: StoredTransactionRaw) => ({
          ...t,
          category:
            typeof t.category === "string"
              ? (() => {
                  try {
                    return JSON.parse(t.category || "[]");
                  } catch {
                    return [];
                  }
                })()
              : (t.category ?? []),
          receiver_details: { account: null, name: null, vpa: null },
          remarks: [],
          bank_peer: null,
          upi_id: null,
          account: null,
          narration: t.narration ?? "",
          transaction_date: t.transaction_date ?? "",
          transaction_type: (t.transaction_type ?? "DEBIT") as
            | "CREDIT"
            | "DEBIT",
          confidence_score: t.confidence_score ?? 0,
        })) as Transaction[];
        setData({
          account_info: {
            account_holder: statement?.account_holder ?? null,
            account_number: statement?.account_number ?? null,
            bank_name: statement?.bank_name ?? null,
            branch: null,
            email: null,
            ifsc_code: null,
            phone: null,
            statement_period: {
              from: statement?.period_from ?? null,
              to: statement?.period_to ?? null,
            },
          },
          transactions: txns,
          confidence_summary: {
            overall_score: statement?.confidence_overall ?? 0,
            total_transactions: txns.length,
            high_confidence_txns: txns.filter(
              (t) => (t.confidence_score ?? 0) >= 0.8,
            ).length,
          },
          merchant_insights: {},
          insights: [],
          recurring_candidates: [],
        });
      })
      .catch((err) => {
        setError(
          err instanceof Error ? err.message : "Failed to load statement",
        );
      })
      .finally(() => {
        setHistoryLoading(false);
      });
  };

  const handleHistoryDelete = (id: number) => {
    deleteStatement(id)
      .then(() =>
        setStoredStatements((prev) => prev.filter((s) => s.id !== id)),
      )
      .catch((err) => {
        setError(
          err instanceof Error ? err.message : "Failed to delete statement",
        );
      });
  };

  useEffect(() => {
    if (!data || !persist) return;
    const accountNumber = data.account_info?.account_number;
    if (!accountNumber) return;
    compareStatements(accountNumber)
      .then(setComparisonData)
      .catch(() => {});
    getConfirmedRecurring(accountNumber)
      .then((r) => setConfirmedRecurring(r.confirmed_recurring))
      .catch(() => {});
  }, [data, persist]);

  const handleFileSelect = async (file: File) => {
    setLoading(true);
    setError(null);
    setComparisonData(null);
    try {
      const response: ApiResponse = await uploadBankStatement(file, persist);
      if (response.success === 1 && response.result) {
        setData(response.result);
        if (persist) fetchStatements();
      } else {
        // Handle logic errors where HTTP might be 200 but success is 0
        setError(
          (response.result as unknown as { error?: string })?.error ||
            response.message ||
            "Failed to analyze statement",
        );
      }
    } catch (err) {
      let errorMessage = "An unexpected error occurred.";
      if (err instanceof Error) {
        errorMessage = err.message;
        // Check for common network error messages (Chrome: 'Failed to fetch', others might vary)
        if (
          errorMessage === "Failed to fetch" ||
          errorMessage.toLowerCase().includes("network")
        ) {
          errorMessage = `Connection failed. Ensure backend is running at ${API_BASE}`;
        }
      }
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setData(null);
    setError(null);
    setComparisonData(null);
    setConfirmedRecurring([]);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 pb-20">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="bg-indigo-600 p-2 rounded-lg">
              <LayoutDashboard className="text-white w-5 h-5" />
            </div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              FinAnalyze
            </h1>
          </div>
          {data && (
            <button
              onClick={handleReset}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Analyze New File
            </button>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Empty State / Upload */}
        {!data && (
          <div className="flex flex-col items-center justify-center min-h-[60vh]">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-slate-900 mb-4">
                Unlock Financial Insights
              </h2>
              <p className="text-slate-500 text-lg max-w-2xl mx-auto">
                Upload your bank statement (PDF, Excel, CSV) to automatically
                categorize transactions, track spending habits, and visualize
                your cash flow.
              </p>
            </div>
            <FileUpload
              onFileSelect={handleFileSelect}
              isLoading={loading}
              error={error}
              onDismissError={() => setError(null)}
            />
            <label className="mt-4 flex items-center gap-2 text-sm text-slate-600 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={persist}
                onChange={(e) => setPersist(e.target.checked)}
                className="w-4 h-4 accent-indigo-600"
              />
              Save to history (enables month-over-month comparison)
            </label>
            {storedStatements.length > 0 && (
              <div className="w-full max-w-2xl mt-4">
                <HistoryPanel
                  statements={storedStatements}
                  onLoad={handleHistoryLoad}
                  onDelete={handleHistoryDelete}
                  loading={historyLoading}
                />
              </div>
            )}
          </div>
        )}

        {/* Dashboard */}
        {data && (
          <div className="animate-in fade-in duration-500">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-slate-800">
                Statement Analysis
              </h2>
              <span className="text-sm text-slate-500 bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm">
                Generated: {new Date().toLocaleDateString()}
              </span>
            </div>

            <ErrorBoundary>
              <AccountOverview
                info={data.account_info}
                confidence={data.confidence_summary}
              />
            </ErrorBoundary>

            <ErrorBoundary>
              <InsightsStrip insights={data.insights ?? []} />
            </ErrorBoundary>

            <ErrorBoundary>
              <SpendingSummary transactions={data.transactions} />
            </ErrorBoundary>

            <ErrorBoundary>
              <AnalyticsCharts
                transactions={data.transactions}
                merchantInsights={data.merchant_insights}
              />
            </ErrorBoundary>

            <ErrorBoundary>
              <MerchantInsights
                insights={data.merchant_insights}
                recurringCandidates={data.recurring_candidates ?? []}
              />
            </ErrorBoundary>

            {comparisonData && (
              <ErrorBoundary>
                <MonthlyComparison
                  months={comparisonData.months}
                  accountNumber={comparisonData.account_number}
                />
              </ErrorBoundary>
            )}

            {confirmedRecurring.length > 0 && (
              <ErrorBoundary>
                <SubscriptionsCard subscriptions={confirmedRecurring} />
              </ErrorBoundary>
            )}

            {persist && (
              <ErrorBoundary>
                <QAChat
                  accountNumber={data.account_info?.account_number ?? undefined}
                />
              </ErrorBoundary>
            )}

            {storedStatements.length > 0 && (
              <ErrorBoundary>
                <HistoryPanel
                  statements={storedStatements}
                  onLoad={handleHistoryLoad}
                  onDelete={handleHistoryDelete}
                  loading={historyLoading}
                />
              </ErrorBoundary>
            )}

            <ErrorBoundary>
              <TransactionTable transactions={data.transactions} />
            </ErrorBoundary>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
