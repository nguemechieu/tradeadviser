/**
 * Performance Audit View
 * Detailed performance metrics and audit trail
 */

export default function PerformanceAuditView({ token, loading, onRefresh }) {
  const [report, setReport] = React.useState(null);
  const [metrics, setMetrics] = React.useState(null);
  const [period, setPeriod] = React.useState("1d");
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!token) return;
    loadAuditData();
  }, [token, period]);

  async function loadAuditData() {
    try {
      setError("");
      const { performanceAudit } = await import("../api/services");

      const reportData = await performanceAudit.getReport(token, period);
      setReport(reportData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit data");
    }
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Performance Audit</h2>
        <div className="header-controls">
          <select value={period} onChange={(e) => setPeriod(e.target.value)}>
            <option value="1h">1 Hour</option>
            <option value="1d">1 Day</option>
            <option value="7d">7 Days</option>
            <option value="30d">30 Days</option>
          </select>
          <button onClick={loadAuditData} disabled={loading}>
            Refresh
          </button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {report && (
        <div className="audit-section">
          <pre className="json-block">{JSON.stringify(report, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}
