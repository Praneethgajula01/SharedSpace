// src/components/ExpenseLedger.jsx — Professional Split Bills & Settlement View

import { useState, useEffect } from "react";
import { getBalances, getSettlements } from "../api/client";

export default function ExpenseLedger({ gangId }) {
  const [balances, setBalances] = useState([]);
  const [settlements, setSettlements] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const [bRes, sRes] = await Promise.all([
          getBalances(gangId),
          getSettlements(gangId),
        ]);
        setBalances(bRes.data);
        setSettlements(sRes.data);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [gangId]);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 48 }}>
        <span className="spinner" />
      </div>
    );
  }

  if (balances.length === 0) {
    return (
      <div
        className="card"
        style={{ textAlign: "center", color: "var(--muted)", padding: "48px 24px" }}
      >
        <div style={{ fontWeight: 600, color: "var(--text)", marginBottom: 4 }}>
          No purchase history recorded yet
        </div>
        <p style={{ fontSize: 13 }}>
          Once orders are placed or logged, roommate balances and settlements will appear here.
        </p>
      </div>
    );
  }

  return (
    <div style={styles.grid}>
      {/* Net Balances */}
      <div className="card">
        <h3 style={styles.sectionTitle}>Net Balances</h3>
        <p style={styles.sectionSub}>
          Total paid minus equal share of all Gang grocery purchases.
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {balances.map((b) => {
            const isPos = b.net_amount > 0;
            const isNeg = b.net_amount < 0;
            return (
              <div key={b.user_id} style={styles.row}>
                <span style={{ fontWeight: 500, color: "var(--text)" }}>
                  {b.user_name}
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span
                    style={{
                      color: isPos
                        ? "var(--accent2)"
                        : isNeg
                        ? "var(--danger)"
                        : "var(--muted)",
                      fontWeight: 600,
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    {isPos ? "+" : ""}₹{b.net_amount.toFixed(2)}
                  </span>
                  <span className="tag tag-purple" style={{ fontSize: 11 }}>
                    {isPos ? "Gets back" : isNeg ? "Owes" : "Settled"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Simplified Settlements */}
      <div className="card">
        <h3 style={styles.sectionTitle}>How to Settle Up</h3>
        <p style={styles.sectionSub}>
          Minimum direct transfers required to clear all Gang balances.
        </p>

        {settlements.length === 0 ? (
          <div
            style={{
              padding: "20px 16px",
              background: "var(--surface2)",
              borderRadius: 6,
              color: "var(--muted)",
              textAlign: "center",
              fontSize: 13,
            }}
          >
            All roommate balances are settled.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {settlements.map((s, i) => (
              <div key={i} style={styles.row}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <strong style={{ color: "var(--text)" }}>{s.debtor}</strong>
                  <span style={{ color: "var(--muted)", fontSize: 12.5 }}>pays</span>
                  <strong style={{ color: "var(--text)" }}>{s.creditor}</strong>
                </div>
                <strong
                  style={{
                    color: "var(--accent)",
                    fontSize: 14.5,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  ₹{s.amount.toFixed(2)}
                </strong>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const styles = {
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: 16,
  },
  sectionTitle: { fontSize: 15.5, fontWeight: 600, marginBottom: 2 },
  sectionSub: { fontSize: 12.5, color: "var(--muted)", marginBottom: 16 },
  row: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "11px 14px",
    background: "var(--surface2)",
    borderRadius: 6,
    border: "1px solid var(--border)",
  },
};
