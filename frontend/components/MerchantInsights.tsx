import React from 'react';
import { MerchantInsight } from '../types';
import { Store, TrendingUp, CalendarClock } from 'lucide-react';

interface MerchantInsightsProps {
  insights: Record<string, MerchantInsight>;
}

export const MerchantInsights: React.FC<MerchantInsightsProps> = ({ insights }) => {
  // Defensive: Handle missing insights object
  const safeInsights = insights || {};
  const merchants = Object.entries(safeInsights) as [string, MerchantInsight][];

  if (merchants.length === 0) return null;

  return (
    <div className="mb-8">
      <h3 className="font-bold text-slate-800 text-lg mb-4 flex items-center gap-2">
        <Store className="text-indigo-600" size={20} />
        Merchant Insights
      </h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {merchants.map(([name, data]) => (
          <div key={name} className="bg-white p-4 rounded-xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start mb-3">
              <h4 className="font-semibold text-slate-700 truncate pr-2 w-full" title={name}>
                {name}
              </h4>
              <span className="bg-slate-100 text-slate-600 text-xs px-2 py-1 rounded-full whitespace-nowrap">
                {data.count} txns
              </span>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2 text-slate-500">
                  <TrendingUp size={14} />
                  <span>Avg Amount</span>
                </div>
                <span className="font-medium text-slate-800">
                  {new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(data.avg_amount || 0)}
                </span>
              </div>

              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2 text-slate-500">
                  <CalendarClock size={14} />
                  <span>Last Seen</span>
                </div>
                <span className="font-medium text-slate-800 text-xs">
                  {data.last_seen || 'N/A'}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};