/**
 * Operations Pillar Dashboard
 * System monitoring, broker connectivity, deployment status
 */

import { useState, useEffect } from "react";
import { operationsDashboardService } from "../api/services";
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

      const [healthData, brokerData, statsData] = await Promise.all([
        operationsDashboardService.getHealth(token),
        operationsDashboardService.getBrokerStatus(token),
        operationsDashboardService.getTradeStats(token, "1h"),
      ]);

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

      {/* Broker Connectivity */}
      <Card title="Broker Connectivity" subtitle="Connection status to trading venues">
        <div className="broker-status">
          <MetricBox
            label="Overall"
            value={
              <>
                <StatusIndicator status={brokerStatus?.overall || "offline"} />
                {brokerStatus?.overall || "offline"}
              </>
            }
          />
          {brokerStatus?.brokers && Object.entries(brokerStatus.brokers).map(([broker, status]) => (
            <div key={broker} className="broker-item">
              <StatusIndicator status={status.status} />
              <span>{broker}</span>
            </div>
          ))}
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
