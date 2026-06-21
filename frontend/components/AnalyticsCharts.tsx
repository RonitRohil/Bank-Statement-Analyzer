import React from "react";
import { Transaction, MerchantInsight } from "../types";
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
  Cell,
} from "recharts";

interface AnalyticsChartsProps {
  transactions: Transaction[];
  merchantInsights: Record<string, MerchantInsight>;
}

const COLORS = [
  "#6366f1",
  "#10b981",
  "#f59e0b",
  "#f43f5e",
  "#8b5cf6",
  "#64748b",
];

const inr = (val: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(val);

const fmtAxisDate = (dateStr: string): string => {
  try {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  } catch {
    return dateStr;
  }
};

/** Entries that are noise, not real merchant names. */
const isNamedMerchant = (name: string): boolean => {
  if (!name || name === "UNKNOWN") return false;
  if (/^\d+$/.test(name)) return false; // pure numeric
  if (/^ACCT\s/i.test(name)) return false; // internal account ref
  return true;
};

export const AnalyticsCharts: React.FC<AnalyticsChartsProps> = ({
  transactions,
  merchantInsights,
}) => {
  const safeTransactions = transactions || [];
  const safeMerchantInsights = merchantInsights || {};

  if (safeTransactions.length === 0) {
    return (
      <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-100 text-center text-slate-400 mb-8">
        Not enough data to generate charts.
      </div>
    );
  }

  const sortedTxns = [...safeTransactions].sort((a, b) => {
    const da = new Date(a.transaction_date).getTime();
    const db = new Date(b.transaction_date).getTime();
    return (isNaN(da) ? 0 : da) - (isNaN(db) ? 0 : db);
  });

  const balanceData = sortedTxns.map((t) => ({
    date: t.transaction_date,
    balance: t.balance || 0,
  }));

  const expense = safeTransactions
    .filter((t) => t.transaction_type === "DEBIT")
    .reduce((s, t) => s + (t.amount || 0), 0);
  const income = safeTransactions
    .filter((t) => t.transaction_type === "CREDIT")
    .reduce((s, t) => s + (t.amount || 0), 0);
  const net = income - expense;

  const flowData = [{ name: "Flow", Income: income, Expense: expense }];

  // Only named merchants in the pie chart
  const merchantData = (
    Object.entries(safeMerchantInsights) as [string, MerchantInsight][]
  )
    .filter(([name]) => isNamedMerchant(name))
    .map(([name, data]) => ({
      name: name.length > 12 ? name.substring(0, 12) + "…" : name,
      fullName: name,
      value: (data.count || 0) * (data.avg_amount || 0),
    }))
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value);

  const topMerchants = merchantData.slice(0, 5);
  const otherValue = merchantData.slice(5).reduce((s, m) => s + m.value, 0);
  const pieData =
    otherValue > 0
      ? [
          ...topMerchants,
          { name: "Others", fullName: "Others", value: otherValue },
        ]
      : topMerchants;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
      {/* Balance History — full width */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100 lg:col-span-2">
        <h3 className="font-bold text-slate-800 text-base mb-5">
          Balance History
        </h3>
        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={balanceData}>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="#e2e8f0"
              />
              <XAxis
                dataKey="date"
                tickFormatter={fmtAxisDate}
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                axisLine={false}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k`}
                width={52}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: "8px",
                  border: "none",
                  boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                  fontSize: 13,
                }}
                labelFormatter={fmtAxisDate}
                formatter={(val: number) => [inr(val), "Balance"]}
              />
              <Line
                type="monotone"
                dataKey="balance"
                stroke="#6366f1"
                strokeWidth={2.5}
                dot={false}
                activeDot={{
                  r: 5,
                  fill: "#6366f1",
                  stroke: "#fff",
                  strokeWidth: 2,
                }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Cash Flow */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100">
        <h3 className="font-bold text-slate-800 text-base mb-4">Cash Flow</h3>

        {/* Summary stats */}
        <div className="flex gap-5 mb-4">
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wider">
              Income
            </p>
            <p className="text-sm font-bold text-emerald-600">{inr(income)}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wider">
              Expense
            </p>
            <p className="text-sm font-bold text-rose-500">{inr(expense)}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400 uppercase tracking-wider">
              Net
            </p>
            <p
              className={`text-sm font-bold ${net >= 0 ? "text-emerald-600" : "text-rose-500"}`}
            >
              {net >= 0 ? "+" : "−"}
              {inr(Math.abs(net))}
            </p>
          </div>
        </div>

        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={flowData} barCategoryGap="30%">
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="#e2e8f0"
              />
              <XAxis dataKey="name" hide />
              <YAxis
                tick={{ fontSize: 11, fill: "#94a3b8" }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k`}
                width={52}
              />
              <Tooltip
                cursor={{ fill: "rgba(100,116,139,0.05)" }}
                contentStyle={{
                  borderRadius: "8px",
                  border: "none",
                  boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                  fontSize: 13,
                }}
                formatter={(val: number) => [inr(val)]}
              />
              <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
              <Bar
                dataKey="Income"
                fill="#10b981"
                radius={[4, 4, 0, 0]}
                barSize={52}
              />
              <Bar
                dataKey="Expense"
                fill="#f43f5e"
                radius={[4, 4, 0, 0]}
                barSize={52}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top Merchants by Volume */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-slate-100">
        <h3 className="font-bold text-slate-800 text-base mb-4">
          Top Merchants by Volume
        </h3>
        <div className="h-56 w-full relative">
          {pieData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="48%"
                    innerRadius={58}
                    outerRadius={82}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {pieData.map((_, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={COLORS[index % COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(
                      val: number,
                      _name: string,
                      props: { payload: { fullName: string } },
                    ) => [inr(val), props.payload.fullName]}
                    contentStyle={{
                      borderRadius: "8px",
                      border: "none",
                      boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
                      fontSize: 13,
                    }}
                  />
                  <Legend
                    iconType="circle"
                    iconSize={8}
                    wrapperStyle={{ fontSize: 12, paddingTop: 4 }}
                  />
                </PieChart>
              </ResponsiveContainer>
              {/* Center label */}
              <div
                className="absolute inset-0 flex items-center justify-center pointer-events-none"
                style={{ paddingBottom: 24 }}
              >
                <div className="text-center">
                  <p className="text-lg font-bold text-slate-700">
                    {pieData.length}
                  </p>
                  <p className="text-xs text-slate-400 leading-none">
                    merchants
                  </p>
                </div>
              </div>
            </>
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="text-slate-400 text-sm">
                No named merchants detected
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
