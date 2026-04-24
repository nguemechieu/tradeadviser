/**
 * Performance & Audit Pillar Dashboard
 * Analytics, compliance, and audit trails
 */

import { useState, useEffect } from "react";
import { Card, MetricBox, DataTable, Alert, Badge, Button } from "./shared";

export function PerformanceAuditDashboard({ token, onError }) {
  const [metrics, setMetrics] = useState(null);
  const [auditLog, setAuditLog] = useState([]);
  const [compliance, setCompliance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filterDays, setFilterDays] = useState(30);

  useEffect(() => {
    loadPerformanceData();
  }, [token, filterDays]);

  async function loadPerformanceData() {
    try {
      setLoading(true);
      setError("");

      const [metricsRes, auditRes, complianceRes] = await Promise.all([
        fetch("/admin/performance-audit/system-metrics", {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`/admin/performance-audit/audit-log?days=${filterDays}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("/admin/performance-audit/compliance-report", {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (!metricsRes.ok) throw new Error("Failed to load metrics");
      if (!auditRes.ok) throw new Error("Failed to load audit log");
      if (!complianceRes.ok) throw new Error("Failed to load compliance report");

      const metricsData = await metricsRes.json();
      const auditData = await auditRes.json();
      const complianceData = await complianceRes.json();

      setMetrics(metricsData);
      setAuditLog(auditData.logs || []);
      setCompliance(complianceData);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error loading performance data";
      setError(msg);
      onError?.(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="pillar-dashboard performance-audit-dashboard">
      <h2>Performance & Audit</h2>

      {error && (
        <Alert
          type="error"
          title="Error"
          message={error}
          onDismiss={() => setError("")}
        />
      )}

      {/* System Metrics */}
      {metrics && (
        <Card title="System Metrics" subtitle="Platform-wide performance indicators">
          <div className="metrics-grid">
            <MetricBox
              label="Platform P&L"
              value={`$${metrics.platform.total_pnl.toFixed(2)}`}
              subtext={`${metrics.platform.total_trades} trades`}
              tone={metrics.platform.total_pnl >= 0 ? "success" : "error"}
            />
            <MetricBox
              label="Total Volume"
              value={`$${(metrics.platform.total_volume / 1e6).toFixed(1)}M`}
              subtext={`Avg: $${(metrics.platform.total_volume / metrics.platform.total_trades).toFixed(0)}`}
              tone="neutral"
            />
            <MetricBox
              label="Average Win Rate"
              value={`${(metrics.platform.average_win_rate * 100).toFixed(1)}%`}
              tone={metrics.platform.average_win_rate > 0.5 ? "success" : "warning"}
            />
            <MetricBox
              label="Active Users (24h)"
              value={metrics.users.active_24h}
              subtext={`of ${metrics.users.total} total`}
              tone="neutral"
            />
            <MetricBox
              label="Active Agents"
              value={metrics.agents.active}
              subtext={`of ${metrics.agents.total} total`}
              tone="success"
            />
          </div>
        </Card>
      )}

      {/* Audit Log */}
      <Card
        title="Audit Trail"
        subtitle={`Activity log for the last ${filterDays} days`}
        action={
          <div className="filter-controls">
            <select value={filterDays} onChange={(e) => setFilterDays(Number(e.target.value))}>
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value={365}>Last year</option>
            </select>
            <Button variant="secondary">Export</Button>
          </div>
        }
      >
        <DataTable
          columns={[
            {
              key: "action",
              label: "Action",
              width: "20%",
              render: (action) => <Badge type={action}>{action}</Badge>,
            },
            { key: "user_id", label: "User", width: "20%" },
            { key: "resource", label: "Resource", width: "15%" },
            {
              key: "impact",
              label: "Impact",
              width: "15%",
              render: (impact) => (
                <Badge
                  type={
                    impact === "success"
                      ? "success"
                      : impact === "error"
                        ? "error"
                        : "warning"
                  }
                >
                  {impact || "--"}
                </Badge>
              ),
            },
            { key: "timestamp", label: "Time", width: "15%" },
            { key: "ip", label: "IP Address", width: "15%" },
          ]}
          rows={auditLog}
        />
      </Card>

      {/* Compliance Report */}
      {compliance && (
        <Card
          title="Compliance Summary"
          subtitle="Regulatory and risk compliance status"
          action={<Button variant="secondary">Generate Report</Button>}
        >
          <div className="compliance-summary">
            <div className="compliance-section">
              <h4>Period</h4>
              <p>
                {compliance.period.start} to {compliance.period.end}
              </p>
            </div>
            <div className="compliance-section">
              <h4>Users & Trading</h4>
              <dl>
                <dt>Total Users:</dt>
                <dd>{compliance.summary.total_users}</dd>
                <dt>Active Traders:</dt>
                <dd>{compliance.summary.active_traders}</dd>
                <dt>Audit Events:</dt>
                <dd>{compliance.summary.audit_events}</dd>
              </dl>
            </div>
            <div className="compliance-section">
              <h4>Risk & Compliance</h4>
              <dl>
                <dt>Compliance Incidents:</dt>
                <dd className={compliance.summary.compliance_incidents > 0 ? "error" : "success"}>
                  {compliance.summary.compliance_incidents}
                </dd>
              </dl>
            </div>
          </div>
        </Card>
      )}

      {/* Performance Trending */}
      <Card title="Performance Trending" subtitle="Historical performance metrics">
        <div className="trending-chart">
          <p>Performance chart would display here</p>
          <p className="hint">Shows platform P&L, Sharpe ratio, and drawdown over time</p>
        </div>
      </Card>

      {/* Top Performers */}
      <Card title="Top Performers" subtitle="Best traders and agents">
        <div className="performers-container">
          <div className="performers-section">
            <h4>Top Traders</h4>
            <p className="hint">Ranking by return percentage</p>
          </div>
          <div className="performers-section">
            <h4>Top Agents</h4>
            <p className="hint">Ranking by P&L</p>
          </div>
        </div>
      </Card>

      {/* Compliance Sections */}
      <div className="compliance-cards">
        <Card title="User Management Compliance" subtitle="Access control and roles">
          <p className="hint">User creation, role changes, and access audit</p>
        </Card>
        <Card title="Trading Activity Compliance" subtitle="Order and execution audit">
          <p className="hint">Order placement, cancellation, and execution tracking</p>
        </Card>
        <Card title="Risk Management Compliance" subtitle="Limit breaches and controls">
          <p className="hint">Risk limit enforcement and breach notifications</p>
        </Card>
        <Card title="License Compliance" subtitle="Subscription and feature entitlements">
          <p className="hint">License validity and feature access verification</p>
        </Card>
        <Card title="System Security" subtitle="Access logs and security events">
          <p className="hint">Login attempts, API access, and security incidents</p>
        </Card>
      </div>
    </div>
  );
}
