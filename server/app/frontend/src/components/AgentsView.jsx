/**
 * Agents Management View
 * AI agent overview, list, performance, control
 */

export default function AgentsView({ token, loading, onRefresh }) {
  const [overview, setOverview] = React.useState(null);
  const [agents, setAgents] = React.useState([]);
  const [selectedAgent, setSelectedAgent] = React.useState(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    if (!token) return;
    loadAgentsData();
  }, [token]);

  async function loadAgentsData() {
    try {
      setError("");
      const { agents: agentsSvc } = await import("../api/services");

      const [overviewData, agentsList] = await Promise.all([
        agentsSvc.getOverview(token),
        agentsSvc.list(token),
      ]);

      setOverview(overviewData);
      setAgents(agentsList);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load agents data");
    }
  }

  async function handlePauseAgent(agentId) {
    try {
      const { agents: agentsSvc } = await import("../api/services");
      await agentsSvc.pauseAgent(agentId, token);
      loadAgentsData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to pause agent");
    }
  }

  async function handleResumeAgent(agentId) {
    try {
      const { agents: agentsSvc } = await import("../api/services");
      await agentsSvc.resumeAgent(agentId, token);
      loadAgentsData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resume agent");
    }
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>AI Agents</h2>
        <button onClick={loadAgentsData} disabled={loading}>
          Refresh
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {overview && (
        <div className="agents-grid">
          <div className="metric-card">
            <p className="eyebrow">Total Agents</p>
            <p>{overview.total || 0}</p>
          </div>
          <div className="metric-card">
            <p className="eyebrow">Active</p>
            <p className="status-pill status-pill--success">{overview.active || 0}</p>
          </div>
          <div className="metric-card">
            <p className="eyebrow">Paused</p>
            <p className="status-pill status-pill--warning">{overview.paused || 0}</p>
          </div>
        </div>
      )}

      {agents.length > 0 && (
        <div className="agents-list">
          <table className="data-table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Type</th>
                <th>Status</th>
                <th>P&L</th>
                <th>Win Rate</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.id} onClick={() => setSelectedAgent(agent)}>
                  <td>{agent.name}</td>
                  <td>{agent.model_type}</td>
                  <td>
                    <span
                      className={`status-pill status-pill--${
                        agent.is_active ? "success" : "warning"
                      }`}
                    >
                      {agent.is_active ? "Active" : "Paused"}
                    </span>
                  </td>
                  <td>{agent.cumulative_pnl?.toFixed(2) || "N/A"}</td>
                  <td>{agent.win_rate?.toFixed(1)}% || "N/A"</td>
                  <td>
                    {agent.is_active ? (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePauseAgent(agent.id);
                        }}
                      >
                        Pause
                      </button>
                    ) : (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleResumeAgent(agent.id);
                        }}
                      >
                        Resume
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedAgent && (
        <div className="panel">
          <div className="panel__header">
            <p className="eyebrow">Agent Details</p>
          </div>
          <pre className="json-block">{JSON.stringify(selectedAgent, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}
