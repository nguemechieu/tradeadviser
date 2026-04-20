/**
 * Agents & AI Pillar Dashboard
 * AI agent deployment, configuration, and performance monitoring
 */

import { useState, useEffect } from "react";
import { Card, MetricBox, DataTable, StatusIndicator, Badge, Button } from "./shared";

export function AgentsDashboard({ token, onError }) {
  const [overview, setOverview] = useState(null);
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadAgentsData();
    const interval = setInterval(loadAgentsData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [token]);

  async function loadAgentsData() {
    try {
      setLoading(true);
      setError("");

      const [overviewRes, agentsRes] = await Promise.all([
        fetch("/admin/agents/overview", {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("/admin/agents/", {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (!overviewRes.ok) throw new Error("Failed to load agents overview");
      if (!agentsRes.ok) throw new Error("Failed to load agents");

      const overviewData = await overviewRes.json();
      const agentsData = await agentsRes.json();

      setOverview(overviewData);
      setAgents(agentsData.agents || []);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error loading agents data";
      setError(msg);
      onError?.(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="pillar-dashboard agents-dashboard">
      <h2>Agents & AI</h2>

      {error && (
        <Alert
          type="error"
          title="Error"
          message={error}
          onDismiss={() => setError("")}
        />
      )}

      {/* Agent Overview */}
      {overview && (
        <Card title="Agent Overview" subtitle="Platform AI agent status">
          <div className="metrics-grid">
            <MetricBox
              label="Total Agents"
              value={overview.total}
              tone="neutral"
            />
            <MetricBox
              label="Active Agents"
              value={overview.active}
              tone="success"
            />
            <MetricBox
              label="Paused Agents"
              value={overview.paused}
              tone="warning"
            />
          </div>
        </Card>
      )}

      {/* Top Performers */}
      {overview?.top_performers && overview.top_performers.length > 0 && (
        <Card title="Top Performing Agents" subtitle="Best performing agents by P&L">
          <div className="top-performers">
            {overview.top_performers.map((agent) => (
              <div key={agent.id} className="performer-card">
                <h4>{agent.name}</h4>
                <div className="performer-stats">
                  <span className="stat">
                    <strong>${agent.pnl.toFixed(2)}</strong> P&L
                  </span>
                  <span className="stat">
                    <strong>{(agent.return * 100).toFixed(1)}%</strong> Return
                  </span>
                  <span className="stat">
                    <strong>{agent.trades}</strong> Trades
                  </span>
                  <span className="stat">
                    <strong>{(agent.win_rate * 100).toFixed(1)}%</strong> Win Rate
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Agents Table */}
      <Card
        title="All Agents"
        subtitle="Deployed agents and their status"
        action={<Button variant="primary">+ Deploy Agent</Button>}
      >
        <DataTable
          columns={[
            { key: "name", label: "Name", width: "20%" },
            {
              key: "status",
              label: "Status",
              width: "15%",
              render: (status) => (
                <>
                  <StatusIndicator status={status} size="small" />
                  <Badge type={status}>{status}</Badge>
                </>
              ),
            },
            { key: "model_type", label: "Type", width: "12%" },
            {
              key: "is_active",
              label: "Active",
              width: "10%",
              render: (active) => <Badge type={active ? "success" : "error"}>{active ? "Yes" : "No"}</Badge>,
            },
            {
              key: "performance.trades",
              label: "Trades",
              width: "8%",
              render: (_, row) => row.performance?.trades || 0,
            },
            {
              key: "performance.pnl",
              label: "P&L",
              width: "12%",
              render: (_, row) => {
                const pnl = row.performance?.pnl || 0;
                return (
                  <span className={pnl >= 0 ? "positive" : "negative"}>
                    ${pnl.toFixed(2)}
                  </span>
                );
              },
            },
            {
              key: "performance.win_rate",
              label: "Win Rate",
              width: "10%",
              render: (_, row) => `${((row.performance?.win_rate || 0) * 100).toFixed(1)}%`,
            },
            { key: "created_at", label: "Created", width: "13%" },
          ]}
          rows={agents}
          onRowClick={(agent) => setSelectedAgent(agent)}
        />
      </Card>

      {/* Agent Details */}
      {selectedAgent && (
        <Card
          title={`Agent: ${selectedAgent.name}`}
          subtitle={selectedAgent.description}
          action={<Button variant="secondary">Edit</Button>}
        >
          <div className="agent-details">
            <div className="detail-section">
              <h4>Status & Configuration</h4>
              <dl>
                <dt>Status:</dt>
                <dd>
                  <StatusIndicator status={selectedAgent.status} />
                  {selectedAgent.status}
                </dd>
                <dt>Active:</dt>
                <dd>{selectedAgent.is_active ? "Running" : "Stopped"}</dd>
                <dt>Model Type:</dt>
                <dd>{selectedAgent.model_type}</dd>
                <dt>Version:</dt>
                <dd>{selectedAgent.model_version}</dd>
              </dl>
            </div>
            <div className="detail-section">
              <h4>Performance</h4>
              <dl>
                <dt>Total Trades:</dt>
                <dd>{selectedAgent.performance?.total_trades || 0}</dd>
                <dt>Win Rate:</dt>
                <dd>{((selectedAgent.performance?.win_rate || 0) * 100).toFixed(1)}%</dd>
                <dt>Cumulative P&L:</dt>
                <dd className={selectedAgent.performance?.cumulative_pnl >= 0 ? "positive" : "negative"}>
                  ${selectedAgent.performance?.cumulative_pnl?.toFixed(2) || "0.00"}
                </dd>
                <dt>Total Return:</dt>
                <dd>{((selectedAgent.performance?.total_return || 0) * 100).toFixed(1)}%</dd>
                <dt>Sharpe Ratio:</dt>
                <dd>{selectedAgent.performance?.sharpe_ratio?.toFixed(2) || "--"}</dd>
                <dt>Max Drawdown:</dt>
                <dd>{selectedAgent.performance?.max_drawdown?.toFixed(1) || "--"}%</dd>
              </dl>
            </div>
            <div className="detail-section">
              <h4>Limits</h4>
              <dl>
                <dt>Max Position Size:</dt>
                <dd>${selectedAgent.limits?.max_position_size || "--"}</dd>
                <dt>Daily Loss Limit:</dt>
                <dd>${selectedAgent.limits?.daily_loss_limit || "--"}</dd>
              </dl>
            </div>
            <div className="detail-section">
              <h4>Recent Audit Log</h4>
              {selectedAgent.audit_log && selectedAgent.audit_log.length > 0 ? (
                <ul className="audit-log">
                  {selectedAgent.audit_log.slice(0, 5).map((log, i) => (
                    <li key={i}>
                      <strong>{log.action}</strong> - {log.timestamp}
                      {log.details && <p className="hint">{log.details}</p>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="hint">No recent activity</p>
              )}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
