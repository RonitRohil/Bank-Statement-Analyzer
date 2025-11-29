import React from 'react';
import { AccountInfo, ConfidenceSummary } from '../types';
import { Building2, User, Calendar, ShieldCheck } from 'lucide-react';

interface AccountOverviewProps {
  info: AccountInfo;
  confidence: ConfidenceSummary;
}

export const AccountOverview: React.FC<AccountOverviewProps> = ({ info, confidence }) => {
  // Defensive check: if info is completely missing or null
  const safeInfo: Partial<AccountInfo> = info || {};
  const safeConfidence = confidence || { high_confidence_txns: 0, total_transactions: 0, overall_score: 0 };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {/* Account Card */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100 lg:col-span-2">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-50 text-blue-600 rounded-lg">
              <Building2 size={24} />
            </div>
            <div>
              <p className="text-sm text-slate-500 font-medium">Bank Details</p>
              <h3 className="text-lg font-bold text-slate-800">{safeInfo.bank_name || 'Unknown Bank'}</h3>
            </div>
          </div>
          <span className="px-3 py-1 bg-slate-100 text-slate-600 text-xs font-bold rounded-full">
            {safeInfo.ifsc_code || 'NO IFSC'}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wider">Account Number</p>
            <p className="font-mono text-slate-700 font-medium">{safeInfo.account_number || 'N/A'}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wider">Branch</p>
            <p className="text-slate-700 font-medium truncate" title={safeInfo.branch || ''}>{safeInfo.branch || 'N/A'}</p>
          </div>
        </div>
      </div>

      {/* Holder Card */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-emerald-50 text-emerald-600 rounded-lg">
            <User size={24} />
          </div>
          <div>
            <p className="text-sm text-slate-500 font-medium">Account Holder</p>
            <h3 className="text-base font-bold text-slate-800 truncate" title={safeInfo.account_holder || ''}>
              {safeInfo.account_holder || 'Unknown'}
            </h3>
          </div>
        </div>
        <div className="mt-4">
           <div className="flex items-center gap-2 text-sm text-slate-600">
             <Calendar size={14} />
             <span>
               {safeInfo.statement_period?.from || 'N/A'} - {safeInfo.statement_period?.to || 'N/A'}
             </span>
           </div>
        </div>
      </div>

      {/* Confidence Score */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-violet-50 text-violet-600 rounded-lg">
            <ShieldCheck size={24} />
          </div>
          <div>
            <p className="text-sm text-slate-500 font-medium">Parse Quality</p>
            <h3 className="text-xl font-bold text-slate-800">
              {(safeConfidence.overall_score * 100).toFixed(0)}%
            </h3>
          </div>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-2 mt-2 overflow-hidden">
          <div 
            className="bg-violet-500 h-2 rounded-full" 
            style={{ width: `${safeConfidence.overall_score * 100}%` }}
          ></div>
        </div>
        <p className="text-xs text-slate-400 mt-2 text-right">
          {safeConfidence.high_confidence_txns} / {safeConfidence.total_transactions} txns verified
        </p>
      </div>
    </div>
  );
};