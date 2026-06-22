import React, { useState, useEffect } from "react";
import { AnalysisResult, ApiResponse, ComparisonResponse } from "./types";
import { uploadBankStatement, compareStatements, API_BASE } from "./services/api";
import { FileUpload } from "./components/FileUpload";
import { AccountOverview } from "./components/AccountOverview";
import { TransactionTable } from "./components/TransactionTable";
import { MerchantInsights } from "./components/MerchantInsights";
import { AnalyticsCharts } from "./components/AnalyticsCharts";
import { SpendingSummary } from "./components/SpendingSummary";
import { InsightsStrip } from "./components/InsightsStrip";
import { ErrorBoundary } from "./components/ErrorBoundary";
import MonthlyComparison from "./components/MonthlyComparison";
import { LayoutDashboard, RefreshCw } from "lucide-react";

const App: React.FC = () => {
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [persist, setPersist] = useState<boolean>(false);
  const [comparisonData, setComparisonData] = useState<ComparisonResponse | null>(null);

  useEffect(() => {
    if (!data || !persist) return;
    const accountNumber = data.account_info?.account_number;
    if (!accountNumber) return;
    compareStatements(accountNumber)
      .then(setComparisonData)
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
