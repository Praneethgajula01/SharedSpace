// src/pages/GangDashboard.jsx — Professional Gang Workspace

import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getGang,
  getActiveRequests,
  getRequestHistory,
  addMember,
  addItem,
  checkAndTrigger,
} from "../api/client";
import RequestCard from "../components/RequestCard";
import ItemHealthCard from "../components/ItemHealthCard";
import ExpenseLedger from "../components/ExpenseLedger";

export default function GangDashboard() {
  const { gangId } = useParams();
  const navigate = useNavigate();
  const user = JSON.parse(localStorage.getItem("ss_user") || "null");

  const [gang, setGang] = useState(null);
  const [requests, setRequests] = useState([]);
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState("requests"); // 'requests' | 'items' | 'expenses'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedMemberId, setSelectedMemberId] = useState(null);

  // Add Member form
  const [memberName, setMemberName] = useState("");
  const [memberEmail, setMemberEmail] = useState("");
  const [memberMsg, setMemberMsg] = useState("");

  // Add Item form
  const [itemName, setItemName] = useState("");
  const [itemInterval, setItemInterval] = useState("3");
  const [itemUnit, setItemUnit] = useState("pack");
  const [itemPrice, setItemPrice] = useState("50");
  const [itemMsg, setItemMsg] = useState("");

  const loadData = useCallback(async () => {
    try {
      await checkAndTrigger(gangId).catch(() => {});

      const [gRes, rRes, hRes] = await Promise.all([
        getGang(gangId),
        getActiveRequests(gangId),
        getRequestHistory(gangId),
      ]);
      setGang(gRes.data);
      setRequests(rRes.data);
      setHistory(hRes.data);
      setError("");

      setSelectedMemberId((prev) => {
        if (prev && gRes.data.members.some((m) => m.id === prev)) return prev;
        const match = gRes.data.members.find(
          (m) => m.email.toLowerCase() === user?.email?.toLowerCase()
        );
        return match ? match.id : gRes.data.members[0]?.id || null;
      });
    } catch (err) {
      setError(err.response?.data?.detail || "Could not load gang.");
    } finally {
      setLoading(false);
    }
  }, [gangId, user?.email]);

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 6000);
    return () => clearInterval(timer);
  }, [loadData]);

  const actingMember =
    gang?.members?.find((m) => m.id === Number(selectedMemberId)) ||
    gang?.members?.[0];

  async function handleAddMember(e) {
    e.preventDefault();
    if (!memberName.trim() || !memberEmail.trim()) return;
    setMemberMsg("");
    try {
      await addMember(gangId, memberName, memberEmail);
      setMemberName("");
      setMemberEmail("");
      setMemberMsg("Roommate added");
      loadData();
    } catch (err) {
      setMemberMsg(err.response?.data?.detail || "Error adding roommate.");
    }
  }

  async function handleAddItem(e) {
    e.preventDefault();
    if (!itemName.trim()) return;
    setItemMsg("");
    try {
      await addItem(
        gangId,
        itemName,
        parseFloat(itemInterval) || 3.0,
        itemUnit || "pack",
        parseFloat(itemPrice) || 50.0
      );
      setItemName("");
      setItemMsg("Item added");
      loadData();
    } catch (err) {
      setItemMsg(err.response?.data?.detail || "Error adding item.");
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 80 }}>
        <span className="spinner" />
      </div>
    );
  }

  if (error || !gang) {
    return (
      <div
        style={{ maxWidth: 480, margin: "60px auto", textAlign: "center" }}
        className="card"
      >
        <h2 style={{ fontSize: 18, fontWeight: 600 }}>{error || "Gang not found"}</h2>
        <button className="btn-primary mt-4" onClick={() => navigate("/gangs")}>
          ← Switch Gang
        </button>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      {/* Top Navbar */}
      <header style={styles.navbar}>
        <div style={styles.navContainer}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={styles.brandMark}>S</div>
            <span style={{ fontWeight: 600, fontSize: 15 }}>SharedSpace</span>
            <span style={{ color: "var(--border-strong)" }}>/</span>
            <span style={{ fontWeight: 500, color: "var(--text-secondary)" }}>
              {gang.name}
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 12.5, color: "var(--muted)" }}>
                Logged in as:
              </span>
              <select
                value={actingMember?.id || ""}
                onChange={(e) => setSelectedMemberId(Number(e.target.value))}
                style={{
                  width: "auto",
                  minWidth: 140,
                  padding: "6px 10px",
                  fontWeight: 500,
                }}
              >
                {gang.members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>
            <button
              className="btn-ghost"
              onClick={() => navigate("/gangs")}
              style={{ padding: "6px 12px" }}
            >
              Switch Gang
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main style={styles.wrapper}>
        {/* Workspace Header */}
        <div style={styles.headerBlock}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>
              {gang.name}
            </h1>
            <p style={{ color: "var(--muted)", fontSize: 13.5, marginTop: 2 }}>
              Gang ID #{gang.id} · Roommates: {gang.members.map((m) => m.name).join(", ")}
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div style={styles.tabBar}>
          <TabButton active={tab === "requests"} onClick={() => setTab("requests")}>
            Order Requests
            {requests.length > 0 && (
              <span style={styles.badgeCount}>{requests.length}</span>
            )}
          </TabButton>
          <TabButton active={tab === "items"} onClick={() => setTab("items")}>
            Groceries & Roommates
          </TabButton>
          <TabButton active={tab === "expenses"} onClick={() => setTab("expenses")}>
            Split Bills
          </TabButton>
        </div>

        {/* TAB 1: ORDER REQUESTS */}
        {tab === "requests" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {requests.length === 0 ? (
              <div
                className="card"
                style={{
                  textAlign: "center",
                  padding: "48px 24px",
                  color: "var(--muted)",
                }}
              >
                <h3 style={{ color: "var(--text)", fontSize: 16, fontWeight: 600, marginBottom: 4 }}>
                  All stocked up
                </h3>
                <p style={{ fontSize: 13.5 }}>
                  When an item is about to run out, it will appear here so any roommate can approve the order.
                </p>
              </div>
            ) : (
              requests.map((r) => (
                <RequestCard
                  key={r.id}
                  request={r}
                  gangId={gang.id}
                  actingMember={actingMember}
                  onResolved={loadData}
                />
              ))
            )}

            {history.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <div className="label" style={{ marginBottom: 10 }}>
                  Past Orders
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {history.map((r) => (
                    <RequestCard
                      key={r.id}
                      request={r}
                      gangId={gang.id}
                      actingMember={actingMember}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: GROCERIES & ROOMMATES */}
        {tab === "items" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            <div style={styles.grid}>
              {gang.items.map((item) => (
                <ItemHealthCard
                  key={item.id}
                  item={item}
                  gangId={gang.id}
                  buyerId={actingMember?.id}
                  onRequestCreated={loadData}
                />
              ))}
            </div>

            <div style={styles.formsGrid}>
              {/* Add Shared Grocery */}
              <div className="card">
                <h3 style={{ fontSize: 15.5, fontWeight: 600, marginBottom: 4 }}>
                  Add Shared Grocery
                </h3>
                <p style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 16 }}>
                  Register a recurring grocery item tracked for the Gang.
                </p>
                <form
                  onSubmit={handleAddItem}
                  style={{ display: "flex", flexDirection: "column", gap: 12 }}
                >
                  <div>
                    <span className="label">Item Name</span>
                    <input
                      value={itemName}
                      onChange={(e) => setItemName(e.target.value)}
                      placeholder="Milk, Bread, Eggs"
                    />
                  </div>
                  <div style={{ display: "flex", gap: 10 }}>
                    <div style={{ flex: 1 }}>
                      <span className="label">Cycle (Days)</span>
                      <input
                        type="number"
                        step="1"
                        value={itemInterval}
                        onChange={(e) => setItemInterval(e.target.value)}
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <span className="label">Unit</span>
                      <input
                        value={itemUnit}
                        onChange={(e) => setItemUnit(e.target.value)}
                        placeholder="pack / litre"
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <span className="label">Est. Price (₹)</span>
                      <input
                        type="number"
                        value={itemPrice}
                        onChange={(e) => setItemPrice(e.target.value)}
                      />
                    </div>
                  </div>
                  <button className="btn-primary" type="submit" style={{ marginTop: 4 }}>
                    Add Item
                  </button>
                  {itemMsg && (
                    <p style={{ fontSize: 12.5, color: "var(--accent2)", fontWeight: 500 }}>
                      {itemMsg}
                    </p>
                  )}
                </form>
              </div>

              {/* Add Roommate */}
              <div className="card">
                <h3 style={{ fontSize: 15.5, fontWeight: 600, marginBottom: 4 }}>
                  Add Roommate
                </h3>
                <p style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 16 }}>
                  Enrol a roommate to approve orders and share expenses.
                </p>
                <form
                  onSubmit={handleAddMember}
                  style={{ display: "flex", flexDirection: "column", gap: 12 }}
                >
                  <div>
                    <span className="label">Roommate Name</span>
                    <input
                      value={memberName}
                      onChange={(e) => setMemberName(e.target.value)}
                      placeholder="Rohan Verma"
                    />
                  </div>
                  <div>
                    <span className="label">Roommate Email</span>
                    <input
                      type="email"
                      value={memberEmail}
                      onChange={(e) => setMemberEmail(e.target.value)}
                      placeholder="rohan@hostel.com"
                    />
                  </div>
                  <button className="btn-primary" type="submit" style={{ marginTop: 4 }}>
                    Add Roommate
                  </button>
                  {memberMsg && (
                    <p style={{ fontSize: 12.5, color: "var(--accent2)", fontWeight: 500 }}>
                      {memberMsg}
                    </p>
                  )}
                </form>
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: SPLIT BILLS */}
        {tab === "expenses" && <ExpenseLedger gangId={gang.id} />}
      </main>
    </div>
  );
}

