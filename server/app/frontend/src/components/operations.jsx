/**
 * Operations Pillar Dashboard
 * System monitoring, broker connectivity, deployment status
 */

import { useState, useEffect } from "react";
import { Card, MetricBox, StatusIndicator, DataTable, Alert, LoadingSpinner } from "./shared";

export function OperationsDashboard({ token, onError }) {
  const [health, setHealth] = useState(null);
  const [brokerStatus, setBrokerStatus] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadOperationsData();
    const interval = setInterval(loadOperationsData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [token]);

  async function loadOperationsData() {
    try {
      setLoading(true);
      setError("");

      const [healthRes, brokerRes, statsRes] = await Promise.all([
        fetch("/api/v3/admin/operations/health", {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("/api/v3/admin/operations/broker-status", {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("/api/v3/admin/operations/trade-stats?period=1h", {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (!healthRes.ok) throw new Error("Failed to load health data");
      if (!brokerRes.ok) throw new Error("Failed to load broker status");
      if (!statsRes.ok) throw new Error("Failed to load statistics");

      const healthData = await healthRes.json();
      const brokerData = await brokerRes.json();
      const statsData = await statsRes.json();

      setHealth(healthData);
      setBrokerStatus(brokerData);
      setStats(statsData);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error loading operations data";
      setError(msg);
      onError?.(msg);
    } finally {
      setLoading(false);
    }
  }

  if (loading && !health) {
    return <LoadingSpinner />;
  }

  return (
    <div className="pillar-dashboard operations-dashboard">
      <h2>Operations</h2>

      {error && (
        <Alert
          type="error"
          title="Error"
          message={error}
          onDismiss={() => setError("")}
        />
      )}

      {/* System Status Overview */}
      <Card title="System Status" subtitle="Overall health and resources">
        <div className="metrics-grid">
          <MetricBox
            label="Overall Status"
            value={
              <>
                <StatusIndicator status={health?.status || "offline"} />
                {health?.status || "offline"}
              </>
            }
            tone={health?.status === "healthy" ? "success" : "warning"}
          />
          <MetricBox
            label="CPU Usage"
            value={`${Math.round(health?.resources.cpu_percent || 0)}%`}
            tone={health?.resources.cpu_percent > 80 ? "error" : "neutral"}
          />
          <MetricBox
            label="Memory Usage"
            value={`${Math.round(health?.resources.memory_percent || 0)}%`}
            tone={health?.resources.memory_percent > 85 ? "error" : "neutral"}
          />
          <MetricBox
            label="Disk Usage"
            value={`${Math.round(health?.resources.disk_percent || 0)}%`}
            tone={health?.resources.disk_percent > 90 ? "error" : "neutral"}
          />
        </div>
      </Card>

      {/* Service Health */}
      <Card title="Services" subtitle="Individual service status">
        <div className="services-grid">
          {health?.services && Object.entries(health.services).map(([name, service]) => (
            <div key={name} className="service-item">
              <div className="service-header">
                <StatusIndicator status={service?.status || "offline"} />
                <span className="service-name">{name}</span>
              </div>
              {service?.response_ms && (
                <p className="service-detail">{service.response_ms}ms response</p>
              )}
              {service?.connections && (
                <p className="service-detail">{service.connections} active</p>
              )}
              {service?.clients && (
                <p className="service-detail">{service.clients} connected</p>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Trading Venues - InvestPro Style */}
      <Card title="Trading Venues" subtitle="Real-time connection status and performance metrics">
        <div className="venues-container">
          {/* Overall Status Summary */}
          <div className="venues-summary">
            <div className="summary-item">
              <div className="summary-value">
                <StatusIndicator status={brokerStatus?.overall || "offline"} size="large" />
              </div>
              <div className="summary-text">
                <p className="summary-label">Overall Status</p>
                <p className="summary-status">{brokerStatus?.overall || "offline"}</p>
              </div>
            </div>
            {brokerStatus?.brokers && (
              <>
                <div className="summary-item">
                  <div className="summary-value">{Object.keys(brokerStatus.brokers).filter(b => brokerStatus.brokers[b].status === 'healthy').length}</div>
                  <div className="summary-text">
                    <p className="summary-label">Connected Venues</p>
                    <p className="summary-status">{Object.keys(brokerStatus.brokers).length} Total</p>
                  </div>
                </div>
                <div className="summary-item">
                  <div className="summary-value">{brokerStatus?.avg_latency_ms?.toFixed(0) || 0}ms</div>
                  <div className="summary-text">
                    <p className="summary-label">Avg Latency</p>
                    <p className="summary-status">Network Response</p>
                  </div>
                </div>
                <div className="summary-item">
                  <div className="summary-value">{brokerStatus?.total_volume_24h || 0}</div>
                  <div className="summary-text">
                    <p className="summary-label">24h Volume</p>
                    <p className="summary-status">Traded</p>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Venues Table */}
          {brokerStatus?.brokers && (
            <div className="venues-table-wrapper">
              <table className="venues-table">
                <thead>
                  <tr>
                    <th className="col-status">Status</th>
                    <th className="col-venue">Venue Name</th>
                    <th className="col-type">Type</th>
                    <th className="col-latency">Latency</th>
                    <th className="col-connections">Active Connections</th>
                    <th className="col-uptime">Uptime</th>
                    <th className="col-volume">Volume (24h)</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(brokerStatus.brokers).map(([venue, data]) => (
                    <tr key={venue} className={`venue-row venue-${data.status}`}>
                      <td className="col-status">
                        <StatusIndicator status={data.status} />
                      </td>
                      <td className="col-venue">
                        <div className="venue-name">
                          <span className="venue-icon">{data.icon || '📊'}</span>
                          <span className="venue-label">{venue}</span>
                        </div>
                      </td>
                      <td className="col-type">
                        <span className="venue-type">{data.type || 'Broker'}</span>
                      </td>
                      <td className="col-latency">
                        <span className={`latency-value latency-${data.latency_ms > 200 ? 'high' : data.latency_ms > 100 ? 'medium' : 'low'}`}>
                          {data.latency_ms || 0}ms
                        </span>
                      </td>
                      <td className="col-connections">
                        <span className="connection-count">{data.connections || 0}</span>
                      </td>
                      <td className="col-uptime">
                        <div className="uptime-bar">
                          <div 
                            className="uptime-fill" 
                            style={{ width: `${(data.uptime_pct || 100) * 100}%` }}
                          />
                        </div>
                        <span className="uptime-text">{(data.uptime_pct || 100).toFixed(1)}%</span>
                      </td>
                      <td className="col-volume">
                        <span className="volume-value">${(data.volume_24h || 0) / 1e6 > 0 ? (data.volume_24h / 1e6).toFixed(1) : 0}M</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      {/* Trading Statistics */}
      {stats && (
        <Card title="Trading Activity" subtitle="Last hour statistics">
          <div className="metrics-grid">
            <MetricBox label="Total Trades" value={stats.trades.total} />
            <MetricBox label="Avg Trade P&L" value={`$${stats.trades.average_pnl.toFixed(2)}`} />
            <MetricBox label="Win Rate" value={`${(stats.trades.win_rate * 100).toFixed(1)}%`} />
            <MetricBox label="Active Users" value={stats.users.active_24h} />
            <MetricBox label="Total Volume" value={`$${(stats.volume.total / 1e6).toFixed(1)}M`} />
            <MetricBox label="Active Agents" value={stats.agents.active} />
          </div>
        </Card>
      )}

      {/* Active Connections */}
      <Card title="Connections" subtitle="Current API and WebSocket activity">
        <div className="metrics-grid">
          <MetricBox label="API Connections" value={health?.services.api?.connections || 0} />
          <MetricBox label="WebSocket Clients" value={health?.services.websocket?.clients || 0} />
        </div>
      </Card>
    </div>
  );
}
