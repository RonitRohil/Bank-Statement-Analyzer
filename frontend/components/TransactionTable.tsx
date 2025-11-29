import React from 'react';
import { Transaction } from '../types';
import { ArrowDownLeft, ArrowUpRight } from 'lucide-react';

interface TransactionTableProps {
  transactions: Transaction[];
}

export const TransactionTable: React.FC<TransactionTableProps> = ({ transactions }) => {
  // Defensive check for transactions array
  const safeTransactions = transactions || [];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-100 flex justify-between items-center">
        <h3 className="font-bold text-slate-800 text-lg">Transactions</h3>
        <span className="text-sm text-slate-500">{safeTransactions.length} entries</span>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wider">
              <th className="px-6 py-3 font-semibold">Date</th>
              <th className="px-6 py-3 font-semibold">Narration</th>
              <th className="px-6 py-3 font-semibold">Method</th>
              <th className="px-6 py-3 font-semibold text-right">Amount</th>
              <th className="px-6 py-3 font-semibold text-right">Balance</th>
              <th className="px-6 py-3 font-semibold text-center">Type</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-sm">
            {safeTransactions.map((txn, index) => (
              <tr key={`${txn.transaction_reference}-${index}`} className="hover:bg-slate-50 transition-colors">
                <td className="px-6 py-4 font-medium text-slate-700 whitespace-nowrap">
                  {txn.transaction_date}
                </td>
                <td className="px-6 py-4 text-slate-600 max-w-xs truncate" title={txn.narration}>
                  {txn.narration}
                  {txn.receiver_details?.name && (
                    <div className="text-xs text-slate-400 mt-1">To: {txn.receiver_details.name}</div>
                  )}
                </td>
                <td className="px-6 py-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-600">
                    {txn.payment_method || 'OTH'}
                  </span>
                </td>
                <td className={`px-6 py-4 text-right font-bold ${
                  txn.transaction_type === 'CREDIT' ? 'text-emerald-600' : 'text-rose-600'
                }`}>
                  {txn.transaction_type === 'CREDIT' ? '+' : '-'} 
                  {new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(txn.amount || 0)}
                </td>
                <td className="px-6 py-4 text-right text-slate-700">
                   {new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(txn.balance || 0)}
                </td>
                <td className="px-6 py-4 text-center">
                  {txn.transaction_type === 'CREDIT' ? (
                    <div className="inline-flex items-center gap-1 text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full text-xs font-bold">
                      <ArrowDownLeft size={12} /> Credit
                    </div>
                  ) : (
                    <div className="inline-flex items-center gap-1 text-rose-600 bg-rose-50 px-2 py-1 rounded-full text-xs font-bold">
                      <ArrowUpRight size={12} /> Debit
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {safeTransactions.length === 0 && (
        <div className="p-8 text-center text-slate-400">
          No transactions found in this period.
        </div>
      )}
    </div>
  );
};