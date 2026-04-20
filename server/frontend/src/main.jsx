import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App.jsx";
import AppAdmin from "./AppAdmin";
import "./styles.css";

// Router component that determines which dashboard to render
function RootRouter() {
  const [role, setRole] = React.useState(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    // Check if user has admin token in localStorage
    const token = localStorage.getItem("tradeadviser-admin-token");
    if (token) {
      // Try to validate token and get user role
      fetch("/api/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => (res.ok ? res.json() : Promise.reject()))
        .then((data) => {
          if (data.role && ["ADMIN", "SUPER_ADMIN", "OPERATIONS"].includes(data.role)) {
            setRole(data.role);
          }
          setLoading(false);
        })
        .catch(() => {
          localStorage.removeItem("tradeadviser-admin-token");
          setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, []);

  if (loading) {
    return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", background: "#0a0e27", color: "#fff" }}>Loading...</div>;
  }

  // Render admin dashboard if user has admin role
  if (role) {
    return <AppAdmin />;
  }

  // Otherwise render trader dashboard
  return <App />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <RootRouter />
  </React.StrictMode>
);

