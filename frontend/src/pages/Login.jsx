// src/pages/Login.jsx — Real Instagram-Style Log In & Sign Up Portal

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { loginUser, signupUser } from "../api/client";

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("login"); // 'login' | 'signup'
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");

    if (!email.trim() || !password.trim()) {
      setError("Please enter your email and password.");
      return;
    }
    if (mode === "signup" && !name.trim()) {
      setError("Please enter your full name to sign up.");
      return;
    }

    setLoading(true);
    try {
      let res;
      if (mode === "signup") {
        res = await signupUser(name.trim(), email.trim(), password);
      } else {
        res = await loginUser(email.trim(), password);
      }

      // Clear any legacy localStorage gang lists and store authenticated user
      localStorage.removeItem("ss_gangs");
      localStorage.setItem("ss_user", JSON.stringify(res.data));
      navigate("/gangs");
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          (mode === "signup" ? "Sign up failed." : "Invalid email or password.")
      );
    } finally {
      setLoading(false);
    }
  }

  function toggleMode() {
    setMode((prev) => (prev === "login" ? "signup" : "login"));
    setError("");
  }

  return (
    <div style={styles.wrapper}>
      <div className="card" style={styles.card}>
        <div style={styles.brandRow}>
          <div style={styles.brandMark}>S</div>
          <span style={styles.brandName}>SharedSpace</span>
          <span className="tag tag-purple" style={{ marginLeft: "auto" }}>
            Hostel Edition
          </span>
        </div>

        <h1 style={styles.title}>
          {mode === "login" ? "Log in to your account" : "Create your account"}
        </h1>
        <p style={styles.sub}>
          {mode === "login"
            ? "Access your personal Gangs, shared groceries, and split bills."
            : "Sign up with your hostel email. If a roommate already added your email to a Gang, it will link automatically."}
        </p>

        <form onSubmit={handleSubmit} style={styles.form}>
          {mode === "signup" && (
            <div>
              <span className="label">Full Name</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Arjun Sharma"
                autoFocus
              />
            </div>
          )}

          <div>
            <span className="label">Email Address</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="arjun@hostel.com"
              autoFocus={mode === "login"}
            />
          </div>

          <div>
            <span className="label">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {error && <p className="error-msg">{error}</p>}

          <button
            className="btn-primary w-full"
            type="submit"
            disabled={loading}
            style={{ padding: "11px 16px", marginTop: 6, fontSize: 14 }}
          >
            {loading ? (
              <span className="spinner" />
            ) : mode === "login" ? (
              "Log In →"
            ) : (
              "Sign Up & Continue →"
            )}
          </button>
        </form>

        <div style={styles.switchBox}>
          {mode === "login" ? (
            <>
              Don't have an account?{" "}
              <button type="button" onClick={toggleMode} style={styles.linkBtn}>
                Sign up
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button type="button" onClick={toggleMode} style={styles.linkBtn}>
                Log in
              </button>
            </>
          )}
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
  switchBox: {
    color: "var(--muted)",
    fontSize: 13.5,
    marginTop: 22,
    paddingTop: 18,
    borderTop: "1px solid var(--border)",
    textAlign: "center",
  },
  linkBtn: {
    background: "none",
    border: "none",
    color: "#a78bfa",
    fontWeight: 700,
    padding: "0 4px",
    fontSize: 13.5,
    cursor: "pointer",
  },
};
