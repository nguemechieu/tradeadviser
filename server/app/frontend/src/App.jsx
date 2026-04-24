/**
 * TradeAdviser Unified App - Single App with Role-Based Routing
 * 
 * Consolidates trader and admin dashboards into one application with role-based access:
 * - TRADER: Portfolio, trading controls, signals
 * - RISK_MANAGER: Risk monitoring and limits
 * - OPERATIONS: System health, broker status, deployment
 * - ADMIN: User/license management, full admin access
 * - SUPER_ADMIN: Complete system access
 */

import { Routes, Route } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Register from './components/Register';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import ImprovedDashboard from './components/ImprovedDashboard';
import Layout from './components/Layout';
import TradingEditor from './components/TradingEditor';
import AdminPanel from './components/AdminPanel';
import NotFound from './components/NotFound';
import AccessDenied from './components/AccessDenied';
import Community from './components/Community';
import VerifyLink from './components/VerifyLink';
import RequireAuth from './components/RequireAuth';
import TradeAdviser from './components/TradeAdviser';
import PersistLogin from './components/PersistLogin';
import RoutesDocumentation from './components/RoutesDocumentation';
import UserGuide from './components/UserGuide';
import { OperationsDashboard } from './components/operations';
import { RiskDashboard } from './components/risk';
import { UsersLicensesDashboard } from './components/users_licenses';
import { AgentsDashboard } from './components/agents';
import { PerformanceAuditDashboard } from './components/performance_audit';

// Backend role definitions (matches backend UserRole enum)
const ROLES = {
  TRADER: 'trader',
  RISK_MANAGER: 'risk_manager',
  OPERATIONS: 'operations',
  ADMIN: 'admin',
  SUPER_ADMIN: 'super_admin'
};

// Allowed roles by route
const ROLE_ACCESS = {
  dashboard: [ROLES.TRADER, ROLES.RISK_MANAGER, ROLES.OPERATIONS, ROLES.ADMIN, ROLES.SUPER_ADMIN],
  trading: [ROLES.TRADER, ROLES.ADMIN, ROLES.SUPER_ADMIN],
  risk: [ROLES.RISK_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN],
  operations: [ROLES.OPERATIONS, ROLES.ADMIN, ROLES.SUPER_ADMIN],
  admin: [ROLES.ADMIN, ROLES.SUPER_ADMIN],
  agents: [ROLES.ADMIN, ROLES.SUPER_ADMIN],
  audit: [ROLES.ADMIN, ROLES.SUPER_ADMIN],
};

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        {/* Public routes */}
        <Route path="login" element={<Login />} />
        <Route path="register" element={<Register />} />
        <Route path="home" element={<TradeAdviser />} />
        <Route path="verify-link" element={<VerifyLink />} />
        <Route path="access-denied" element={<AccessDenied />} />

        {/* Protected routes - Trader/User Dashboard */}
        <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.dashboard} />}>
          <Route path="/" element={<ImprovedDashboard />} />
        </Route>

        {/* Protected routes - Trading Editor */}
        <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.trading} />}>
          <Route path="trading-editor" element={<TradingEditor />} />
        </Route>

        {/* Protected routes - Community */}
        <Route element={<RequireAuth allowedRoles={[ROLES.TRADER, ROLES.ADMIN, ROLES.SUPER_ADMIN]} />}>
          <Route path="community" element={<Community />} />
        </Route>

        {/* Admin Section - 5 Pillars */}
        
        {/* 1. Operations Pillar */}
        <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.operations} />}>
          <Route path="admin/operations" element={<OperationsDashboard />} />
        </Route>

        {/* 2. Risk Pillar */}
        <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.risk} />}>
          <Route path="admin/risk" element={<RiskDashboard />} />
        </Route>

        {/* 3. Users & Licenses Pillar */}
        <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.admin} />}>
          <Route path="admin/users-licenses" element={<UsersLicensesDashboard />} />
        </Route>

        {/* 4. Agents & AI Pillar */}
        <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.agents} />}>
          <Route path="admin/agents" element={<AgentsDashboard />} />
        </Route>

        {/* 5. Performance & Audit Pillar */}
        <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.audit} />}>
          <Route path="admin/performance-audit" element={<PerformanceAuditDashboard />} />
        </Route>

        {/* Documentation Routes */}
        <Route element={<RequireAuth allowedRoles={[ROLES.ADMIN, ROLES.SUPER_ADMIN]} />}>
          <Route path="docs/routes" element={<RoutesDocumentation />} />
        </Route>

        <Route path="docs/guide" element={<UserGuide />} />

        {/* Legacy admin panel route (redirect to operations) */}
        <Route element={<RequireAuth allowedRoles={ROLE_ACCESS.admin} />}>
          <Route path="admin-panel" element={<AdminPanel />} />
        </Route>

        {/* Error and catch-all routes */}
        <Route path="not-found" element={<NotFound />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

export default App;
