import React, { useState, useEffect } from "react";
import { Trash2, Loader2, Clock, ChevronDown } from "lucide-react";
import { StoredStatement } from "../types";

interface Props {
  statements: StoredStatement[];
  onLoad: (id: number) => void;
  onDelete: (id: number) => void;
  loading: boolean;
}

const PAGE_SIZE = 10;

export default function HistoryPanel({
  statements,
  onLoad,
  onDelete,
  loading,
}: Props) {
  const [loadingRowId, setLoadingRowId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  useEffect(() => {
    if (!loading && loadingRowId !== null) {
      setLoadingRowId(null);
    }
  }, [loading]);

  const handleLoad = (id: number) => {
    setLoadingRowId(id);
    onLoad(id);
  };

  const handleDeleteConfirm = (id: number) => {
    setConfirmDeleteId(null);
    onDelete(id);
  };

  const visible = statements.slice(0, visibleCount);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-6 mt-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Clock className="w-5 h-5 text-indigo-500" />
          <h2 className="text-lg font-semibold text-slate-800">
            Statement History
          </h2>
        </div>
        <span className="text-xs font-medium bg-indigo-50 text-indigo-600 px-2.5 py-1 rounded-full">
          {statements.length}{" "}
          {statements.length === 1 ? "statement" : "statements"}
        </span>
      </div>

      {statements.length === 0 ? (
        <p className="text-sm text-slate-400 text-center py-6">
          No statements stored yet. Upload with 'Save to history' to build your
          archive.
        </p>
      ) : (
        <>
          <div className="divide-y divide-slate-100">
            {visible.map((s) => (
              <div key={s.id} className="py-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-slate-800 truncate">
                        {s.bank_name ?? "Unknown Bank"}
                      </span>
                      {s.account_holder && (
                        <span className="text-sm text-slate-500 truncate">
                          · {s.account_holder}
                        </span>
                      )}
                      {s.confidence_overall !== null && (
                        <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full">
                          {Math.round(s.confidence_overall * 100)}%
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-400 mt-0.5">
                      {s.period_from && s.period_to
                        ? `${s.period_from} → ${s.period_to}`
                        : "Period unknown"}{" "}
                      · Uploaded {new Date(s.uploaded_at).toLocaleDateString()}
                    </div>

                    {confirmDeleteId === s.id && (
                      <div className="mt-2 flex items-center gap-2 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">
                        <span>
                          Delete this statement? This cannot be undone.
                        </span>
                        <button
                          onClick={() => handleDeleteConfirm(s.id)}
                          className="font-semibold underline ml-1 hover:text-red-800"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          className="font-medium text-slate-500 hover:text-slate-700 ml-1"
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => handleLoad(s.id)}
                      disabled={loadingRowId !== null || loading}
                      className="flex items-center gap-1.5 text-sm font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1.5 rounded-lg transition-colors"
                    >
                      {loadingRowId === s.id && (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      )}
                      Load
                    </button>
                    <button
                      onClick={() =>
                        setConfirmDeleteId(
                          confirmDeleteId === s.id ? null : s.id,
                        )
                      }
                      disabled={loadingRowId !== null}
                      className="p-1.5 text-slate-400 hover:text-red-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg hover:bg-red-50 transition-colors"
                      aria-label="Delete statement"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {visibleCount < statements.length && (
            <button
              onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
              className="mt-4 w-full flex items-center justify-center gap-1.5 text-sm text-slate-500 hover:text-indigo-600 py-2 border border-dashed border-slate-200 rounded-lg hover:border-indigo-300 transition-colors"
            >
              <ChevronDown className="w-4 h-4" />
              Show more ({statements.length - visibleCount} remaining)
            </button>
          )}
        </>
      )}
    </div>
  );
}
