// src/pages/GangList.jsx — Database-Backed Personal Gang Directory (Strict Account Isolation)

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getUserGangs, createGang, joinGang } from "../api/client";

export default function GangList() {
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("ss_user") || "null");

  const [gangs, setGangs] = useState([]);
  const [fetching, setFetching] = useState(true);
  const [gangName, setGangName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [joinId, setJoinId] = useState("");
  const [joinError, setJoinError] = useState("");

  const loadMyGangs = useCallback(async () => {
    if (!user?.id) return;
    setFetching(true);
    try {
      const res = await getUserGangs(user.id);
      setGangs(res.data);
    } catch {
      setGangs([]);
    } finally {
      setFetching(false);
    }
  }, [user?.id]);

  useEffect(() => {
    loadMyGangs();
  }, [loadMyGangs]);

  async function handleCreate(e) {
    e.preventDefault();
    if (!gangName.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await createGang(gangName, user.name, user.email);
      const gang = res.data;
      navigate(`/gangs/${gang.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create gang.");
    } finally {
      setLoading(false);
    }
  }

  async function handleJoin() {
    const id = parseInt(joinId);
    if (!id) return;
    setJoinError("");
    try {
      await joinGang(id, user.id);
      navigate(`/gangs/${id}`);
    } catch (err) {
      setJoinError(err.response?.data?.detail || `Could not join Gang #${id}.`);
    }
  }

  function handleLogout() {
    localStorage.removeItem("ss_user");
    localStorage.removeItem("ss_gangs");
    navigate("/");
  }

  return (
    <div style={styles.page}>
      <header style={styles.navbar}>
        <div style={styles.navContainer}>
          <div style={styles.brandRow}>
            <div style={styles.brandMark}>S</div>
            <span style={styles.brandName}>SharedSpace</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <span style={{ fontSize: 13, color: "var(--muted)" }}>
              <strong style={{ color: "var(--text)" }}>{user?.name}</strong> · {user?.email}
            </span>
            <button className="btn-ghost" onClick={handleLogout} style={{ padding: "6px 14px" }}>
              Sign Out
            </button>
          </div>
        </div>
      </header>

      <main style={styles.wrapper}>
        <div style={{ marginBottom: 26 }}>
          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: "-0.02em" }}>
            My Gangs
          </h1>
          <p style={{ color: "var(--muted)", fontSize: 14, marginTop: 4 }}>
            Showing only Gangs linked to your account (<strong>{user?.email}</strong>).
          </p>
        </div>

        {/* Authenticated User's Gangs List */}
        <div style={styles.list}>
          {fetching ? (
            <div style={{ textAlign: "center", padding: 40 }}>
              <span className="spinner" />
            </div>
          ) : gangs.length === 0 ? (
            <div
              className="card"
              style={{
                textAlign: "center",
                color: "var(--muted)",
                padding: "44px 24px",
              }}
            >
              <div
                style={{
                  fontWeight: 700,
                  fontSize: 16,
                  color: "var(--text)",
                  marginBottom: 4,
                }}
              >
                You aren't part of any Gang yet
              </div>
              <p style={{ fontSize: 13.5 }}>
                Create a new Gang below, or enter a Gang ID shared by your roommate to join.
              </p>
            </div>
          ) : (
            gangs.map((g) => (
              <div
                key={g.id}
                className="card"
                style={styles.gangCard}
                onClick={() => navigate(`/gangs/${g.id}`)}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  <div style={styles.gangAvatar}>
                    {g.name.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 16, color: "var(--text)" }}>
                      {g.name}
                    </div>
                    <div style={{ color: "var(--muted)", fontSize: 12.5 }}>
                      Gang ID #{g.id} · {g.members?.length || 1} member(s) ·{" "}
                      {g.items?.length || 0} item(s)
                    </div>
                  </div>
                </div>
                <span className="btn-primary" style={{ padding: "7px 14px", fontSize: 12.5 }}>
                  Open Gang →
                </span>
              </div>
            ))
          )}
        </div>

        {/* Action Cards */}
        <div style={styles.actionsGrid}>
          <div className="card">
            <h3 style={styles.cardTitle}>Create a New Gang</h3>
            <p style={styles.cardSub}>
              Start a shared grocery workspace for your room or hostel floor.
            </p>
            <form onSubmit={handleCreate} style={{ display: "flex", gap: 8 }}>
              <input
                value={gangName}
                onChange={(e) => setGangName(e.target.value)}
                placeholder="e.g. 404 Found, Wing B Boys"
                style={{ flex: 1 }}
              />
              <button className="btn-primary" type="submit" disabled={loading}>
                {loading ? <span className="spinner" /> : "Create"}
              </button>
            </form>
            {error && <p className="error-msg mt-2">{error}</p>}
          </div>

          <div className="card">
            <h3 style={styles.cardTitle}>Join by Gang ID</h3>
            <p style={styles.cardSub}>
              Have a Gang ID from your roommate? Enter it to join and link it to your account.
            </p>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                type="number"
                value={joinId}
                onChange={(e) => setJoinId(e.target.value)}
                placeholder="Enter Gang ID"
                style={{ flex: 1 }}
              />
              <button className="btn-ghost" onClick={handleJoin}>
                Join Gang
              </button>
            </div>
            {joinError && <p className="error-msg mt-2">{joinError}</p>}
          </div>
        </div>
      </main>
    </div>
  );
}

const styles = {
  page: { minHeight: "100vh" },
  navbar: {
    background: "rgba(9, 13, 22, 0.8)",
    backdropFilter: "blur(14px)",
    borderBottom: "1px solid var(--border)",
    height: 60,
    display: "flex",
    alignItems: "center",
    position: "sticky",
    top: 0,
    zIndex: 20,
  },
  navContainer: {
    width: "100%",
    maxWidth: 900,
    margin: "0 auto",
    padding: "0 20px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  brandRow: { display: "flex", alignItems: "center", gap: 10 },
  brandMark: {
    width: 30,
    height: 30,
    borderRadius: 8,
    background: "var(--accent-gradient)",
    color: "#ffffff",
    fontWeight: 800,
    fontSize: 15,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 2px 10px rgba(139, 92, 246, 0.4)",
  },
  brandName: {
    fontWeight: 800,
    fontSize: 16,
    color: "var(--text)",
    letterSpacing: "-0.02em",
  },
  wrapper: { maxWidth: 900, margin: "0 auto", padding: "36px 20px" },
  list: { display: "flex", flexDirection: "column", gap: 12, marginBottom: 28 },
  gangCard: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    cursor: "pointer",
    padding: "18px 22px",
    border: "1px solid rgba(139, 92, 246, 0.22)",
  },
  gangAvatar: {
    width: 42,
    height: 42,
    borderRadius: 10,
    background:
      "linear-gradient(135deg, rgba(139, 92, 246, 0.25), rgba(16, 185, 129, 0.2))",
    border: "1px solid rgba(139, 92, 246, 0.4)",
    color: "#ffffff",
    fontWeight: 800,
    fontSize: 17,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  actionsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
    gap: 16,
  },
  cardTitle: { fontSize: 16, fontWeight: 700, marginBottom: 4 },
  cardSub: { fontSize: 13, color: "var(--muted)", marginBottom: 16 },
};
