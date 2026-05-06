import React, { useState } from 'react';
import './ProTradingTerminal.css';

interface TradingBot {
  id: string;
  name: string;
  strategy: string;
  status: 'running' | 'paused' | 'stopped';
  pair: string;
  profit: number;
  trades: number;
  winRate: number;
  lastTrade: string;
}

interface Signal {
  id: string;
  coin: string;
  action: 'buy' | 'sell';
  price: number;
  strength: number;
  timestamp: string;
  source: string;
}

interface Trade {
  id: string;
  pair: string;
  action: 'buy' | 'sell';
  price: number;
  amount: number;
  total: number;
  profit: number;
  timestamp: string;
  status: 'completed' | 'pending' | 'failed';
}

const ProTradingTerminal: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'terminal' | 'bots' | 'signals' | 'trades' | 'settings'>('terminal');
  
  const [bots] = useState<TradingBot[]>([
    {
      id: '1',
      name: 'Golden Trend Bot',
      strategy: 'Moving Average Crossover',
      status: 'running',
      pair: 'BTC/USDT',
      profit: 2450.50,
      trades: 45,
      winRate: 68,
      lastTrade: '2 minutes ago',
    },
    {
      id: '2',
      name: 'RSI Scalper',
      strategy: 'RSI Overbought/Oversold',
      status: 'running',
      pair: 'ETH/USDT',
      profit: 1234.75,
      trades: 78,
      winRate: 62,
      lastTrade: '5 minutes ago',
    },
    {
      id: '3',
      name: 'Breakout Hunter',
      strategy: 'Support/Resistance Break',
      status: 'paused',
      pair: 'XRP/USDT',
      profit: -450.25,
      trades: 23,
      winRate: 45,
      lastTrade: '1 hour ago',
    },
  ]);

  const [signals] = useState<Signal[]>([
    {
      id: '1',
      coin: 'BTC',
      action: 'buy',
      price: 67850.50,
      strength: 0.92,
      timestamp: 'now',
      source: 'MA Crossover',
    },
    {
      id: '2',
      coin: 'ETH',
      action: 'sell',
      price: 3450.25,
      strength: 0.85,
      timestamp: '2 min ago',
      source: 'RSI Signal',
    },
    {
      id: '3',
      coin: 'SOL',
      action: 'buy',
      price: 145.75,
      strength: 0.78,
      timestamp: '5 min ago',
      source: 'Breakout Alert',
    },
    {
      id: '4',
      coin: 'ADA',
      action: 'sell',
      price: 0.95,
      strength: 0.72,
      timestamp: '10 min ago',
      source: 'Trend Reversal',
    },
  ]);

  const [trades] = useState<Trade[]>([
    {
      id: '1',
      pair: 'BTC/USDT',
      action: 'buy',
      price: 67200,
      amount: 0.05,
      total: 3360,
      profit: 325.50,
      timestamp: '2 hours ago',
      status: 'completed',
    },
    {
      id: '2',
      pair: 'ETH/USDT',
      action: 'sell',
      price: 3420,
      amount: 1.5,
      total: 5130,
      profit: -85.25,
      timestamp: '1 hour ago',
      status: 'completed',
    },
    {
      id: '3',
      pair: 'XRP/USDT',
      action: 'buy',
      price: 2.45,
      amount: 100,
      total: 245,
      profit: 0,
      timestamp: '15 minutes ago',
      status: 'pending',
    },
  ]);

  const [selectedBot, setSelectedBot] = useState<TradingBot | null>(bots[0]);
  const [botControls, setBotControls] = useState({
    mode: 'manual',
    riskLevel: 'medium',
    maxDrawdown: 10,
    profitTarget: 5,
    tradeAmount: 100,
  });

  const handleBotAction = (botId: string, action: 'start' | 'stop' | 'pause') => {
    alert(`Bot ${botId} ${action}ed`);
  };

  const totalProfit = bots.reduce((sum, bot) => sum + bot.profit, 0);
  const totalTrades = bots.reduce((sum, bot) => sum + bot.trades, 0);
  const avgWinRate = Math.round(bots.reduce((sum, bot) => sum + bot.winRate, 0) / bots.length);

  return (
    <section className="pro-trading-terminal">
      {/* Header */}
      <div className="terminal-header">
        <div className="header-content">
          <h1>🚀 Pro Trading Terminal</h1>
          <p>Advanced automated trading with AI-powered signals and bot management</p>
        </div>
        <div className="header-stats">
          <div className="stat">
            <span className="stat-label">Portfolio</span>
            <span className={`stat-value ${totalProfit >= 0 ? 'positive' : 'negative'}`}>
              ${totalProfit.toFixed(2)}
            </span>
          </div>
          <div className="stat">
            <span className="stat-label">Total Trades</span>
            <span className="stat-value">{totalTrades}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Avg Win Rate</span>
            <span className="stat-value">{avgWinRate}%</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="terminal-tabs">
        <button
          className={`tab ${activeTab === 'terminal' ? 'active' : ''}`}
          onClick={() => setActiveTab('terminal')}
        >
          📊 Terminal
        </button>
        <button
          className={`tab ${activeTab === 'bots' ? 'active' : ''}`}
          onClick={() => setActiveTab('bots')}
        >
          🤖 Bots ({bots.length})
        </button>
        <button
          className={`tab ${activeTab === 'signals' ? 'active' : ''}`}
          onClick={() => setActiveTab('signals')}
        >
          ⚡ Signals ({signals.length})
        </button>
        <button
          className={`tab ${activeTab === 'trades' ? 'active' : ''}`}
          onClick={() => setActiveTab('trades')}
        >
          📈 Trades ({trades.length})
        </button>
        <button
          className={`tab ${activeTab === 'settings' ? 'active' : ''}`}
          onClick={() => setActiveTab('settings')}
        >
          ⚙️ Settings
        </button>
      </div>

      <div className="terminal-container">
        {/* TERMINAL TAB */}
        {activeTab === 'terminal' && (
          <div className="terminal-content">
            <div className="terminal-grid">
              {/* Active Bots Panel */}
              <div className="panel">
                <h3>🤖 Active Bots</h3>
                <div className="bots-list">
                  {bots.map((bot) => (
                    <div
                      key={bot.id}
                      className={`bot-item ${bot.status} ${selectedBot?.id === bot.id ? 'selected' : ''}`}
                      onClick={() => setSelectedBot(bot)}
                    >
                      <div className="bot-header">
                        <div className="bot-name">{bot.name}</div>
                        <div className={`status-badge ${bot.status}`}>
                          {bot.status === 'running' ? '▶' : bot.status === 'paused' ? '⏸' : '⏹'} {bot.status}
                        </div>
                      </div>
                      <div className="bot-pair">{bot.pair}</div>
                      <div className="bot-metrics">
                        <span className={`profit ${bot.profit >= 0 ? 'positive' : 'negative'}`}>
                          ${bot.profit.toFixed(2)}
                        </span>
                        <span className="win-rate">{bot.winRate}% WR</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Live Chart Placeholder */}
              <div className="panel chart-panel">
                <h3>📈 Live Chart</h3>
                <div className="chart-area">
                  <div className="chart-placeholder">
                    <svg viewBox="0 0 500 200" className="chart-svg">
                      <polyline
                        points="0,100 50,85 100,95 150,70 200,80 250,60 300,75 350,65 400,70 450,50 500,60"
                        fill="none"
                        stroke="#78e6c8"
                        strokeWidth="2"
                      />
                      <polyline
                        points="0,120 50,110 100,115 150,100 200,105 250,95 300,110 350,100 400,105 450,85 500,95"
                        fill="none"
                        stroke="rgba(120, 230, 200, 0.3)"
                        strokeWidth="1"
                        strokeDasharray="5,5"
                      />
                    </svg>
                  </div>
                  <div className="chart-info">
                    <div className="info-row">
                      <span>Pair:</span>
                      <strong>{selectedBot?.pair}</strong>
                    </div>
                    <div className="info-row">
                      <span>Strategy:</span>
                      <strong>{selectedBot?.strategy}</strong>
                    </div>
                    <div className="info-row">
                      <span>Last Trade:</span>
                      <strong>{selectedBot?.lastTrade}</strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* Live Signals Feed */}
              <div className="panel signals-panel">
                <h3>⚡ Live Signals</h3>
                <div className="signals-feed">
                  {signals.slice(0, 4).map((signal) => (
                    <div key={signal.id} className={`signal-item ${signal.action}`}>
                      <div className="signal-icon">
                        {signal.action === 'buy' ? '🟢' : '🔴'}
                      </div>
                      <div className="signal-info">
                        <div className="signal-coin">{signal.coin}</div>
                        <div className="signal-source">{signal.source}</div>
                      </div>
                      <div className="signal-strength">
                        <div className="strength-bar">
                          <div className="strength-fill" style={{ width: `${signal.strength * 100}%` }}></div>
                        </div>
                        <span>{(signal.strength * 100).toFixed(0)}%</span>
                      </div>
                      <div className="signal-price">${signal.price.toFixed(2)}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Bot Controls */}
            {selectedBot && (
              <div className="bot-controls">
                <h3>🎮 Bot Controls - {selectedBot.name}</h3>
                <div className="controls-grid">
                  <div className="control-section">
                    <label>Trading Mode</label>
                    <select
                      value={botControls.mode}
                      onChange={(e) =>
                        setBotControls({ ...botControls, mode: e.target.value })
                      }
                      className="control-input"
                    >
                      <option value="manual">Manual</option>
                      <option value="semi-auto">Semi-Auto</option>
                      <option value="fully-auto">Fully Automated</option>
                    </select>
                  </div>

                  <div className="control-section">
                    <label>Risk Level</label>
                    <select
                      value={botControls.riskLevel}
                      onChange={(e) =>
                        setBotControls({ ...botControls, riskLevel: e.target.value })
                      }
                      className="control-input"
                    >
                      <option value="low">Low (1%)</option>
                      <option value="medium">Medium (2%)</option>
                      <option value="high">High (5%)</option>
                    </select>
                  </div>

                  <div className="control-section">
                    <label>Max Drawdown (%)</label>
                    <input
                      type="number"
                      value={botControls.maxDrawdown}
                      onChange={(e) =>
                        setBotControls({
                          ...botControls,
                          maxDrawdown: parseFloat(e.target.value),
                        })
                      }
                      className="control-input"
                      min="1"
                      max="50"
                    />
                  </div>

                  <div className="control-section">
                    <label>Profit Target (%)</label>
                    <input
                      type="number"
                      value={botControls.profitTarget}
                      onChange={(e) =>
                        setBotControls({
                          ...botControls,
                          profitTarget: parseFloat(e.target.value),
                        })
                      }
                      className="control-input"
                      min="1"
                      max="50"
                    />
                  </div>

                  <div className="control-section">
                    <label>Trade Amount ($)</label>
                    <input
                      type="number"
                      value={botControls.tradeAmount}
                      onChange={(e) =>
                        setBotControls({
                          ...botControls,
                          tradeAmount: parseFloat(e.target.value),
                        })
                      }
                      className="control-input"
                      min="10"
                      step="10"
                    />
                  </div>
                </div>

                <div className="bot-actions">
                  <button
                    className={`btn-action ${selectedBot.status === 'running' ? 'active' : ''}`}
                    onClick={() => handleBotAction(selectedBot.id, 'start')}
                  >
                    ▶ Start
                  </button>
                  <button
                    className={`btn-action pause ${selectedBot.status === 'paused' ? 'active' : ''}`}
                    onClick={() => handleBotAction(selectedBot.id, 'pause')}
                  >
                    ⏸ Pause
                  </button>
                  <button
                    className="btn-action stop"
                    onClick={() => handleBotAction(selectedBot.id, 'stop')}
                  >
                    ⏹ Stop
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* BOTS TAB */}
        {activeTab === 'bots' && (
          <div className="bots-tab">
            <div className="tab-header">
              <h2>Trading Bots Management</h2>
              <button className="btn-primary">+ Create New Bot</button>
            </div>

            <div className="bots-grid">
              {bots.map((bot) => (
                <div key={bot.id} className={`bot-card ${bot.status}`}>
                  <div className="card-header">
                    <h3>{bot.name}</h3>
                    <span className={`status-badge ${bot.status}`}>
                      {bot.status}
                    </span>
                  </div>

                  <div className="card-info">
                    <p><strong>Strategy:</strong> {bot.strategy}</p>
                    <p><strong>Trading Pair:</strong> {bot.pair}</p>
                  </div>

                  <div className="card-metrics">
                    <div className="metric">
                      <span className="label">Profit</span>
                      <span className={`value ${bot.profit >= 0 ? 'positive' : 'negative'}`}>
                        ${bot.profit.toFixed(2)}
                      </span>
                    </div>
                    <div className="metric">
                      <span className="label">Trades</span>
                      <span className="value">{bot.trades}</span>
                    </div>
                    <div className="metric">
                      <span className="label">Win Rate</span>
                      <span className="value">{bot.winRate}%</span>
                    </div>
                  </div>

                  <div className="card-actions">
                    <button className="btn-small">Edit</button>
                    <button className="btn-small">Logs</button>
                    <button className="btn-small delete">Delete</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SIGNALS TAB */}
        {activeTab === 'signals' && (
          <div className="signals-tab">
            <h2>Trading Signals</h2>

            <div className="signals-list">
              {signals.map((signal) => (
                <div key={signal.id} className={`signal-card ${signal.action}`}>
                  <div className="signal-left">
                    <div className="signal-icon-large">
                      {signal.action === 'buy' ? '🟢 BUY' : '🔴 SELL'}
                    </div>
                  </div>

                  <div className="signal-middle">
                    <h4>{signal.coin}</h4>
                    <p>Price: ${signal.price.toFixed(2)}</p>
                    <p>Source: {signal.source}</p>
                  </div>

                  <div className="signal-strength-large">
                    <div className="strength-label">Signal Strength</div>
                    <div className="strength-bar-large">
                      <div className="strength-fill-large" style={{ width: `${signal.strength * 100}%` }}></div>
                    </div>
                    <div className="strength-percent">{(signal.strength * 100).toFixed(0)}%</div>
                  </div>

                  <div className="signal-actions">
                    <span className="timestamp">{signal.timestamp}</span>
                    <button className="btn-signal">Accept</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TRADES TAB */}
        {activeTab === 'trades' && (
          <div className="trades-tab">
            <h2>Trade History</h2>

            <div className="trades-table">
              <table>
                <thead>
                  <tr>
                    <th>Pair</th>
                    <th>Action</th>
                    <th>Price</th>
                    <th>Amount</th>
                    <th>Total</th>
                    <th>Profit/Loss</th>
                    <th>Status</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade) => (
                    <tr key={trade.id}>
                      <td><strong>{trade.pair}</strong></td>
                      <td>
                        <span className={`action ${trade.action}`}>
                          {trade.action === 'buy' ? '🟢 BUY' : '🔴 SELL'}
                        </span>
                      </td>
                      <td>${trade.price.toFixed(2)}</td>
                      <td>{trade.amount}</td>
                      <td>${trade.total.toFixed(2)}</td>
                      <td>
                        <span className={`profit ${trade.profit >= 0 ? 'positive' : 'negative'}`}>
                          ${trade.profit.toFixed(2)}
                        </span>
                      </td>
                      <td>
                        <span className={`status ${trade.status}`}>
                          {trade.status === 'completed' ? '✓' : trade.status === 'pending' ? '⏳' : '✗'} {trade.status}
                        </span>
                      </td>
                      <td className="time">{trade.timestamp}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* SETTINGS TAB */}
        {activeTab === 'settings' && (
          <div className="settings-tab">
            <h2>Terminal Settings</h2>

            <div className="settings-grid">
              <div className="settings-section">
                <h3>Exchange Connection</h3>
                <div className="setting-item">
                  <label>Exchange</label>
                  <select className="setting-input">
                    <option>Binance</option>
                    <option>Coinbase</option>
                    <option>Kraken</option>
                    <option>Bybit</option>
                  </select>
                </div>
                <div className="setting-item">
                  <label>API Key</label>
                  <input type="password" className="setting-input" placeholder="Enter API Key" />
                </div>
                <div className="setting-item">
                  <label>API Secret</label>
                  <input type="password" className="setting-input" placeholder="Enter API Secret" />
                </div>
                <button className="btn-secondary">Test Connection</button>
              </div>

              <div className="settings-section">
                <h3>Notification Settings</h3>
                <div className="setting-item">
                  <label>
                    <input type="checkbox" defaultChecked />
                    Email notifications
                  </label>
                </div>
                <div className="setting-item">
                  <label>
                    <input type="checkbox" defaultChecked />
                    SMS alerts
                  </label>
                </div>
                <div className="setting-item">
                  <label>
                    <input type="checkbox" defaultChecked />
                    Push notifications
                  </label>
                </div>
              </div>

              <div className="settings-section">
                <h3>Risk Management</h3>
                <div className="setting-item">
                  <label>Daily Loss Limit ($)</label>
                  <input type="number" className="setting-input" defaultValue="500" />
                </div>
                <div className="setting-item">
                  <label>Max Open Positions</label>
                  <input type="number" className="setting-input" defaultValue="5" />
                </div>
              </div>
            </div>

            <button className="btn-primary">Save Settings</button>
          </div>
        )}
      </div>
    </section>
  );
};

export default ProTradingTerminal;
