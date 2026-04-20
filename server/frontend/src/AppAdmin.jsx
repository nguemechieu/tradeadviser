/**
 * Sopotek Quant System - Admin Dashboard (5-Pillar Architecture)
 * 
 * The server dashboard is where the platform is managed, not where trading happens.
 * Desktop app = Trader workspace (live trading, execution, charts)
 * Server dashboard = Admin command center (oversight, governance, operations)
 * 
 * 5 Pillars:
 * 1. Operations - System health, broker connectivity, deployment
 * 2. Risk - Portfolio risk monitoring, limits, breaches
 * 3. Users & Licenses - Account management and subscriptions
 * 4. Agents & AI - Agent deployment and performance
 * 5. Performance & Audit - Analytics and compliance
 */

import { useState, useEffect, useTransition, useMemo } from "react";
import logo from "./assets/logo.png";

import { PillarNav, Alert } from "./components/shared";
import { OperationsDashboard } from "./components/operations";
import { RiskDashboard } from "./components/risk";
import { UsersLicensesDashboard } from "./components/users_licenses";
import { AgentsDashboard } from "./components/agents";
import { PerformanceAuditDashboard } from "./components/performance_audit";

const STORAGE_KEY = "tradeadviser-admin-dashboard:v1";
const PILLAR_DEFAULT = "operations";

function readPersistedState() {
  if (typeof window === "undefined") {
    return {
      token: "",
      activePillar: PILLAR_DEFAULT,
      authMode: "login",
      username: "",
      password: "",
    };
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {
        token: "",
        activePillar: PILLAR_DEFAULT,
        authMode: "login",
        username: "",
        password: "",
      };
    }

    const parsed = JSON.parse(raw);
    return {
      token: typeof parsed.token === "string" ? parsed.token : "",
      activePillar: typeof parsed.activePillar === "string" ? parsed.activePillar : PILLAR_DEFAULT,
      authMode: typeof parsed.authMode === "string" ? parsed.authMode : "login",
      username: typeof parsed.username === "string" ? parsed.username : "",
      password: typeof parsed.password === "string" ? parsed.password : "",
    };
  } catch {
    return {
      token: "",
      activePillar: PILLAR_DEFAULT,
      authMode: "login",
      username: "",
      password: "",
    };
  }
}

async function parseResponse(response) {
  const text = await response.text();
  let payload = null;

  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    const message =
      (payload && typeof payload === "object" && payload.detail) ||
      (payload && typeof payload === "object" && payload.message) ||
      (typeof payload === "string" ? payload : "") ||
      `Request failed with status ${response.status}`;
    throw new Error(String(message));
  }

  return payload;
}

async function apiRequest(path, options = {}, token = "") {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return parseResponse(
    await fetch(path, {
      ...options,
      headers,
    })
  );
}

function LoginPanel({ onLogin, isLoading, error }) {
  const [username, setUsername] = useState("admin@sopotek.local");
  const [password, setPassword] = useState("admin123");

  const handleSubmit = async (e) => {
    e.preventDefault();
    onLogin(username, password);
  };

  return (
    <div className="auth-panel">
      <div className="auth-card">
        <div className="auth-header">
          <img src={logo} alt="Sopotek" className="auth-logo" />
          <h1>Admin Dashboard</h1>
          <p>Platform Management & Oversight</p>
        </div>

        {error && (
          <Alert
            type="error"
            title="Login Failed"
            message={error}
            dismissible={true}
            onDismiss={() => {}}
          />
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="admin@sopotek.local"
              required
            />
          </div>

          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button type="submit" className="button button--primary button--large" disabled={isLoading}>
            {isLoading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <p className="auth-hint">Demo: admin@sopotek.local / admin123</p>
      </div>

      <footer className="auth-footer">
        <p>&copy; 2025 TradeAdviser. Institutional Platform. All Rights Reserved.</p>
      </footer>
    </div>
  );
}

export default function App() {
  const persisted = useMemo(() => readPersistedState(), []);

  const [token, setToken] = useState(persisted.token);
  const [activePillar, setActivePillar] = useState(persisted.activePillar);
  const [user, setUser] = useState(null);
  const [authError, setAuthError] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [dashboardError, setDashboardError] = useState("");
  const [isPending, startUITransition] = useTransition();

  // Persist state changes
  useEffect(() => {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        token,
        activePillar,
        authMode: "login",
        username: "",
        password: "",
      })
    );
  }, [token, activePillar]);

  // Load user on mount if token exists
  useEffect(() => {
    if (token) {
      loadCurrentUser();
    }
  }, [token]);

  async function loadCurrentUser() {
    try {
      const userData = await apiRequest("/auth/me", {}, token);
      setUser(userData);
    } catch (error) {
      // Invalid token, clear it
      setToken("");
      setUser(null);
    }
  }

  async function handleLogin(email, password) {
    setAuthError("");
    setAuthBusy(true);

    try {
      const response = await apiRequest("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      startUITransition(() => {
        setToken(response.access_token);
        setUser(response.user);
        setActivePillar(PILLAR_DEFAULT);
        setAuthError("");
      });
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : "Login failed");
    } finally {
      setAuthBusy(false);
    }
  }

  function handleLogout() {
    setToken("");
    setUser(null);
    setActivePillar(PILLAR_DEFAULT);
    setAuthError("");
  }

  function handlePillarChange(pillarId) {
    startUITransition(() => {
      setActivePillar(pillarId);
      setDashboardError("");
    });
  }

  // Not authenticated
  if (!token || !user) {
    return <LoginPanel onLogin={handleLogin} isLoading={authBusy} error={authError} />;
  }

  // Authenticated - render admin dashboard with 5 pillars
  return (
    <div className="app admin-dashboard">
      <header className="dashboard-header">
        <div className="header-left">
          <img src={logo} alt="Sopotek" className="logo" />
          <h1>Sopotek Admin Console</h1>
        </div>
        <div className="header-right">
          <span className="user-info">
            {user.display_name || user.email}
            <span className="badge badge--admin">{user.role}</span>
          </span>
          <button className="button button--secondary button--small" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      <nav className="dashboard-nav">
        <PillarNav activePillar={activePillar} onChange={handlePillarChange} />
      </nav>

      <main className="dashboard-main">
        {dashboardError && (
          <Alert
            type="error"
            title="Dashboard Error"
            message={dashboardError}
            onDismiss={() => setDashboardError("")}
          />
        )}

        {isPending && <div className="loading-overlay" />}

        {activePillar === "operations" && (
          <OperationsDashboard token={token} onError={setDashboardError} />
        )}

        {activePillar === "risk" && <RiskDashboard token={token} onError={setDashboardError} />}

        {activePillar === "users-licenses" && (
          <UsersLicensesDashboard token={token} onError={setDashboardError} />
        )}

        {activePillar === "agents" && <AgentsDashboard token={token} onError={setDashboardError} />}

        {activePillar === "performance-audit" && (
          <PerformanceAuditDashboard token={token} onError={setDashboardError} />
        )}
      </main>

      <footer className="dashboard-footer">
        <p>TradeAdviser - Institutional Trading Platform</p>
      </footer>
    </div>
  );
}
