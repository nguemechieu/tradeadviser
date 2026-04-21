/**
 * Risk Management View
 * Portfolio risk limits, breaches, monitoring
 */

export default function RiskView({ token, loading, onRefresh }) {
  const [overview, setOverview] = React.useState(null);
  const [breaches, setBreaches] = React.useState([]);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!token) return;
    loadRiskData();
  }, [token]);

  async function loadRiskData() {
    try {
      setError("");
      const { risk: riskSvc } = await import("../api/services");

      const [overviewData, breachesData] = await Promise.all([
        riskSvc.getOverview(token),
        riskSvc.getRecentBreaches(token).catch(() => []),
      ]);

      setOverview(overviewData);
      setBreaches(breachesData || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load risk data");
    }
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Risk Management</h2>
        <button onClick={loadRiskData} disabled={loading}>
          Refresh
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {overview && (
        <div className="risk-grid">
          <div className="metric-card">
            <p className="eyebrow">Total Users</p>
            <p>{overview.total_users || 0}</p>
          </div>
          <div className="metric-card">
            <p className="eyebrow">Users with Limits</p>
            <p>{overview.users_with_limits || 0}</p>
          </div>
          <div className="metric-card">
            <p className="eyebrow eyebrow--warning">Recent Breaches</p>
            <p className="status-pill status-pill--error">{overview.recent_breaches || 0}</p>
          </div>
          {overview.breach_types && overview.breach_types.length > 0 && (
            <div className="metric-card">
              <p className="eyebrow">Breach Types</p>
              <p>{overview.breach_types.join(", ")}</p>
            </div>
          )}
        </div>
      )}

      {breaches.length > 0 && (
        <div className="breaches-list">
          <div className="panel__header">
            <p className="eyebrow">Recent Breaches</p>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Limit Type</th>
                <th>Limit</th>
                <th>Current</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {breaches.map((breach, idx) => (
                <tr key={idx}>
                  <td>{breach.user_id}</td>
                  <td>{breach.limit_type}</td>
                  <td>{breach.limit_value}</td>
                  <td>{breach.current_value}</td>
                  <td>{new Date(breach.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
