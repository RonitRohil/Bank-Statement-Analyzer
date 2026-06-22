interface ConfirmedRecurring {
  merchant: string;
  statement_count: number;
  avg_amount: number;
  last_seen: string | null;
}

interface Props {
  subscriptions: ConfirmedRecurring[];
}

export default function SubscriptionsCard({ subscriptions }: Props) {
  if (!subscriptions.length) return null;

  const monthlyTotal = subscriptions.reduce((sum, s) => sum + s.avg_amount, 0);

  return (
    <div className="bg-white rounded-xl shadow p-6 mt-6">
      <h2 className="text-lg font-semibold mb-1">Confirmed Subscriptions</h2>
      <p className="text-sm text-gray-500 mb-4">
        Recurring charges detected across multiple statements · Est. ₹{monthlyTotal.toLocaleString("en-IN")}/mo
      </p>
      <div className="divide-y">
        {subscriptions.map((s) => (
          <div key={s.merchant} className="flex justify-between items-center py-2">
            <div>
              <span className="font-medium">{s.merchant}</span>
              <span className="text-xs text-gray-400 ml-2">
                {s.statement_count} statements
              </span>
            </div>
            <span className="text-sm font-semibold text-gray-700">
              ~₹{s.avg_amount.toLocaleString("en-IN")}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
