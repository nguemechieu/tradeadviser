/**
 * Risk Pillar Dashboard
 * Portfolio risk monitoring, risk limits, and breach alerts
 */

import { useState, useEffect } from "react";
import { Card, MetricBox, StatusIndicator, DataTable, Alert, Badge } from "./shared";

export function RiskDashboard({ token, onError }) {
  const [overview, setOverview] = useState(null);
  const [breaches, setBreaches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadRiskData();
    const interval = setInterval(loadRiskData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [token]);

  async function loadRiskData() {
    try {
      setLoading(true);
      setError("");

      const [overviewRes, breachesRes] = await Promise.all([
        fetch("/admin/risk/overview", {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("/admin/risk/breaches", {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (!overviewRes.ok) throw new Error("Failed to load risk overview");
      if (!breachesRes.ok) throw new Error("Failed to load breaches");

      const overviewData = await overviewRes.json();
      const breachesData = await breachesRes.json();

      setOverview(overviewData);
      setBreaches(breachesData.breaches || []);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error loading risk data";
      setError(msg);
      onError?.(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="pillar-dashboard risk-dashboard">
      <h2>Risk Management</h2>

      {error && (
        <Alert
          type="error"
          title="Error"
          message={error}
          onDismiss={() => setError("")}
        />
      )}

      {/* Risk Overview */}
      {overview && (
        <Card title="Risk Overview" subtitle="Platform-wide risk status">
          <div className="metrics-grid">
            <MetricBox
              label="Users with Limits"
              value={overview.users_with_limits}
              tone="neutral"
            />
            <MetricBox
              label="Recent Breaches"
              value={overview.recent_breaches}
              tone={overview.recent_breaches > 0 ? "warning" : "success"}
            />
            <MetricBox
              label="Breach Types"
              value={overview.breach_types.join(", ") || "None"}
              tone="neutral"
            />
          </div>
        </Card>
      )}

      {/* Recent Breaches */}
      {breaches.length > 0 && (
        <Card title="Recent Risk Breaches" subtitle="Recent limit violations">
          <DataTable
            columns={[
              { key: "user_id", label: "User", width: "20%" },
              { key: "limit_type", label: "Type", width: "25%" },
              {
                key: "value",
                label: "Value",
                width: "15%",
                render: (v) => `$${v?.toFixed(2)}`,
              },
              {
                key: "limit",
                label: "Limit",
                width: "15%",
                render: (v) => `$${v?.toFixed(2)}`,
              },
              { key: "action", label: "Action", width: "15%" },
              { key: "timestamp", label: "Time", width: "10%" },
            ]}
            rows={breaches}
          />
        </Card>
      )}

      {/* Portfolio Heat Map */}
      <Card title="Portfolio Heat Map" subtitle="Exposure concentration by user">
        <div className="heat-map-placeholder">
          <p>Heat map visualization would display here</p>
          <p>Shows concentration of positions and exposure across user base</p>
        </div>
      </Card>

      {/* Symbol Exposure */}
      <Card title="Symbol Exposure" subtitle="Aggregate platform exposure">
        <div className="exposure-grid">
          <MetricBox
            label="Total Platform Exposure"
            value="--"
            subtext="Aggregated across all users"
          />
          <MetricBox
            label="Max Single Symbol"
            value="--"
            subtext="Highest concentration risk"
          />
          <MetricBox
            label="Leverage Utilization"
            value="--"
            subtext="% of available leverage in use"
          />
        </div>
      </Card>

      {/* Risk Limits Summary */}
      <Card title="Risk Limits Summary" subtitle="Platform risk configuration">
        <div className="risk-limits-info">
          <p>Click on a user to view/edit their specific risk limits</p>
          <p className="hint">Risk limits are critical for institutional compliance</p>
        </div>
      </Card>
    </div>
  );
}
