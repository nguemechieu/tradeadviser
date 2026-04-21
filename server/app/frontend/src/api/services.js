/**
 * Comprehensive API Services Layer
 * All backend API endpoints for TradeAdviser
 */

import { axiosPrivate } from './axios';

/**
 * Generic API request wrapper using axios
 * Token is automatically injected by axiosPrivate interceptor
 */
async function apiRequest(endpoint, options = {}, token = null) {
  try {
    const config = {
      method: options.method || 'GET',
      ...options,
    };

    if (options.body) {
      config.data = typeof options.body === 'string' 
        ? JSON.parse(options.body) 
        : options.body;
    }

    const response = await axiosPrivate(endpoint, config);
    return response.data;
  } catch (error) {
    const message = 
      error.response?.data?.detail || 
      error.response?.data?.message || 
      error.message || 
      `API Error: ${error.response?.status || 'Unknown'}`;
    throw new Error(message);
  }
}

// ============================================================================
// AUTHENTICATION & SESSION
// ============================================================================

export const authService = {
  register: async (email, password, username, displayName) =>
    apiRequest("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
        username,
        display_name: displayName,
      }),
    }),

  login: async (identifier, password, rememberMe = true) =>
    apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        identifier,
        password,
        remember_me: rememberMe,
      }),
    }),

  getCurrentUser: async (token) =>
    apiRequest("/auth/me", {}, token),

  refresh: async (refreshToken, rememberMe = true) =>
    apiRequest("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({
        refresh_token: refreshToken,
        remember_me: rememberMe,
      }),
    }),

  forgotPassword: async (identifier) =>
    apiRequest("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ identifier }),
    }),

  resetPassword: async (resetToken, newPassword) =>
    apiRequest("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({
        reset_token: resetToken,
        new_password: newPassword,
      }),
    }),
};

export const sessionService = {
  login: async (username, password) =>
    apiRequest("/api/v1/session/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  resume: async (sessionId) =>
    apiRequest("/api/v1/session/resume", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    }),
};

// ============================================================================
// PORTFOLIO & TRADING
// ============================================================================

export const portfolioService = {
  getDashboard: async (token) =>
    apiRequest("/portfolio/dashboard", {}, token),

  getPositions: async (token) =>
    apiRequest("/portfolio/positions", {}, token),

  getOrders: async (token) =>
    apiRequest("/portfolio/orders", {}, token),
};

export const tradingService = {
  placeOrder: async (payload, token) =>
    apiRequest("/api/v1/trading/orders", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),

  cancelOrder: async (orderId, token) =>
    apiRequest("/api/v1/trading/orders/cancel", {
      method: "POST",
      body: JSON.stringify({ order_id: orderId }),
    }, token),

  closePosition: async (payload, token) =>
    apiRequest("/api/v1/trading/positions/close", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),

  triggerKillSwitch: async (reason, token) =>
    apiRequest("/api/v1/trading/kill-switch", {
      method: "POST",
      body: JSON.stringify({ reason }),
    }, token),

  connectBroker: async (payload, token) =>
    apiRequest("/api/v1/trading/broker/connect", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),

  requestMarketDataSubscription: async (payload, token) =>
    apiRequest("/api/v1/trading/subscriptions/market-data", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),
};

// ============================================================================
// TRADES & SIGNALS
// ============================================================================

export const tradesService = {
  list: async (token, limit = 50) =>
    apiRequest(`/trades?limit=${limit}`, {}, token),

  create: async (payload, token) =>
    apiRequest("/trades", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),
};

export const signalsService = {
  list: async (token, limit = 50) =>
    apiRequest(`/signals?limit=${limit}`, {}, token),

  create: async (payload, token) =>
    apiRequest("/signals", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),
};

// ============================================================================
// PERFORMANCE & AUDIT
// ============================================================================

export const performanceService = {
  getSummary: async (token) =>
    apiRequest("/performance", {}, token),
};

export const performanceAuditService = {
  getReport: async (token, period = "1d") =>
    apiRequest(`/admin/performance-audit?period=${period}`, {}, token),

  getMetrics: async (token, startDate, endDate) =>
    apiRequest(`/admin/performance-audit/metrics?start=${startDate}&end=${endDate}`, {}, token),
};

// ============================================================================
// WORKSPACE
// ============================================================================

