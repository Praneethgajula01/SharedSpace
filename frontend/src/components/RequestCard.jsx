// src/components/RequestCard.jsx — Clean, professional order request card

import { useState } from "react";
import { respondToRequest } from "../api/client";

export default function RequestCard({ request, gangId, actingMember, onResolved }) {
  const [loading, setLoading] = useState(null);
  const [error, setError] = useState("");

  async function respond(action) {
    if (!actingMember?.id) return;
    setLoading(action);
    setError("");
    try {
      await respondToRequest(gangId, request.id, actingMember.id, action);
      onResolved?.();
    } catch (err) {
      setError(err.response?.data?.detail || "Could not process.");
    } finally {
      setLoading(null);
    }
  }

  const receipt = request.order_receipt;

  // PENDING CARD
  if (request.status === "PENDING") {
    return (
      <div className="card" style={styles.pendingCard}>
        <div style={styles.topRow}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <span className="tag tag-yellow">Running Low</span>
              <span style={{ fontSize: 12, color: "var(--muted)" }}>
                Est. ₹{request.item_price} / {request.item_unit || "unit"}
              </span>
            </div>
            <h3 style={{ fontSize: 17, fontWeight: 600, color: "var(--text)" }}>
              Order {request.item_name}?
            </h3>
            <p style={{ color: "var(--muted)", fontSize: 13.5, marginTop: 3 }}>
              Looks like your gang is about to run out of{" "}
              <strong style={{ color: "var(--text-secondary)" }}>{request.item_name}</strong>.
              Approving this request places one shared order for the Gang.
            </p>
          </div>

          <div style={styles.actions}>
            <button
              className="btn-primary"
              onClick={() => respond("YES")}
              disabled={!!loading}
            >
              {loading === "YES" ? "Ordering..." : "Yes, Order Now"}
            </button>
            <button
              className="btn-ghost"
              onClick={() => respond("SNOOZE")}
              disabled={!!loading}
            >
              {loading === "SNOOZE" ? "..." : "Remind Later"}
            </button>
            <button
              className="btn-ghost"
              onClick={() => respond("NO")}
              disabled={!!loading}
            >
              {loading === "NO" ? "..." : "We Still Have It"}
            </button>
          </div>
        </div>

        {error && <p className="error-msg mt-2">{error}</p>}
      </div>
    );
  }

  // RESOLVED CARD
  return (
    <div className="card" style={{ padding: "14px 20px" }}>
      <div style={styles.resolvedRow}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <strong style={{ fontSize: 14.5, color: "var(--text)" }}>
              {request.item_name}
            </strong>
            {receipt?.order_id && (
              <span
                style={{
                  fontSize: 11.5,
                  fontFamily: "monospace",
                  color: "var(--muted)",
                  background: "var(--surface2)",
                  padding: "1px 6px",
                  borderRadius: 4,
                }}
              >
                {receipt.order_id}
              </span>
            )}
          </div>

          {request.status === "ACCEPTED" && receipt ? (
            <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 3 }}>
              Ordered by <strong style={{ color: "var(--text-secondary)" }}>{receipt.approved_by}</strong>{" "}
              · Total ₹{receipt.total_amount.toFixed(0)} · Arriving by{" "}
              {new Date(receipt.estimated_delivery_time).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
          ) : (
            <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 3 }}>
              Skipped by {request.decided_by_name || "roommate"}
            </div>
          )}
        </div>

        {request.status === "ACCEPTED" ? (
          <span className="tag tag-green">Ordered</span>
        ) : (
          <span className="tag tag-purple">Skipped</span>
        )}
      </div>
    </div>
  );
}

const styles = {
  pendingCard: {
    borderLeft: "3px solid var(--accent)",
    padding: "20px 24px",
  },
  topRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 20,
    flexWrap: "wrap",
  },
  resolvedRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
  },
  actions: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
    flexShrink: 0,
  },
};
