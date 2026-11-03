// src/App.jsx — Root router for SharedSpace

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import GangList from "./pages/GangList";
import GangDashboard from "./pages/GangDashboard";

// Read user from localStorage (set on Login page)
function PrivateRoute({ children }) {
  const user = JSON.parse(localStorage.getItem("ss_user") || "null");
  return user ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route
          path="/gangs"
          element={<PrivateRoute><GangList /></PrivateRoute>}
        />
        <Route
          path="/gangs/:gangId"
          element={<PrivateRoute><GangDashboard /></PrivateRoute>}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
