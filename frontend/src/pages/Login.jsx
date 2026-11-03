// src/pages/Login.jsx — Student-Friendly Dark-Glass Sign-In Portal

import { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function Login() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function handleSubmit(e) {
    e.preventDefault();
    if (!name.trim() || !email.trim()) {
      setError("Please enter both your name and email address.");
      return;
    }
    setError("");
    setLoading(true);
    localStorage.setItem(
      "ss_user",
      JSON.stringify({ name: name.trim(), email: email.trim().toLowerCase() })
    );
    setLoading(false);
    navigate("/gangs");
  }

  return (
    <div style={styles.wrapper}>
      <div className="card" style={styles.card}>
        <div style={styles.brandRow}>
          <div style={styles.brandMark}>S</div>
          <span style={styles.brandName}>SharedSpace</span>
          <span className="tag tag-purple" style={{ marginLeft: "auto" }}>Hostel Edition</span>
        </div>

        <h1 style={styles.title}>Jump into your Gang</h1>
        <p style={styles.sub}>
          Smart grocery auto-ordering and instant bill splits for roommates.
        </p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <div>
            <span className="label">Your Name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Arjun"
              autoFocus
            />
          </div>
          <div>
            <span className="label">College / Hostel Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="arjun@hostel.com"
            />
          </div>
          {error && <p className="error-msg">{error}</p>}
          <button
            className="btn-primary w-full"
            type="submit"
            disabled={loading}
            style={{ padding: "11px 16px", marginTop: 6, fontSize: 14 }}
          >
            {loading ? <span className="spinner" /> : "Enter SharedSpace →"}
          </button>
        </form>

        <div style={styles.footer}>
          Zero passwords · Instant Gang sync
        </div>
      </div>
    </div>
  );
}

const styles = {
  wrapper: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
  },
  card: {
    width: "100%",
    maxWidth: 410,
    padding: "36px 32px",
    boxShadow: "var(--shadow)",
    border: "1px solid rgba(139, 92, 246, 0.25)",
  },
  brandRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 24,
  },
  brandMark: {
    width: 34,
    height: 34,
    borderRadius: 10,
    background: "var(--accent-gradient)",
    color: "#ffffff",
    fontWeight: 800,
    fontSize: 16,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 4px 12px rgba(139, 92, 246, 0.4)",
  },
  brandName: {
    fontWeight: 800,
    fontSize: 17,
    color: "var(--text)",
    letterSpacing: "-0.02em",
  },
  title: {
    fontSize: 22,
    fontWeight: 700,
    color: "var(--text)",
    letterSpacing: "-0.02em",
    marginBottom: 6,
  },
  sub: {
    color: "var(--muted)",
    fontSize: 13.5,
    marginBottom: 24,
    lineHeight: 1.5,
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  footer: {
    color: "var(--muted)",
    fontSize: 12,
    marginTop: 24,
    paddingTop: 16,
    borderTop: "1px solid var(--border)",
    textAlign: "center",
  },
};
