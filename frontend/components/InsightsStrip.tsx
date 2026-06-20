import React from "react";
import { Lightbulb } from "lucide-react";

interface InsightsStripProps {
  insights: string[];
}

export const InsightsStrip: React.FC<InsightsStripProps> = ({ insights }) => {
  if (!insights || insights.length === 0) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-5 mb-6">
      <div className="flex items-center gap-2 mb-3">
        <Lightbulb className="w-4 h-4 text-indigo-500" />
        <h3 className="font-semibold text-slate-700 text-sm uppercase tracking-wide">
          Quick Insights
        </h3>
      </div>
      <div className="flex flex-wrap gap-2">
        {insights.map((insight, i) => (
          <span
            key={i}
            className="inline-flex items-center px-3 py-1.5 rounded-full text-sm font-medium bg-indigo-50 text-indigo-700 border border-indigo-100"
          >
            {insight}
          </span>
        ))}
      </div>
    </div>
  );
};
