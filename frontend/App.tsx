import React, { useState } from 'react';
import { AnalysisResult, ApiResponse } from './types';
import { uploadBankStatement } from './services/api';
import { FileUpload } from './components/FileUpload';
import { AccountOverview } from './components/AccountOverview';
import { TransactionTable } from './components/TransactionTable';
import { MerchantInsights } from './components/MerchantInsights';
import { AnalyticsCharts } from './components/AnalyticsCharts';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LayoutDashboard, RefreshCw } from 'lucide-react';

const App: React.FC = () => {
  const [data, setData] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      const response: ApiResponse = await uploadBankStatement(file);
      if (response.success === 1 && response.result) {
        setData(response.result);
      } else {
        // Handle logic errors where HTTP might be 200 but success is 0
        const resAny = response as any;
        setError(resAny.result?.error || response.message || 'Failed to analyze statement');
      }
    } catch (err) {
      let errorMessage = 'An unexpected error occurred.';
      if (err instanceof Error) {
        errorMessage = err.message;
        // Check for common network error messages (Chrome: 'Failed to fetch', others might vary)
        if (errorMessage === 'Failed to fetch' || errorMessage.toLowerCase().includes('network')) {
          errorMessage = 'Connection failed. Ensure backend is running at http://localhost:5000';
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
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">FinAnalyze</h1>
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
              <h2 className="text-3xl font-bold text-slate-900 mb-4">Unlock Financial Insights</h2>
              <p className="text-slate-500 text-lg max-w-2xl mx-auto">
                Upload your bank statement (PDF, Excel, CSV) to automatically categorize transactions, track spending habits, and visualize your cash flow.
              </p>
            </div>
            <FileUpload 
              onFileSelect={handleFileSelect} 
              isLoading={loading} 
              error={error}
              onDismissError={() => setError(null)}
            />
          </div>
        )}

        {/* Dashboard */}
        {data && (
          <div className="animate-in fade-in duration-500">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-slate-800">Statement Analysis</h2>
              <span className="text-sm text-slate-500 bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm">
                Generated: {new Date().toLocaleDateString()}
              </span>
            </div>

            <ErrorBoundary>
              <AccountOverview info={data.account_info} confidence={data.confidence_summary} />
            </ErrorBoundary>
            
            <ErrorBoundary>
              <AnalyticsCharts transactions={data.transactions} merchantInsights={data.merchant_insights} />
            </ErrorBoundary>
            
            <ErrorBoundary>
              <MerchantInsights insights={data.merchant_insights} />
            </ErrorBoundary>
            
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