function TabButton({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        background: active ? "var(--accent-gradient)" : "rgba(30, 41, 59, 0.55)",
        color: active ? "#ffffff" : "var(--text-secondary)",
        border: active ? "1px solid transparent" : "1px solid var(--border)",
        borderRadius: 10,
        padding: "10px 18px",
        fontWeight: active ? 700 : 600,
        fontSize: 13.5,
        boxShadow: active ? "0 4px 14px rgba(139, 92, 246, 0.35)" : "none",
      }}
    >
      {children}
    </button>
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
    maxWidth: 940,
    margin: "0 auto",
    padding: "0 20px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 12,
  },
  brandMark: {
    width: 28,
    height: 28,
    borderRadius: 8,
    background: "var(--accent-gradient)",
    color: "#ffffff",
    fontWeight: 800,
    fontSize: 14,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    boxShadow: "0 2px 10px rgba(139, 92, 246, 0.4)",
  },
  wrapper: { maxWidth: 940, margin: "0 auto", padding: "32px 20px" },
  headerBlock: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-end",
    marginBottom: 22,
  },
  tabBar: {
    display: "flex",
    gap: 10,
    marginBottom: 24,
    flexWrap: "wrap",
  },
  badgeCount: {
    background: "#ffffff",
    color: "#6366f1",
    fontSize: 11,
    fontWeight: 800,
    padding: "1px 7px",
    borderRadius: 999,
    marginLeft: 6,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(270px, 1fr))",
    gap: 16,
  },
  formsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: 16,
  },
};
