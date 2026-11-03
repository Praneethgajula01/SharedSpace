// src/components/SurvivalChart.jsx — Weibull survival curve S(t) visualization

import { useState, useEffect } from "react";
import { getSurvivalCurve } from "../api/client";

export default function SurvivalChart({ gangId, items }) {
  const [selectedItemId, setSelectedItemId] = useState(items[0]?.id || null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedItemId && items.length > 0) {
      setSelectedItemId(items[0].id);
    }
  }, [items, selectedItemId]);

  useEffect(() => {
    if (!selectedItemId) return;
    async function load() {
      setLoading(true);
      try {
        const res = await getSurvivalCurve(gangId, selectedItemId);
        setData(res.data);
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [gangId, selectedItemId]);

  if (items.length === 0) {
    return (
      <div className="card" style={{ textAlign: "center", color: "var(--muted)", padding: 40 }}>
        Add an item first to see its Weibull Survival Curve S(t).
      </div>
    );
  }

  // Render clean SVG chart so we don't depend on heavy bundle sizes
  const width = 600;
  const height = 260;
  const pad = 40;

  let pathD = "";
  let elapsedX = null;
  let maxT = 10;

  if (data && data.curve.length > 0) {
    maxT = data.curve[data.curve.length - 1].t || 10;
    const pts = data.curve.map((pt) => {
      const x = pad + (pt.t / maxT) * (width - pad * 2);
      const y = pad + (1 - pt.survival) * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    pathD = "M " + pts.join(" L ");
    elapsedX = pad + Math.min(1, data.elapsed_days / maxT) * (width - pad * 2);
  }

  return (
    <div className="card">
      <div className="flex justify-between items-center" style={{ marginBottom: 16 }}>
        <div>
          <h3>Weibull Survival Curve S(t)</h3>
          <p style={{ color: "var(--muted)", fontSize: 13 }}>
            Probability that the item is still in stock after <em>t</em> days
          </p>
        </div>
        <select
          style={{ width: 180 }}
          value={selectedItemId || ""}
          onChange={(e) => setSelectedItemId(Number(e.target.value))}
        >
          {items.map((it) => (
            <option key={it.id} value={it.id}>
              {it.name}
            </option>
          ))}
        </select>
      </div>

      {loading && <div style={{ padding: 40, textAlign: "center" }}><span className="spinner" /></div>}

      {!loading && data && (
        <div>
          <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", background: "var(--surface2)", borderRadius: 8 }}>
            {/* Axes */}
            <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke="var(--border)" strokeWidth="1" />
            <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="var(--border)" strokeWidth="1" />

            {/* Y-axis labels */}
            <text x={8} y={pad + 4} fill="var(--muted)" fontSize="10">100%</text>
            <text x={14} y={(height / 2) + 4} fill="var(--muted)" fontSize="10">50%</text>
            <text x={20} y={height - pad + 4} fill="var(--muted)" fontSize="10">0%</text>

            {/* X-axis labels */}
            <text x={pad} y={height - 12} fill="var(--muted)" fontSize="10">0d</text>
            <text x={width / 2} y={height - 12} fill="var(--muted)" fontSize="10">{(maxT / 2).toFixed(1)}d</text>
            <text x={width - pad - 20} y={height - 12} fill="var(--muted)" fontSize="10">{maxT.toFixed(1)}d</text>

            {/* Current elapsed marker */}
            {elapsedX && (
              <>
                <line
                  x1={elapsedX}
                  y1={pad}
                  x2={elapsedX}
                  y2={height - pad}
                  stroke="var(--warn)"
                  strokeDasharray="4 4"
                  strokeWidth="1.5"
                />
                <text x={elapsedX + 5} y={pad + 14} fill="var(--warn)" fontSize="10">
                  Now ({data.elapsed_days}d)
                </text>
              </>
            )}

            {/* Survival curve S(t) */}
            <path d={pathD} fill="none" stroke="var(--accent2)" strokeWidth="2.5" />
          </svg>
        </div>
      )}
    </div>
  );
}

