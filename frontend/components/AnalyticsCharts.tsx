import React from 'react';
import { Transaction, MerchantInsight } from '../types';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
  PieChart,
  Pie,
  Cell
} from 'recharts';

interface AnalyticsChartsProps {
  transactions: Transaction[];
  merchantInsights: Record<string, MerchantInsight>;
}

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#f43f5e', '#8b5cf6', '#64748b'];

export const AnalyticsCharts: React.FC<AnalyticsChartsProps> = ({ transactions, merchantInsights }) => {
  // Robustness check: Ensure data exists before processing
  const safeTransactions = transactions || [];
  const safeMerchantInsights = merchantInsights || {};

  if (safeTransactions.length === 0) {
    return (
      <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-100 text-center text-slate-400 mb-8">
        Not enough data to generate charts.
      </div>
    );
  }

  // Process data for charts
  const sortedTxns = [...safeTransactions].sort((a, b) => {
    // Handle invalid dates safely
    const dateA = new Date(a.transaction_date).getTime();
    const dateB = new Date(b.transaction_date).getTime();
    return (isNaN(dateA) ? 0 : dateA) - (isNaN(dateB) ? 0 : dateB);
  });

  const balanceData = sortedTxns.map(t => ({
    date: t.transaction_date,
    balance: t.balance || 0,
  }));

  const expense = safeTransactions
    .filter(t => t.transaction_type === 'DEBIT')
    .reduce((sum, t) => sum + (t.amount || 0), 0);

  const income = safeTransactions
    .filter(t => t.transaction_type === 'CREDIT')
    .reduce((sum, t) => sum + (t.amount || 0), 0);

  const flowData = [
    {
      name: 'Flow',
      Income: income,
      Expense: expense,
    }
  ];

  // Prepare Merchant Data for Pie Chart
  const merchantData = (Object.entries(safeMerchantInsights) as [string, MerchantInsight][])
    .map(([name, data]) => ({
      name: name.length > 15 ? name.substring(0, 15) + '...' : name,
      fullName: name,
      value: (data.count || 0) * (data.avg_amount || 0)
    }))
    .filter(item => item.value > 0)
    .sort((a, b) => b.value - a.value);

  // Group smaller slices if too many
  const topMerchants = merchantData.slice(0, 5);
  const otherValue = merchantData.slice(5).reduce((sum, item) => sum + item.value, 0);
  
  const pieData = [...topMerchants];
  if (otherValue > 0) {
    pieData.push({ name: 'Others', fullName: 'Others', value: otherValue });
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      {/* Balance History Chart - Full Width */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100 lg:col-span-2">
        <h3 className="font-bold text-slate-800 text-lg mb-6">Balance History</h3>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={balanceData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis 
                dataKey="date" 
                tick={{fontSize: 12, fill: '#64748b'}} 
                axisLine={false}
                tickLine={false}
              />
              <YAxis 
                tick={{fontSize: 12, fill: '#64748b'}} 
                axisLine={false}
                tickLine={false}
                tickFormatter={(val) => `₹${(val/1000).toFixed(0)}k`}
              />
              <Tooltip 
                contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                formatter={(val: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(val)}
              />
              <Line 
                type="monotone" 
                dataKey="balance" 
                stroke="#6366f1" 
                strokeWidth={3} 
                dot={{r: 4, fill: '#6366f1', strokeWidth: 2, stroke: '#fff'}}
                activeDot={{r: 6}}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Income vs Expense Chart */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100">
        <h3 className="font-bold text-slate-800 text-lg mb-6">Cash Flow</h3>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={flowData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
              <XAxis dataKey="name" hide />
              <YAxis 
                tick={{fontSize: 12, fill: '#64748b'}} 
                axisLine={false}
                tickLine={false}
                tickFormatter={(val) => `₹${(val/1000).toFixed(0)}k`}
              />
              <Tooltip 
                 cursor={{fill: 'transparent'}}
                 contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                 formatter={(val: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(val)}
              />
              <Legend />
              <Bar dataKey="Income" fill="#10b981" radius={[4, 4, 0, 0]} barSize={40} />
              <Bar dataKey="Expense" fill="#f43f5e" radius={[4, 4, 0, 0]} barSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Merchant Volume Pie Chart */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100">
        <h3 className="font-bold text-slate-800 text-lg mb-6">Top Merchants by Volume</h3>
        <div className="h-64 w-full relative">
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  formatter={(val: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(val)}
                  contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-slate-400">
              No merchant data available
            </div>
          )}
        </div>
      </div>
    </div>
  );
};