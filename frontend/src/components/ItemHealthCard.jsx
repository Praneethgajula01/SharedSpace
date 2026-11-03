// src/components/ItemHealthCard.jsx — Professional item card

import { useState, useEffect, useCallback } from "react";
import { getItemStats, recordPurchase } from "../api/client";

export default function ItemHealthCard({ item, gangId, buyerId, onRequestCreated }) {
  const [stats, setStats] = useState(null);
  const [buying, setBuying] = useState(false);
  const [msg, setMsg] = useState("");

  const fetchStats = useCallback(async () => {
    try {
      const res = await getItemStats(gangId, item.id);
      setStats(res.data);
    } catch {
      // ignore
    }
  }, [gangId, item.id]);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  async function handleRecordPurchase() {
    setBuying(true);
    setMsg("");
    try {
      await recordPurchase(gangId, item.id, item.price || 50, buyerId || null);
      setMsg("Added to expenses");
      fetchStats();
      onRequestCreated?.();
    } catch {
      setMsg("Could not record");
    } finally {
      setBuying(false);
    }
  }

  const pct = stats ? Math.round(stats.best_estimate * 100) : 0;
  let statusBadge = <span className="tag tag-green">Stocked</span>;
  if (pct >= 70) {
    statusBadge = <span className="tag tag-red">Almost Empty</span>;
  } else if (pct >= 40) {
    statusBadge = <span className="tag tag-yellow">Running Low</span>;
  }

  return (
    <div className="card" style={styles.card}>
      <div>
        <div style={styles.header}>
          <div style={{ fontWeight: 600, fontSize: 15.5, color: "var(--text)" }}>
            {item.name}
          </div>
          {statusBadge}
        </div>

        <div style={styles.metaGrid}>
          <div>
            <span className="label" style={{ marginBottom: 2 }}>Est. Price</span>
            <span style={{ fontWeight: 500, color: "var(--text-secondary)" }}>
              ₹{item.price} / {item.unit}
            </span>
          </div>
          <div>
            <span className="label" style={{ marginBottom: 2 }}>Typical Cycle</span>
            <span style={{ fontWeight: 500, color: "var(--text-secondary)" }}>
              Every {item.declared_interval_days} days
            </span>
          </div>
          <div>
            <span className="label" style={{ marginBottom: 2 }}>Last Bought</span>
            <span style={{ fontWeight: 500, color: "var(--text-secondary)" }}>
              {stats ? `${stats.elapsed_days}d ago` : "—"}
            </span>
          </div>
        </div>
      </div>

      {msg && (
        <p style={{ fontSize: 12.5, color: "var(--accent2)", marginTop: 10, fontWeight: 500 }}>
          {msg}
        </p>
      )}

      <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
        <button
          className="btn-ghost w-full"
          onClick={handleRecordPurchase}
          disabled={buying}
        >
          {buying ? "Saving..." : "I Bought This Offline"}
        </button>
      </div>
    </div>
  );
}

const styles = {
  card: {
    display: "flex",
    flexDirection: "column",
    justifyContent: "space-between",
    padding: "18px 20px",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 8,
    marginBottom: 14,
  },
  metaGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: 8,
    background: "var(--surface2)",
    padding: "10px 12px",
    borderRadius: 6,
    fontSize: 12.5,
  },
};
