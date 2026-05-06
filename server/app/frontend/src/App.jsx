/**
 * TradeAdviser Unified App - Role-Based Routing
 *
 * Consolidates trader, risk, operations, AI, strategy research,
 * Quant PM, network exchange, and admin dashboards into one app.
 *
 * Roles:
 * - TRADER: Portfolio, trading controls, signals, community, AI review
 * - RISK_MANAGER: Risk monitoring, limits, Quant PM, portfolio risk
 * - OPERATIONS: System health, broker/network status, deployment
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
import ProTradingTerminal from "./components/ProTradingTerminal";
import AdminPanel from "./components/AdminPanel";
import NotFound from "./components/NotFound";
import AccessDenied from "./components/AccessDenied";
import Community from "./components/Community";
import VerifyLink from "./components/VerifyLink";
import RequireAuth from "./components/RequireAuth";
import RequirePublic from "./components/RequirePublic";
import TradeAdviser from "./components/TradeAdviser";
import PersistLogin from "./components/PersistLogin";
import RoutesDocumentation from "./components/RoutesDocumentation";
import UserGuide from "./components/UserGuide";

import { OperationsDashboard } from "./components/operations";
import { RiskDashboard } from "./components/risk";
import { UsersLicensesDashboard } from "./components/users_licenses";
import { AgentsDashboard } from "./components/agents";
import { PerformanceAuditDashboard } from "./components/performance_audit";

/**
 * New TradeAdviser modules.
 *
 * Create these components if they do not exist yet.
 * You can start them as placeholder dashboards, then connect real data later.
 */
import PortfolioDashboard from "./components/portfolio/PortfolioDashboard";
import QuantPmDashboard from "./components/portfolio/QuantPmDashboard";
import PositionsDashboard from "./components/positions/PositionsDashboard";

import SignalsDashboard from "./components/signals/SignalsDashboard";
import StrategyResearchDashboard from "./components/strategy/StrategyResearchDashboard";
import StrategyAssignmentDashboard from "./components/strategy/StrategyAssignmentDashboard";
import StrategyPerformanceDashboard from "./components/strategy/StrategyPerformanceDashboard";
import BacktestingDashboard from "./components/backtesting/BacktestingDashboard";

import AiTradeReviewDashboard from "./components/ai/AiTradeReviewDashboard";
import AiPositionManagerDashboard from "./components/ai/AiPositionManagerDashboard";
import AiAuditDashboard from "./components/ai/AiAuditDashboard";

import BrokersDashboard from "./components/brokers/BrokersDashboard";
import StellarNetworkDashboard from "./components/stellar/StellarNetworkDashboard";
import StellarSwapDashboard from "./components/stellar/StellarSwapDashboard";
import StellarTrustlineDashboard from "./components/stellar/StellarTrustlineDashboard";

import RiskLimitsDashboard from "./components/risk/RiskLimitsDashboard";
import RiskReportsDashboard from "./components/risk/RiskReportsDashboard";

import SystemHealthDashboard from "./components/operations/SystemHealthDashboard";
import BrokerStatusDashboard from "./components/operations/BrokerStatusDashboard";
import DeploymentDashboard from "./components/operations/DeploymentDashboard";

import SettingsDashboard from "./components/settings/SettingsDashboard";
import NotificationsSettings from "./components/settings/NotificationsSettings";
import SecuritySettings from "./components/settings/SecuritySettings";
import TradingSettings from "./components/settings/TradingSettings";
import IntegrationsSettings from "./components/settings/IntegrationsSettings";
import AccountDashboard from "./components/account/AccountDashboard";

