"use client";

import { useEffect, useState } from "react";

type Snapshot = {
  id: number;
  snapshot_date: string;
  asset_name: string;
  balance: string;
};

const ASSETS = ["HDFC", "IDFC", "MF", "Stocks", "US Market", "EPFO"];

function formatDate(iso: string) {
  const d = new Date(iso + "T00:00:00");
  const day = d.getDate();
  const suffix =
    day % 10 === 1 && day !== 11
      ? "st"
      : day % 10 === 2 && day !== 12
      ? "nd"
      : day % 10 === 3 && day !== 13
      ? "rd"
      : "th";
  const month = d.toLocaleString("en-GB", { month: "long" });
  const year = d.getFullYear();
  return `${day}${suffix} ${month} ${year}`;
}

function formatINR(n: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(n);
}

export default function Home() {
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedDate, setExpandedDate] = useState<string | null>(null);

  const [date, setDate] = useState("");
  const [tab, setTab] = useState<"overview" | "history">("overview");
  const [showForm, setShowForm] = useState(false);

  const [balances, setBalances] = useState<Record<string, string>>(
    Object.fromEntries(ASSETS.map((a) => [a, ""]))
  );

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editBalance, setEditBalance] = useState("");
  const [showPercent, setShowPercent] = useState(false);

  const [message, setMessage] = useState<{
    type: "error" | "success" | "confirm";
    text: string;
    onConfirm?: () => void;
  } | null>(null);

  const loadSnapshots = () => {
    fetch("http://localhost:8000/snapshots")
      .then((res) => res.json())
      .then((data) => {
        setSnapshots(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    const today = new Date().toISOString().split("T")[0];
    setDate(today);
    loadSnapshots();
  }, []);

  const showMessage = (type: "error" | "success", text: string, duration = 4000) => {
    setMessage({ type, text });
    if (duration > 0) {
      setTimeout(() => setMessage(null), duration);
    }
  };

  const handleBulk = async (e: React.FormEvent) => {
    e.preventDefault();

    let usdToInr = 84;
    try {
      const rateRes = await fetch("https://api.frankfurter.dev/v2/rate/USD/INR");
      const rateData = await rateRes.json();
      usdToInr = rateData.rate;
    } catch {
      showMessage("error", "Could not fetch exchange rate, using fallback");
    }

    const payloads = ASSETS.map((asset) => {
      let value = balances[asset] || "0";
      if (asset === "US Market" && Number(value) > 0) {
        value = (Number(value) * usdToInr).toFixed(2);
      }
      return {
        snapshot_date: date,
        asset_name: asset,
        balance: value,
      };
    }).filter((p) => Number(p.balance) > 0);

    if (payloads.length === 0) return;

    const res = await fetch("http://localhost:8000/snapshots/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payloads),
    });

    if (res.ok) {
      setBalances(Object.fromEntries(ASSETS.map((a) => [a, ""])));
      loadSnapshots();
      showMessage("success", "Saved successfully");
    } else {
      const err = await res.json();
      showMessage("error", err.detail || "Save failed", 6000);
    }
  };

  const handleDelete = (id: number) => {
    setMessage({
      type: "confirm",
      text: "Delete this snapshot?",
      onConfirm: async () => {
        const res = await fetch(`http://localhost:8000/snapshots/${id}`, { method: "DELETE" });
        if (res.ok) loadSnapshots();
        setMessage(null);
      },
    });
  };

  const handleDeleteDate = (dateStr: string) => {
    setMessage({
      type: "confirm",
      text: `Delete all snapshots for ${dateStr}?`,
      onConfirm: async () => {
        const items = snapshots.filter((s) => s.snapshot_date === dateStr);
        for (const item of items) {
          await fetch(`http://localhost:8000/snapshots/${item.id}`, { method: "DELETE" });
        }
        loadSnapshots();
        setMessage(null);
      },
    });
  };

  const startEdit = (s: Snapshot) => {
    setEditingId(s.id);
    setEditBalance(s.balance);
  };

  const saveEdit = async (id: number) => {
    const res = await fetch(`http://localhost:8000/snapshots/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ balance: editBalance }),
    });
    if (res.ok) {
      setEditingId(null);
      loadSnapshots();
      showMessage("success", "Updated");
    }
  };

  const byDate: Record<string, { total: number; items: Snapshot[] }> = {};
  snapshots.forEach((s) => {
    if (!byDate[s.snapshot_date]) byDate[s.snapshot_date] = { total: 0, items: [] };
    byDate[s.snapshot_date].total += Number(s.balance);
    byDate[s.snapshot_date].items.push(s);
  });

  const sortedDates = Object.keys(byDate).sort().reverse();

  const latestDate = sortedDates[0];
  const previousDate = sortedDates[1];
  const latestTotal = latestDate ? byDate[latestDate].total : 0;
  const previousTotal = previousDate ? byDate[previousDate].total : 0;
  const change = latestTotal - previousTotal;
  const changePercent = previousTotal === 0 ? 0 : (change / previousTotal) * 100;

  if (loading) return <p className="p-8">Loading...</p>;

  return (
    <main className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Wealth Tracker</h1>

      <div className="flex gap-4 mb-6 border-b">
        <button
          onClick={() => setTab("overview")}
          className={`pb-2 ${tab === "overview" ? "border-b-2 border-black font-medium" : "text-gray-500"}`}
        >
          Overview
        </button>
        <button
          onClick={() => setTab("history")}
          className={`pb-2 ${tab === "history" ? "border-b-2 border-black font-medium" : "text-gray-500"}`}
        >
          History
        </button>
      </div>

      <div className="h-12 mb-4">
        {message && (
          <div
            className={`h-full px-4 flex justify-between items-center rounded border text-sm ${
              message.type === "error"
                ? "bg-red-50 border-red-200 text-red-800"
                : message.type === "success"
                ? "bg-green-50 border-green-200 text-green-800"
                : "bg-amber-50 border-amber-200 text-amber-800"
            }`}
          >
            <span>{message.text}</span>
            <div className="flex items-center gap-2">
              {message.type === "confirm" && message.onConfirm && (
                <>
                  <button onClick={message.onConfirm} className="bg-red-600 text-white px-3 py-1 rounded text-xs">
                    Yes
                  </button>
                  <button onClick={() => setMessage(null)} className="bg-gray-200 px-3 py-1 rounded text-xs">
                    Cancel
                  </button>
                </>
              )}
              {message.type !== "confirm" && (
                <button onClick={() => setMessage(null)} className="text-current opacity-60 hover:opacity-100 text-lg leading-none">
                  ×
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {tab === "overview" && (
        <>
          {latestDate && (
            <div className="mb-6 p-4 border rounded bg-gray-50 flex justify-between items-center">
              <div>
                <div className="text-sm text-gray-600">Net worth as of {formatDate(latestDate)}</div>
                <div className="text-3xl font-semibold mt-1">
                  {formatINR(latestTotal)}
                  <span
                    className={`ml-3 text-lg font-normal ${
                      (showPercent ? changePercent : change) > 0
                        ? "text-green-600"
                        : (showPercent ? changePercent : change) < 0
                        ? "text-red-600"
                        : "text-gray-500"
                    }`}
                  >
                    ({showPercent
                      ? `${changePercent > 0 ? "+" : ""}${changePercent.toFixed(1)}%`
                      : `${change > 0 ? "+" : ""}${formatINR(change)}`})
                  </span>
                </div>
              </div>
              <button
                onClick={() => setShowPercent((p) => !p)}
                className="text-sm text-gray-600 hover:text-black underline"
              >
                Change ({showPercent ? "%" : "₹"})
              </button>
            </div>
          )}

          <div className="mb-8">
            <button
              onClick={() => setShowForm((s) => !s)}
              className="text-sm text-gray-600 underline mb-2"
            >
              {showForm ? "Hide form" : "Add snapshot"}
            </button>

            {showForm && (
              <form onSubmit={handleBulk} className="border p-4 rounded space-y-3">
                <div>
                  <label className="block text-sm">Date</label>
                  <input
                    type="date"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                    className="border p-2 w-full rounded"
                    required
                  />
                </div>

                {ASSETS.map((asset) => (
                  <div key={asset} className="flex items-center gap-3">
                    <label className="w-28 text-sm">
                      {asset === "US Market" ? "US Market ($)" : asset}
                    </label>
                    <input
                      type="number"
                      step="0.01"
                      placeholder="0"
                      value={balances[asset]}
                      onChange={(e) =>
                        setBalances((prev) => ({ ...prev, [asset]: e.target.value }))
                      }
                      className="border p-2 flex-1 rounded"
                    />
                  </div>
                ))}

                <button type="submit" className="bg-black text-white px-4 py-2 rounded mt-2">
                  Save All
                </button>
              </form>
            )}
          </div>

          <div className="border border-dashed rounded p-8 text-center text-gray-400">
            Graphs and visuals will go here
          </div>
        </>
      )}

      {tab === "history" && (
        <>
          {sortedDates.length === 0 ? (
            <p>No snapshots yet.</p>
          ) : (
            <ul className="space-y-2">
              {sortedDates.map((d) => {
                const group = byDate[d];
                const isOpen = expandedDate === d;
                return (
                  <li key={d} className="border rounded">
                    <div className="flex items-center">
                      <button
                        onClick={() => setExpandedDate(isOpen ? null : d)}
                        className="flex-1 p-3 flex justify-between items-center text-left"
                      >
                        <span className="font-medium">{formatDate(d)}</span>
                        <span className="font-mono">{formatINR(group.total)}</span>
                      </button>
                      <button
                        onClick={() => handleDeleteDate(d)}
                        className="pr-3 text-red-600 text-sm"
                      >
                        Delete date
                      </button>
                    </div>

                    {isOpen && (
                      <ul className="border-t px-3 pb-3 space-y-1 text-sm">
                        {group.items.map((s) => (
                          <li key={s.id} className="flex justify-between items-center py-1">
                            <span>{s.asset_name}</span>
                            <div className="flex items-center gap-3">
                              {editingId === s.id ? (
                                <>
                                  <input
                                    type="number"
                                    step="0.01"
                                    value={editBalance}
                                    onChange={(e) => setEditBalance(e.target.value)}
                                    className="border p-1 w-24 rounded"
                                  />
                                  <button onClick={() => saveEdit(s.id)} className="text-green-700 text-xs">
                                    Save
                                  </button>
                                  <button onClick={() => setEditingId(null)} className="text-gray-500 text-xs">
                                    Cancel
                                  </button>
                                </>
                              ) : (
                                <>
                                  <span className="font-mono">{formatINR(Number(s.balance))}</span>
                                  <button onClick={() => startEdit(s)} className="text-blue-600 text-xs">
                                    Edit
                                  </button>
                                  <button onClick={() => handleDelete(s.id)} className="text-red-600 text-xs">
                                    Delete
                                  </button>
                                </>
                              )}
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}
    </main>
  );
}