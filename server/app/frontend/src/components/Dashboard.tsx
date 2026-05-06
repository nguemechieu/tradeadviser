
import './Dashboard.css'

const Dashboard = () => {
  const stats = [
    {
      label: "Portfolio Balance",
      value: "$124,580.42",
      change: "+8.42%",
      status: "positive",
    },
    {
      label: "Open Positions",
      value: "12",
      change: "4 active markets",
      status: "neutral",
    },
    {
      label: "Today’s P/L",
      value: "+$2,840.18",
      change: "+2.31%",
      status: "positive",
    },
    {
      label: "Risk Exposure",
      value: "18.7%",
      change: "Within limits",
      status: "safe",
    },
  ];

  const markets = [
    { symbol: "BTC/USDT", market: "Crypto", signal: "Buy", confidence: "87%" },
    { symbol: "EUR/USD", market: "Forex", signal: "Hold", confidence: "62%" },
    { symbol: "AAPL", market: "Stocks", signal: "Buy", confidence: "74%" },
    { symbol: "ETH/USDT", market: "Crypto", signal: "Sell", confidence: "69%" },
  ];

  return (
    <main className="dashboard-page">
      <section className="dashboard-hero">
        <div>
          <span className="dashboard-kicker">TradeAdviser Terminal</span>
          <h1>Dashboard</h1>
          <p>
            Welcome back. Monitor your portfolio, AI trade signals, risk
            exposure, and live market activity from one professional workspace.
          </p>
        </div>

        <div className="dashboard-actions">
          <button className="btn btn-secondary">View Reports</button>
          <button className="btn btn-primary">New Trade</button>
        </div>
      </section>

      <section className="dashboard-stats">
        {stats.map((item) => (
          <div className="dashboard-card" key={item.label}>
            <p className="dashboard-card-label">{item.label}</p>
            <h2>{item.value}</h2>
            <span className={`dashboard-badge ${item.status}`}>
              {item.change}
            </span>
          </div>
        ))}
      </section>

      <section className="dashboard-grid">
        <div className="dashboard-panel">
          <div className="panel-header">
            <div>
              <h2>AI Market Signals</h2>
              <p>Latest multi-asset trading recommendations.</p>
            </div>
            <span className="live-badge">Live</span>
          </div>

          <div className="market-list">
            {markets.map((item) => (
              <div className="market-row" key={item.symbol}>
                <div>
                  <strong>{item.symbol}</strong>
                  <span>{item.market}</span>
                </div>

                <div className="market-signal">
                  <span className={`signal ${item.signal.toLowerCase()}`}>
                    {item.signal}
                  </span>
                  <small>{item.confidence}</small>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="dashboard-panel">
          <div className="panel-header">
            <div>
              <h2>System Status</h2>
              <p>Execution, broker, and risk engine health.</p>
            </div>
          </div>

          <div className="status-list">
            <div className="status-row">
              <span>Broker Connection</span>
              <strong className="status-online">Online</strong>
            </div>

            <div className="status-row">
              <span>Risk Engine</span>
              <strong className="status-online">Active</strong>
            </div>

            <div className="status-row">
              <span>AI Reasoning Layer</span>
              <strong className="status-online">Ready</strong>
            </div>

            <div className="status-row">
              <span>Auto Trading</span>
              <strong className="status-warning">Manual Mode</strong>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
};

export default Dashboard;