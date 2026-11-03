// src/api/client.js
// Central Axios client — all API calls go through here.
// Base URL points to our FastAPI server running on port 8000.

import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

// ── Gangs ────────────────────────────────────────────────────────────────────

export const createGang = (name, creatorName, creatorEmail) =>
  api.post("/gangs", { name, creator_name: creatorName, creator_email: creatorEmail });

export const getGang = (gangId) => api.get(`/gangs/${gangId}`);

export const addMember = (gangId, name, email) =>
  api.post(`/gangs/${gangId}/members`, { name, email });

export const addItem = (gangId, name, intervalDays, unit, price) =>
  api.post(`/gangs/${gangId}/items`, {
    name,
    declared_interval_days: intervalDays,
    unit,
    price,
  });

// ── Requests (alerts) ─────────────────────────────────────────────────────────

export const getActiveRequests = (gangId) =>
  api.get(`/gangs/${gangId}/requests`);

export const getRequestHistory = (gangId) =>
  api.get(`/gangs/${gangId}/requests/history`);

export const respondToRequest = (gangId, requestId, userId, action) =>
  api.post(`/gangs/${gangId}/requests/${requestId}/respond`, { user_id: userId, action });

export const checkAndTrigger = (gangId) =>
  api.post(`/gangs/${gangId}/check-and-trigger`);

export const getBanditStatus = (gangId) =>
  api.get(`/gangs/${gangId}/bandit`);

// ── Items / Stats ─────────────────────────────────────────────────────────────

export const getItemStats = (gangId, itemId) =>
  api.get(`/gangs/${gangId}/items/${itemId}/stats`);

export const getSurvivalCurve = (gangId, itemId) =>
  api.get(`/gangs/${gangId}/items/${itemId}/survival`);

export const recordPurchase = (gangId, itemId, price, buyerId) =>
  api.post(`/gangs/${gangId}/items/${itemId}/purchase`, {
    price,
    buyer_id: buyerId || null,
  });

// ── Expenses ──────────────────────────────────────────────────────────────────

export const getBalances = (gangId) => api.get(`/gangs/${gangId}/balances`);
export const getSettlements = (gangId) => api.get(`/gangs/${gangId}/settlements`);

export default api;

