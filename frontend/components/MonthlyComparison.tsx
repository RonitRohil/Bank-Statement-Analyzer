import React from "react";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { MonthSummary } from "../types";

interface Props {
  months: MonthSummary[];
  accountNumber: string;
}

const MonthlyComparison: React.FC<Props> = ({ months, accountNumber }) => {
  if (!months.length) return null;

  const data = months.map((m) => ({
    name: m.month,
    Income: m.income,
    Expenses: m.expenses,
    Net: m.net,
  }));

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 mt-6">
      <h2 className="text-lg font-semibold text-slate-800 mb-1">
        Month-over-Month
      </h2>
      <p className="text-sm text-slate-500 mb-4">Account: {accountNumber}</p>

      {months.length === 1 && (
        <p className="text-xs text-amber-600 mb-3">
          Upload more statements to see trends. Showing single-month data.
        </p>
      )}

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data}>
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis
            tick={{ fontSize: 12 }}
            tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip
            formatter={(v: number) => `₹${v.toLocaleString("en-IN")}`}
            contentStyle={{
              borderRadius: "8px",
              border: "none",
              boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
              fontSize: 13,
            }}
          />
          <Legend />
          <Bar dataKey="Income" fill="#4ade80" radius={[4, 4, 0, 0]} />
          <Bar dataKey="Expenses" fill="#f87171" radius={[4, 4, 0, 0]} />
          <Line
            type="monotone"
            dataKey="Net"
            stroke="#6366f1"
            strokeWidth={2}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
        {months.slice(-4).map((m) => (
          <div key={m.month} className="rounded-lg bg-gray-50 p-3 text-center">
            <div className="text-xs text-gray-500">{m.month}</div>
            <div className="font-semibold text-sm">
              ₹{m.expenses.toLocaleString("en-IN")}
            </div>
            {m.delta_expenses_pct !== null && (
              <div
                className={`text-xs ${m.delta_expenses_pct > 0 ? "text-red-500" : "text-green-600"}`}
              >
                {m.delta_expenses_pct > 0 ? "▲" : "▼"}{" "}
                {Math.abs(m.delta_expenses_pct)}%
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default MonthlyComparison;