import "./App.css";

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

  portfolio: [
    ROLES.TRADER,
    ROLES.RISK_MANAGER,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  positions: [
    ROLES.TRADER,
    ROLES.RISK_MANAGER,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  signals: [
    ROLES.TRADER,
    ROLES.RISK_MANAGER,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  strategies: [
    ROLES.TRADER,
    ROLES.RISK_MANAGER,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  backtesting: [
    ROLES.TRADER,
    ROLES.RISK_MANAGER,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  ai: [
    ROLES.TRADER,
    ROLES.RISK_MANAGER,
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

  quantPm: [
    ROLES.RISK_MANAGER,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  operations: [
    ROLES.OPERATIONS,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  brokers: [
    ROLES.TRADER,
    ROLES.OPERATIONS,
    ROLES.ADMIN,
    ROLES.SUPER_ADMIN,
  ],

  stellar: [
    ROLES.TRADER,
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

  settings: [
    ROLES.TRADER,
    ROLES.RISK_MANAGER,
    ROLES.OPERATIONS,
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
        
        {/* Auth-only routes - redirect authenticated users away */}
        <Route element={<RequirePublic />}>
          <Route path="login" element={<Login />} />
          <Route path="register" element={<Register />} />
          <Route path="verify-link" element={<VerifyLink />} />
        </Route>
        
        <Route path="unauthorized" element={<AccessDenied />} />
        <Route path="access-denied" element={<AccessDenied />} />

        {/* Public documentation */}
        <Route path="docs/guide" element={<UserGuide />} />

        {/* Protected session routes */}
        <Route element={<PersistLogin />}>
          {/* Main dashboard */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.dashboard} />}>
            <Route path="dashboard" element={<ImprovedDashboard />} />
            <Route path="dashboard/classic" element={<Dashboard />} />
            <Route path="account" element={<AccountDashboard />} />
            <Route path="settings" element={<SettingsDashboard />} />
            <Route path="settings/notifications" element={<NotificationsSettings />} />
            <Route path="settings/security" element={<SecuritySettings />} />
            <Route path="settings/trading" element={<TradingSettings />} />
            <Route path="settings/integrations" element={<IntegrationsSettings />} />
          </Route>

          {/* Trading */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.trading} />}>
            <Route path="trading-terminal" element={<ProTradingTerminal />} />
            <Route path="trading-editor" element={<TradingEditor />} />
            <Route path="trade" element={<Navigate to="/trading-editor" replace />} />
            <Route path="trading" element={<Navigate to="/trading-editor" replace />} />
          </Route>

          {/* Portfolio / positions */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.portfolio} />}>
            <Route path="portfolio" element={<PortfolioDashboard />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.positions} />}>
            <Route path="positions" element={<PositionsDashboard />} />
            <Route path="open-positions" element={<Navigate to="/positions" replace />} />
          </Route>

          {/* Signals */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.signals} />}>
            <Route path="signals" element={<SignalsDashboard />} />
          </Route>

          {/* Strategy research, assignment, performance */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.strategies} />}>
            <Route path="strategies" element={<StrategyResearchDashboard />} />
            <Route path="strategies/research" element={<StrategyResearchDashboard />} />
            <Route path="strategies/assignments" element={<StrategyAssignmentDashboard />} />
            <Route path="strategies/performance" element={<StrategyPerformanceDashboard />} />
          </Route>

          {/* Backtesting */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.backtesting} />}>
            <Route path="backtesting" element={<BacktestingDashboard />} />
            <Route path="backtest" element={<Navigate to="/backtesting" replace />} />
          </Route>

          {/* AI trade review and AI position management */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.ai} />}>
            <Route path="ai" element={<AiTradeReviewDashboard />} />
            <Route path="ai/trade-review" element={<AiTradeReviewDashboard />} />
            <Route path="ai/position-manager" element={<AiPositionManagerDashboard />} />
            <Route path="ai/audit" element={<AiAuditDashboard />} />
          </Route>

          {/* Community */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.community} />}>
            <Route path="community" element={<Community />} />
          </Route>

          {/* Risk */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.risk} />}>
            <Route path="risk" element={<RiskDashboard />} />
            <Route path="risk/limits" element={<RiskLimitsDashboard />} />
            <Route path="risk/reports" element={<RiskReportsDashboard />} />
          </Route>

          {/* Quant Portfolio Manager */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.quantPm} />}>
            <Route path="quant-pm" element={<QuantPmDashboard />} />
            <Route path="portfolio-manager" element={<Navigate to="/quant-pm" replace />} />
          </Route>

          {/* Brokers / exchanges */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.brokers} />}>
            <Route path="brokers" element={<BrokersDashboard />} />
            <Route path="exchanges" element={<Navigate to="/brokers" replace />} />
          </Route>

          {/* Stellar Network Exchange */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.stellar} />}>
            <Route path="stellar" element={<StellarNetworkDashboard />} />
            <Route path="stellar/swap" element={<StellarSwapDashboard />} />
            <Route path="stellar/trustlines" element={<StellarTrustlineDashboard />} />
          </Route>

          {/* Operations */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.operations} />}>
            <Route path="operations" element={<OperationsDashboard />} />
            <Route path="operations/system-health" element={<SystemHealthDashboard />} />
            <Route path="operations/broker-status" element={<BrokerStatusDashboard />} />
            <Route path="operations/deployment" element={<DeploymentDashboard />} />
            <Route path="admin/operations" element={<OperationsDashboard />} />
          </Route>

          {/* Admin legacy routes */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.admin} />}>
            <Route path="admin" element={<Navigate to="/admin/operations" replace />} />
            <Route path="admin-panel" element={<AdminPanel />} />
            <Route path="license" element={<UsersLicensesDashboard />} />
            <Route path="licenses" element={<UsersLicensesDashboard />} />
          </Route>

          {/* Admin 5 pillars */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.admin} />}>
            <Route path="admin/users-licenses" element={<UsersLicensesDashboard />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.agents} />}>
            <Route path="agents" element={<AgentsDashboard />} />
            <Route path="admin/agents" element={<AgentsDashboard />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.audit} />}>
            <Route path="audit" element={<PerformanceAuditDashboard />} />
            <Route path="admin/performance-audit" element={<PerformanceAuditDashboard />} />
          </Route>

          {/* Admin docs */}
          <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.docs} />}>
            <Route path="docs/routes" element={<RoutesDocumentation />} />
          </Route>
        </Route>

        {/* Compatibility redirects */}
        <Route path="admin-dashboard" element={<Navigate to="/admin/operations" replace />} />
        <Route path="risk-dashboard" element={<Navigate to="/risk" replace />} />
        <Route path="ops" element={<Navigate to="/operations" replace />} />
        <Route path="strategy" element={<Navigate to="/strategies" replace />} />
        <Route path="strategy-research" element={<Navigate to="/strategies/research" replace />} />
        <Route path="strategy-assignment" element={<Navigate to="/strategies/assignments" replace />} />
        <Route path="ai-review" element={<Navigate to="/ai/trade-review" replace />} />
        <Route path="ai-position-manager" element={<Navigate to="/ai/position-manager" replace />} />

        {/* Error and catch-all routes */}
        <Route path="not-found" element={<NotFound />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

export default App;