// src/App.jsx — Root router for SharedSpace with strict session check

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import GangList from "./pages/GangList";
import GangDashboard from "./pages/GangDashboard";

function PrivateRoute({ children }) {
  const user = JSON.parse(localStorage.getItem("ss_user") || "null");
  // Require real database user ID + signed token
  return user && user.id && user.token ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Login />} />
        <Route
          path="/gangs"
          element={
            <PrivateRoute>
              <GangList />
            </PrivateRoute>
          }
        />
        <Route
          path="/gangs/:gangId"
          element={
            <PrivateRoute>
              <GangDashboard />
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
