/**
 * Operations Dashboard View
 * System health, broker status, connections, deployment status
 */

export default function OperationsView({ token, loading, onRefresh }) {
  const [systemHealth, setSystemHealth] = React.useState(null);
  const [brokerStatus, setBrokerStatus] = React.useState(null);
  const [connections, setConnections] = React.useState(null);
  const [deploymentStatus, setDeploymentStatus] = React.useState(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!token) return;
    loadOperationsData();
  }, [token]);

  async function loadOperationsData() {
    try {
      setError("");
      const { operations: ops } = await import("../api/services");

      const [health, broker, conn, deploy] = await Promise.all([
        ops.getSystemHealth(token),
        ops.getBrokerStatus(token),
        ops.getActiveConnections(token),
        ops.getDeploymentStatus(token),
      ]);

      setSystemHealth(health);
      setBrokerStatus(broker);
      setConnections(conn);
      setDeploymentStatus(deploy);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load operations data");
    }
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>System Operations</h2>
        <button onClick={loadOperationsData} disabled={loading}>
          Refresh
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {systemHealth && (
        <div className="operations-grid">
          <div className="metric-card">
            <p className="eyebrow">System Status</p>
            <p className={`status-pill status-pill--${systemHealth.status === "ok" ? "success" : "error"}`}>
              {systemHealth.status || "Unknown"}
            </p>
          </div>

          {systemHealth.services && (
            <>
              <div className="metric-card">
                <p className="eyebrow">Database</p>
                <p>{systemHealth.services.database?.status || "N/A"}</p>
                <small>{systemHealth.services.database?.response_ms}ms</small>
              </div>
              <div className="metric-card">
                <p className="eyebrow">API</p>
                <p>{systemHealth.services.api?.status || "N/A"}</p>
                <small>{systemHealth.services.api?.connections} connections</small>
              </div>
              <div className="metric-card">
                <p className="eyebrow">WebSocket</p>
                <p>{systemHealth.services.websocket?.status || "N/A"}</p>
                <small>{systemHealth.services.websocket?.clients} clients</small>
              </div>
            </>
          )}

          {systemHealth.resources && (
            <>
              <div className="metric-card">
                <p className="eyebrow">CPU</p>
                <p>{systemHealth.resources.cpu_percent?.toFixed(1)}%</p>
              </div>
              <div className="metric-card">
                <p className="eyebrow">Memory</p>
                <p>{systemHealth.resources.memory_percent?.toFixed(1)}%</p>
              </div>
              <div className="metric-card">
                <p className="eyebrow">Disk</p>
                <p>{systemHealth.resources.disk_percent?.toFixed(1)}%</p>
              </div>
            </>
          )}
        </div>
      )}

      {brokerStatus && (
        <div className="panel">
          <div className="panel__header">
            <p className="eyebrow">Broker Status</p>
          </div>
          <pre className="json-block">{JSON.stringify(brokerStatus, null, 2)}</pre>
        </div>
      )}

      {deploymentStatus && (
        <div className="panel">
          <div className="panel__header">
            <p className="eyebrow">Deployment Status</p>
          </div>
          <pre className="json-block">{JSON.stringify(deploymentStatus, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}
