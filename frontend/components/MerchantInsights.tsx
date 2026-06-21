import React from "react";
import { MerchantInsight, RecurringCandidate } from "../types";
import { Store, TrendingUp, CalendarClock, Layers } from "lucide-react";

interface MerchantInsightsProps {
  insights: Record<string, MerchantInsight>;
  recurringCandidates: RecurringCandidate[];
}

const inr = (val: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(val);

const fmtDate = (d: string | null | undefined): string => {
  if (!d) return "—";
  try {
    return new Date(d + "T00:00:00").toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return d;
  }
};

/** Skip entries that are noise rather than real merchant names. */
const isNamedMerchant = (name: string): boolean => {
  if (!name || name === "UNKNOWN") return false;
  if (/^\d+$/.test(name)) return false;
  if (/^ACCT\s/i.test(name)) return false;
  return true;
};

export const MerchantInsights: React.FC<MerchantInsightsProps> = ({
  insights,
  recurringCandidates,
}) => {
  const safeInsights = insights || {};
  const recurringSet = new Set(
    (recurringCandidates ?? []).map((r) => r.merchant),
  );

  const named = (Object.entries(safeInsights) as [string, MerchantInsight][])
    .filter(([name]) => isNamedMerchant(name))
    .sort((a, b) => {
      const volA = a[1].count * (a[1].avg_amount || 0);
      const volB = b[1].count * (b[1].avg_amount || 0);
      return volB - volA;
    });

  const unknownEntry = safeInsights["UNKNOWN"];
  const unknownCount = unknownEntry?.count ?? 0;

  if (named.length === 0 && unknownCount === 0) return null;

  return (
    <div className="mb-8">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-bold text-slate-800 text-base flex items-center gap-2">
          <Store className="text-indigo-600" size={18} />
          Merchant Insights
          {named.length > 0 && (
            <span className="text-xs font-normal text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">
              {named.length} identified
            </span>
          )}
        </h3>
        {unknownCount > 0 && (
          <span className="text-xs text-slate-400 flex items-center gap-1">
            <Layers size={12} />
            {unknownCount} uncategorized txn{unknownCount !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {named.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {named.map(([name, data]) => {
            const totalVol = data.count * (data.avg_amount || 0);
            return (
              <div
                key={name}
                className="bg-white p-4 rounded-xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between items-start mb-3">
                  <h4
                    className="font-semibold text-slate-800 truncate pr-2 flex items-center gap-1"
                    title={name}
                  >
                    <span>{name}</span>
                    {recurringSet.has(name) && (
                      <span
                        title="Likely recurring"
                        className="ml-1 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700"
                      >
                        ↻
                      </span>
                    )}
                  </h4>
                  <span className="bg-indigo-50 text-indigo-600 text-xs px-2 py-0.5 rounded-full whitespace-nowrap font-medium">
                    {data.count} txn{data.count !== 1 ? "s" : ""}
                  </span>
                </div>

                <div className="space-y-2.5">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <TrendingUp size={13} /> Avg / txn
                    </span>
                    <span className="font-semibold text-slate-800">
                      {inr(data.avg_amount || 0)}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400">Total spent</span>
                    <span className="font-semibold text-slate-800">
                      {inr(totalVol)}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-400 flex items-center gap-1.5">
                      <CalendarClock size={13} /> Last seen
                    </span>
                    <span className="text-slate-600 text-xs">
                      {fmtDate(data.last_seen)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="text-slate-400 text-sm">
          No named merchants could be identified from narrations.
        </p>
      )}
    </div>
  );
};
