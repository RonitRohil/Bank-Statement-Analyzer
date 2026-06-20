import React from 'react';
import { AccountInfo, ConfidenceSummary } from '../types';
import { Building2, User, Calendar, ShieldCheck } from 'lucide-react';

interface AccountOverviewProps {
  info: AccountInfo;
  confidence: ConfidenceSummary;
}

const fmtDate = (d: string | null | undefined): string => {
  if (!d) return '—';
  try {
    return new Date(d + 'T00:00:00').toLocaleDateString('en-IN', {
      day: 'numeric', month: 'short', year: 'numeric',
    });
  } catch {
    return d;
  }
};

const scoreColor = (score: number): string => {
  if (score >= 0.9) return 'bg-emerald-500';
  if (score >= 0.75) return 'bg-amber-400';
  return 'bg-rose-500';
};

export const AccountOverview: React.FC<AccountOverviewProps> = ({ info, confidence }) => {
  const safeInfo: Partial<AccountInfo> = info || {};
  const safeConf = confidence || { high_confidence_txns: 0, total_transactions: 0, overall_score: 0 };
  const pct = Math.round(safeConf.overall_score * 100);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">

      {/* Bank Details */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100 lg:col-span-2">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <Building2 size={22} />
            </div>
            <div>
              <p className="text-xs text-slate-400 uppercase tracking-wider font-medium">Bank</p>
              <h3 className="text-base font-bold text-slate-800 leading-tight">
                {safeInfo.bank_name || <span className="text-slate-400 font-normal italic">Unknown Bank</span>}
              </h3>
            </div>
          </div>
          {safeInfo.ifsc_code ? (
            <span className="px-2.5 py-1 bg-blue-50 text-blue-700 text-xs font-mono font-semibold rounded-full border border-blue-100">
              {safeInfo.ifsc_code}
            </span>
          ) : (
            <span className="px-2.5 py-1 bg-slate-100 text-slate-400 text-xs rounded-full">No IFSC</span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wider mb-0.5">Account Number</p>
            <p className="font-mono text-slate-700 font-semibold text-sm">
              {safeInfo.account_number || <span className="text-slate-400 font-sans font-normal">—</span>}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wider mb-0.5">Branch</p>
            <p className="text-slate-700 font-medium text-sm truncate" title={safeInfo.branch || ''}>
              {safeInfo.branch || <span className="text-slate-400 font-normal">—</span>}
            </p>
          </div>
        </div>
      </div>

      {/* Account Holder */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
            <User size={22} />
          </div>
          <div className="min-w-0">
            <p className="text-xs text-slate-400 uppercase tracking-wider font-medium">Account Holder</p>
            <h3 className="text-base font-bold text-slate-800 truncate leading-tight" title={safeInfo.account_holder || ''}>
              {safeInfo.account_holder || <span className="text-slate-400 font-normal italic">—</span>}
            </h3>
          </div>
        </div>

        <div className="border-t border-slate-50 pt-3 mt-2">
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Calendar size={11} /> Statement Period
          </p>
          {safeInfo.statement_period?.from ? (
            <p className="text-sm font-medium text-slate-700">
              {fmtDate(safeInfo.statement_period.from)}
              <span className="text-slate-400 mx-1">–</span>
              {fmtDate(safeInfo.statement_period.to)}
            </p>
          ) : (
            <p className="text-sm text-slate-400 italic">Not available</p>
          )}
        </div>
      </div>

      {/* Parse Quality */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100">
        <div className="flex items-center gap-3 mb-3">
          <div className="p-2 bg-violet-50 text-violet-600 rounded-lg">
            <ShieldCheck size={22} />
          </div>
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wider font-medium">Parse Quality</p>
            <h3 className="text-2xl font-bold text-slate-800 leading-none mt-0.5">{pct}%</h3>
          </div>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
          <div
            className={`${scoreColor(safeConf.overall_score)} h-1.5 rounded-full transition-all duration-700`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="text-xs text-slate-400 mt-2 text-right">
          {safeConf.high_confidence_txns} / {safeConf.total_transactions} txns verified
        </p>
      </div>

    </div>
  );
};
