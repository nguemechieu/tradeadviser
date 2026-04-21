import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import axios from 'axios';

import App from "./App.jsx";
import AppAdmin from "./AppAdmin.jsx";
import { AuthProvider } from "./context/AuthProvider.jsx";
import "./styles.css";
import "./app.css";

// Error Boundary
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Error Boundary caught:", error, errorInfo);
    // Don't hide the error in production, let it propagate to the UI
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "center", 
          height: "100vh", 
          background: "#0a0e27", 
          color: "#fff",
          flexDirection: "column",
          gap: "20px"
        }}>
          <h1>Application Error</h1>
          <p>{this.state.error?.message}</p>
          <button 
            onClick={() => window.location.reload()}
            style={{
              padding: "10px 20px",
              background: "#2563eb",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer"
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

// Router component that determines which dashboard to render
function RootRouter() {
  const [role, setRole] = React.useState(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    // Check if user has admin token in localStorage
    const token = localStorage.getItem("tradeadviser-admin-token");
    if (token) {
      // Try to validate token and get user role
      axios.get("/api/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => {
          const data = res.data;
          if (data.role && ["ADMIN", "SUPER_ADMIN", "OPERATIONS"].includes(data.role)) {
            setRole(data.role);
          }
          setLoading(false);
        })
        .catch((error) => {
          console.error("Admin auth check failed:", error.message);
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
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <RootRouter />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
);

