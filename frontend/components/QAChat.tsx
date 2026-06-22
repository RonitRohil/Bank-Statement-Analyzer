import React, { useState } from "react";
import { askQuestion } from "../services/api";

interface Props {
  accountNumber?: string;
}

interface QAResult {
  answer: string;
  tool_used: string;
  data_points: number;
}

export default function QAChat({ accountNumber }: Props) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<QAResult | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    try {
      const data = await askQuestion(question.trim(), accountNumber);
      setResult(data);
      setQuestion("");
    } catch {
      setResult({
        answer: "Something went wrong. Please try again.",
        tool_used: "error",
        data_points: 0,
      });
    } finally {
      setLoading(false);
    }
  };

  const isError = result?.tool_used === "error";

  return (
    <div className="bg-white rounded-xl shadow p-6 mt-6">
      <h2 className="text-lg font-semibold mb-1">Ask About Your Transactions</h2>
      <p className="text-sm text-gray-500 mb-4">
        Ask a question in plain English and get an answer based on your stored data.
      </p>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your transactions…"
          disabled={loading}
          className="flex-1 border border-slate-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "…" : "Ask"}
        </button>
      </form>

      {loading && (
        <div className="mt-4 animate-pulse">
          <div className="h-4 bg-slate-200 rounded w-3/4 mb-2" />
          <div className="h-4 bg-slate-200 rounded w-1/2" />
        </div>
      )}

      {result && !loading && (
        <div className="mt-4">
          <div
            className={`rounded-lg px-4 py-3 text-sm leading-relaxed ${
              isError
                ? "bg-amber-50 border border-amber-200 text-amber-800"
                : "bg-indigo-50 border border-indigo-100 text-slate-800"
            }`}
          >
            {result.answer}
          </div>
          {result.data_points > 0 && (
            <p className="text-xs text-gray-400 mt-1 ml-1">
              Based on {result.data_points} transaction{result.data_points !== 1 ? "s" : ""}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