export const workspaceService = {
  getSettings: async (token) =>
    apiRequest("/workspace/settings", {}, token),

  updateSettings: async (settings, token) =>
    apiRequest("/workspace/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    }, token),
};

// ============================================================================
// ADMIN - OVERVIEW & USERS
// ============================================================================

export const adminService = {
  getOverview: async (token) =>
    apiRequest("/admin/overview", {}, token),

  listUsers: async (token) =>
    apiRequest("/admin/users", {}, token),

  createUser: async (payload, token) =>
    apiRequest("/admin/users", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),

  updateUserStatus: async (userId, isActive, token) =>
    apiRequest(`/admin/users/${userId}/status`, {
      method: "PUT",
      body: JSON.stringify({ is_active: isActive }),
    }, token),

  updateUserRole: async (userId, role, token) =>
    apiRequest(`/admin/users/${userId}/role`, {
      method: "PUT",
      body: JSON.stringify({ role }),
    }, token),
};

// ============================================================================
// ADMIN - OPERATIONS
// ============================================================================

export const operationsService = {
  getSystemHealth: async (token) =>
    apiRequest("/admin/operations/health", {}, token),

  getBrokerStatus: async (token) =>
    apiRequest("/admin/operations/broker-status", {}, token),

  getActiveConnections: async (token) =>
    apiRequest("/admin/operations/active-connections", {}, token),

  getTradeStatistics: async (token, period = "1h") =>
    apiRequest(`/admin/operations/trade-stats?period=${period}`, {}, token),

  getDeploymentStatus: async (token) =>
    apiRequest("/admin/operations/deployment-status", {}, token),
};

// ============================================================================
// ADMIN - AGENTS
// ============================================================================

export const agentsService = {
  getOverview: async (token) =>
    apiRequest("/admin/agents/overview", {}, token),

  list: async (token) =>
    apiRequest("/admin/agents", {}, token),

  getAgent: async (agentId, token) =>
    apiRequest(`/admin/agents/${agentId}`, {}, token),

  createAgent: async (payload, token) =>
    apiRequest("/admin/agents", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),

  updateAgent: async (agentId, payload, token) =>
    apiRequest(`/admin/agents/${agentId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }, token),

  deleteAgent: async (agentId, token) =>
    apiRequest(`/admin/agents/${agentId}`, {
      method: "DELETE",
    }, token),

  getAgentPerformance: async (agentId, token) =>
    apiRequest(`/admin/agents/${agentId}/performance`, {}, token),

  pauseAgent: async (agentId, token) =>
    apiRequest(`/admin/agents/${agentId}/pause`, {
      method: "POST",
    }, token),

  resumeAgent: async (agentId, token) =>
    apiRequest(`/admin/agents/${agentId}/resume`, {
      method: "POST",
    }, token),
};

// ============================================================================
// ADMIN - RISK
// ============================================================================

export const riskService = {
  getOverview: async (token) =>
    apiRequest("/admin/risk/overview", {}, token),

  getUserLimits: async (userId, token) =>
    apiRequest(`/admin/risk/limits/${userId}`, {}, token),

  updateUserLimits: async (userId, payload, token) =>
    apiRequest(`/admin/risk/limits/${userId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }, token),

  getRecentBreaches: async (token) =>
    apiRequest("/admin/risk/breaches", {}, token),

  getUserBreaches: async (userId, token) =>
    apiRequest(`/admin/risk/breaches/${userId}`, {}, token),
};

// ============================================================================
// DASHBOARD COMPONENTS - OPERATIONS
// ============================================================================

export const operationsDashboardService = {
  getHealth: async (token) =>
    apiRequest("/admin/operations/health", {}, token),

  getBrokerStatus: async (token) =>
    apiRequest("/admin/operations/broker-status", {}, token),

  getTradeStats: async (token, period = "1h") =>
    apiRequest(`/admin/operations/trade-stats?period=${period}`, {}, token),

  getActiveConnections: async (token) =>
    apiRequest("/admin/operations/active-connections", {}, token),

  getDeploymentStatus: async (token) =>
    apiRequest("/admin/operations/deployment-status", {}, token),
};

// ============================================================================
// DASHBOARD COMPONENTS - RISK
// ============================================================================

export const riskDashboardService = {
  getOverview: async (token) =>
    apiRequest("/admin/risk/overview", {}, token),

  getBreaches: async (token) =>
    apiRequest("/admin/risk/breaches", {}, token),

  getLimits: async (token, userId) =>
    apiRequest(`/admin/risk/limits/${userId}`, {}, token),

  updateLimits: async (token, userId, limits) =>
    apiRequest(`/admin/risk/limits/${userId}`, {
      method: "PUT",
      body: JSON.stringify(limits),
    }, token),
};

// ============================================================================
// DASHBOARD COMPONENTS - USERS & LICENSES
// ============================================================================

export const usersLicensesDashboardService = {
  getUsers: async (token) =>
    apiRequest("/admin/users-licenses/users", {}, token),

  getLicenses: async (token) =>
    apiRequest("/admin/users-licenses/licenses", {}, token),

  createUser: async (token, payload) =>
    apiRequest("/admin/users-licenses/users", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),

  createLicense: async (token, payload) =>
    apiRequest("/admin/users-licenses/licenses", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),

  updateUserStatus: async (token, userId, isActive) =>
    apiRequest(`/admin/users-licenses/users/${userId}/status`, {
      method: "PUT",
      body: JSON.stringify({ is_active: isActive }),
    }, token),

  revokeLicense: async (token, licenseId) =>
    apiRequest(`/admin/users-licenses/licenses/${licenseId}`, {
      method: "DELETE",
    }, token),
};

// ============================================================================
// DASHBOARD COMPONENTS - AGENTS
// ============================================================================

export const agentsDashboardService = {
  getOverview: async (token) =>
    apiRequest("/admin/agents/overview", {}, token),

  listAgents: async (token) =>
    apiRequest("/admin/agents", {}, token),

  getAgent: async (token, agentId) =>
    apiRequest(`/admin/agents/${agentId}`, {}, token),

  createAgent: async (token, payload) =>
    apiRequest("/admin/agents", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),

  updateAgent: async (token, agentId, payload) =>
    apiRequest(`/admin/agents/${agentId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }, token),

  deleteAgent: async (token, agentId) =>
    apiRequest(`/admin/agents/${agentId}`, {
      method: "DELETE",
    }, token),

  getPerformance: async (token, agentId) =>
    apiRequest(`/admin/agents/${agentId}/performance`, {}, token),

  pauseAgent: async (token, agentId) =>
    apiRequest(`/admin/agents/${agentId}/pause`, {
      method: "POST",
    }, token),

  resumeAgent: async (token, agentId) =>
    apiRequest(`/admin/agents/${agentId}/resume`, {
      method: "POST",
    }, token),
};

// ============================================================================
// DASHBOARD COMPONENTS - PERFORMANCE & AUDIT
// ============================================================================

export const performanceAuditDashboardService = {
  getSystemMetrics: async (token) =>
    apiRequest("/admin/performance-audit/system-metrics", {}, token),

  getAuditLog: async (token, days = 7) =>
    apiRequest(`/admin/performance-audit/audit-log?days=${days}`, {}, token),

  getComplianceReport: async (token) =>
    apiRequest("/admin/performance-audit/compliance-report", {}, token),

  getMetrics: async (token, period = "1d") =>
    apiRequest(`/admin/performance-audit/metrics?period=${period}`, {}, token),

  getAuditTrail: async (token, startDate, endDate) =>
    apiRequest(`/admin/performance-audit/audit-trail?start=${startDate}&end=${endDate}`, {}, token),
};

// ============================================================================
// ADMIN - USERS & LICENSES
// ============================================================================

export const usersLicensesService = {
  getLicenses: async (token) =>
    apiRequest("/users/licenses", {}, token),

  issueLicense: async (payload, token) =>
    apiRequest("/users/licenses", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),

  revokeLicense: async (licenseId, token) =>
    apiRequest(`/users/licenses/${licenseId}`, {
      method: "DELETE",
    }, token),

  updateLicense: async (licenseId, payload, token) =>
    apiRequest(`/users/licenses/${licenseId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }, token),
};

// ============================================================================
// SYSTEM
// ============================================================================

export const systemService = {
  health: async () =>
    apiRequest("/health", { method: "GET" }),

  getInfo: async () =>
    apiRequest("/", { method: "GET" }),

  connectWebSocket: (sessionId) => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return new WebSocket(
      `${protocol}//${window.location.host}/ws/events?session_id=${encodeURIComponent(sessionId)}`
    );
  },
};

// ============================================================================
// COMBINED EXPORT
// ============================================================================

export const apiServices = {
  auth: authService,
  session: sessionService,
  portfolio: portfolioService,
  trading: tradingService,
  trades: tradesService,
  signals: signalsService,
  performance: performanceService,
  performanceAudit: performanceAuditService,
  workspace: workspaceService,
  admin: adminService,
  operations: operationsService,
  agents: agentsService,
  risk: riskService,
  usersLicenses: usersLicensesService,
  system: systemService,
  // Dashboard component services
  operationsDashboard: operationsDashboardService,
  riskDashboard: riskDashboardService,
  usersLicensesDashboard: usersLicensesDashboardService,
  agentsDashboard: agentsDashboardService,
  performanceAuditDashboard: performanceAuditDashboardService,
};

export default apiServices;
