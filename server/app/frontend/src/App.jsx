/**
 * TradeAdviser Unified App - Role-Based Routing
 *
 * Consolidates trader, risk, operations, and admin dashboards into one app.
 *
 * Roles:
 * - TRADER: Portfolio, trading controls, signals, community
 * - RISK_MANAGER: Risk monitoring and limits
 * - OPERATIONS: System health, broker status, deployment
 * - ADMIN: User/license management, agents, audit, admin access
 * - SUPER_ADMIN: Complete system access
 */

import { Navigate, Route, Routes } from "react-router-dom";

import Register from "./components/Register";
import Login from "./components/Login";
import Dashboard from "./components/Dashboard";
import ImprovedDashboard from "./components/ImprovedDashboard";
import Layout from "./components/Layout";
import TradingEditor from "./components/TradingEditor";
import AdminPanel from "./components/AdminPanel";
import NotFound from "./components/NotFound";
import AccessDenied from "./components/AccessDenied";
import Community from "./components/Community";
import VerifyLink from "./components/VerifyLink";
import RequireAuth from "./components/RequireAuth";
import TradeAdviser from "./components/TradeAdviser";
import PersistLogin from "./components/PersistLogin";
import RoutesDocumentation from "./components/RoutesDocumentation";
import UserGuide from "./components/UserGuide";

import { OperationsDashboard } from "./components/operations";
import { RiskDashboard } from "./components/risk";
import { UsersLicensesDashboard } from "./components/users_licenses";
import { AgentsDashboard } from "./components/agents";
import { PerformanceAuditDashboard } from "./components/performance_audit";
import "./App.css"
// Backend role definitions.
// These should match your backend UserRole enum values exactly.
export const ROLES = Object.freeze({
  TRADER: "trader",
  RISK_MANAGER: "risk_manager",
  OPERATIONS: "operations",
  ADMIN: "admin",
  SUPER_ADMIN: "super_admin",
});

// Role groups by route area.
export const ROLE_ACCESS = Object.freeze({
  dashboard: [
    ROLES.TRADER,
    ROLES.RISK_MANAGER,
    ROLES.OPERATIONS,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  trading: [
    ROLES.TRADER,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  community: [
    ROLES.TRADER,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  risk: [
    ROLES.RISK_MANAGER,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  operations: [
    ROLES.OPERATIONS,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  admin: [
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  agents: [
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  audit: [
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  docs: [
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],
});

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        {/* Public routes */}
        <Route index element={<TradeAdviser />} />
        <Route path="home" element={<TradeAdviser />} />
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="verify-link" element={<VerifyLink />} />
        <Route path="access-denied" element={<AccessDenied />} />

        {/* Public documentation */}
        <Route path="docs/guide" element={<UserGuide />} />

        {/* Protected session routes */}
        <Route element={<PersistLogin />}>
          {/* Main dashboard */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.dashboard} />}>
            <Route path="dashboard" element={<ImprovedDashboard />} />
            <Route path="dashboard/classic" element={<Dashboard />} />
          </Route>

          {/* Trading */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.trading} />}>
            <Route path="trading-editor" element={<TradingEditor />} />
          </Route>

          {/* Community */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.community} />}>
            <Route path="community" element={<Community />} />
          </Route>

          {/* Admin legacy route */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.admin} />}>
            <Route path="admin-panel" element={<AdminPanel />} />
          </Route>

          {/* Admin 5 pillars */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.operations} />}>
            <Route path="admin/operations" element={<OperationsDashboard />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.risk} />}>
            <Route path="admin/risk" element={<RiskDashboard />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.admin} />}>
            <Route path="admin/users-licenses" element={<UsersLicensesDashboard />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.agents} />}>
            <Route path="admin/agents" element={<AgentsDashboard />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.audit} />}>
            <Route path="admin/performance-audit" element={<PerformanceAuditDashboard />} />
          </Route>

          {/* Admin docs */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.docs} />}>
            <Route path="docs/routes" element={<RoutesDocumentation />} />
          </Route>
        </Route>

        {/* Compatibility redirects */}
        <Route path="admin" element={<Navigate to="/admin/operations" replace />} />
        <Route path="trade" element={<Navigate to="/trading-editor" replace />} />
        <Route path="trading" element={<Navigate to="/trading-editor" replace />} />

        {/* Error and catch-all routes */}
        <Route path="not-found" element={<NotFound />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

export default App;