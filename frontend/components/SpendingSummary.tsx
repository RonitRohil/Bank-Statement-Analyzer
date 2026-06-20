import React, { useEffect, useState } from "react";
import { SummaryResponse, Transaction } from "../types";
import { getSummary } from "../services/api";

interface SpendingSummaryProps {
  transactions: Transaction[];
}

export const SpendingSummary: React.FC<SpendingSummaryProps> = ({
  transactions,
}) => {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!transactions.length) return;
    setLoading(true);
    setError(null);
    getSummary(transactions)
      .then(setSummary)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Summary unavailable"),
      )
      .finally(() => setLoading(false));
  }, [transactions]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 mb-6 animate-pulse">
        <div className="h-4 bg-slate-200 rounded w-40 mb-4" />
        <div className="grid grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-20 bg-slate-100 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 mb-6">
        <p className="text-sm text-slate-500">
          Spending summary unavailable: {error}
        </p>
      </div>
    );
  }

  if (!summary) return null;

  const currency = summary.currency ?? "INR";
  const fmt = (n: number) =>
    new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(n);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 mb-6">
      <h3 className="font-bold text-slate-800 text-lg mb-4">
        Spending Summary
      </h3>

      {/* Big-number tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-emerald-50 rounded-lg p-4">
          <p className="text-xs text-emerald-600 font-semibold uppercase tracking-wide mb-1">
            Total Income
          </p>
          <p className="text-2xl font-bold text-emerald-700">
            {fmt(summary.total_income)}
          </p>
        </div>
        <div className="bg-rose-50 rounded-lg p-4">
          <p className="text-xs text-rose-600 font-semibold uppercase tracking-wide mb-1">
            Total Expenses
          </p>
          <p className="text-2xl font-bold text-rose-700">
            {fmt(summary.total_expenses)}
          </p>
        </div>
        <div
          className={`${summary.net >= 0 ? "bg-indigo-50" : "bg-amber-50"} rounded-lg p-4`}
        >
          <p
            className={`text-xs font-semibold uppercase tracking-wide mb-1 ${summary.net >= 0 ? "text-indigo-600" : "text-amber-600"}`}
          >
            Net
          </p>
          <p
            className={`text-2xl font-bold ${summary.net >= 0 ? "text-indigo-700" : "text-amber-700"}`}
          >
            {fmt(summary.net)}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        {/* Top categories */}
        {summary.by_category.length > 0 && (
          <div>
            <p className="text-sm font-semibold text-slate-700 mb-2">
              Top Categories{" "}
              <span className="text-xs text-slate-400 font-normal">
                (share of spend — may exceed 100%)
              </span>
            </p>
            <ul className="space-y-2">
              {summary.by_category.slice(0, 5).map((cat) => (
                <li
                  key={cat.category}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-slate-600">{cat.category}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-700 font-medium">
                      {fmt(cat.total)}
                    </span>
                    <span className="text-xs text-slate-400 w-12 text-right">
                      {cat.percentage.toFixed(1)}%
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Top merchants */}
        {summary.top_merchants.length > 0 && (
          <div>
            <p className="text-sm font-semibold text-slate-700 mb-2">
              Top Merchants
            </p>
            <ul className="space-y-2">
              {summary.top_merchants.slice(0, 5).map((m) => (
                <li
                  key={m.merchant}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-slate-600">{m.merchant}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-700 font-medium">
                      {fmt(m.total)}
                    </span>
                    <span className="text-xs text-slate-400">{m.count}×</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};
