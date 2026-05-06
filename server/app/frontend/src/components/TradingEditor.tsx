import React, { useState } from 'react';
import './TradingEditor.css';

interface Strategy {
  id: string;
  name: string;
  type: string;
  entryCondition: string;
  exitCondition: string;
  stopLoss: string;
  takeProfit: string;
  risk: number;
  winRate: number;
  created: string;
}

const TradingEditor: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'create' | 'strategies' | 'backtest'>('create');
  const [strategies, setStrategies] = useState<Strategy[]>([
    {
      id: '1',
      name: 'Golden Crossover',
      type: 'Moving Average',
      entryCondition: 'MA(50) > MA(200)',
      exitCondition: 'RSI > 70',
      stopLoss: '2%',
      takeProfit: '5%',
      risk: 1.5,
      winRate: 67,
      created: '2 days ago',
    },
    {
      id: '2',
      name: 'Breakout Strategy',
      type: 'Support/Resistance',
      entryCondition: 'Price > Resistance',
      exitCondition: 'Price < Support',
      stopLoss: '3%',
      takeProfit: '8%',
      risk: 2.5,
      winRate: 62,
      created: '5 days ago',
    },
  ]);

  const [formData, setFormData] = useState({
    name: '',
    type: 'moving-average',
    entryCondition: '',
    exitCondition: '',
    stopLoss: '',
    takeProfit: '',
  });

  const [selectedStrategy, setSelectedStrategy] = useState<Strategy | null>(null);

  const handleFormChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleCreateStrategy = () => {
    if (formData.name && formData.entryCondition && formData.exitCondition) {
      const newStrategy: Strategy = {
        id: Date.now().toString(),
        name: formData.name,
        type: formData.type,
        entryCondition: formData.entryCondition,
        exitCondition: formData.exitCondition,
        stopLoss: formData.stopLoss || 'N/A',
        takeProfit: formData.takeProfit || 'N/A',
        risk: Math.random() * 3 + 1,
        winRate: Math.random() * 30 + 55,
        created: 'just now',
      };
      setStrategies([newStrategy, ...strategies]);
      setFormData({
        name: '',
        type: 'moving-average',
        entryCondition: '',
        exitCondition: '',
        stopLoss: '',
        takeProfit: '',
      });
      alert('Strategy created successfully!');
    }
  };

  const handleDeleteStrategy = (id: string) => {
    setStrategies(strategies.filter(s => s.id !== id));
  };

  return (
    <section className="trading-editor">
      {/* Header */}
      <div className="editor-header">
        <div className="header-content">
          <h1>Trading Strategy Editor</h1>
          <p>Create, manage, and backtest your trading strategies</p>
        </div>
        <div className="header-actions">
          <button className="btn-icon">📥 Import</button>
          <button className="btn-icon">📤 Export</button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="editor-tabs">
        <button
          className={`tab ${activeTab === 'create' ? 'active' : ''}`}
          onClick={() => setActiveTab('create')}
        >
          ✏️ Create Strategy
        </button>
        <button
          className={`tab ${activeTab === 'strategies' ? 'active' : ''}`}
          onClick={() => setActiveTab('strategies')}
        >
          📋 My Strategies ({strategies.length})
        </button>
        <button
          className={`tab ${activeTab === 'backtest' ? 'active' : ''}`}
          onClick={() => setActiveTab('backtest')}
        >
          📊 Backtest
        </button>
      </div>

      <div className="editor-container">
        {/* CREATE STRATEGY TAB */}
        {activeTab === 'create' && (
          <div className="editor-content">
            <div className="form-section">
              <h2>Strategy Configuration</h2>

              <div className="form-group">
                <label>Strategy Name *</label>
                <input
                  type="text"
                  name="name"
                  value={formData.name}
                  onChange={handleFormChange}
                  placeholder="Enter strategy name (e.g., Golden Crossover)"
                  className="form-input"
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Strategy Type *</label>
                  <select
                    name="type"
                    value={formData.type}
                    onChange={handleFormChange}
                    className="form-input"
                  >
                    <option value="moving-average">Moving Average</option>
                    <option value="rsi">RSI</option>
                    <option value="macd">MACD</option>
                    <option value="bollinger">Bollinger Bands</option>
                    <option value="support-resistance">Support/Resistance</option>
                    <option value="trend-following">Trend Following</option>
                    <option value="mean-reversion">Mean Reversion</option>
                    <option value="breakout">Breakout</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>Risk Per Trade (%)</label>
                  <input
                    type="number"
                    placeholder="e.g., 1-2"
                    min="0.1"
                    max="5"
                    step="0.1"
                    className="form-input"
                  />
                </div>
              </div>

              <div className="form-section-divider"></div>

              <div className="form-group">
                <label>Entry Condition *</label>
                <textarea
                  name="entryCondition"
                  value={formData.entryCondition}
                  onChange={handleFormChange}
                  placeholder="Define your entry signal(e.g., MA(50) > MA(200) AND RSI < 50)"
                  className="form-textarea"
                  rows={4}
                />
                <p className="form-hint">Use technical indicators: MA, RSI, MACD, BB, ATR, etc.</p>
              </div>

              <div className="form-group">
                <label>Exit Condition *</label>
                <textarea
                  name="exitCondition"
                  value={formData.exitCondition}
                  onChange={handleFormChange}
                  placeholder="Define your exit signal (e.g., RSI > 70 OR Time > 4H)"
                  className="form-textarea"
                  rows={4}
                />
                <p className="form-hint">Can combine multiple conditions with AND/OR operators</p>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Stop Loss (%)</label>
                  <input
                    type="number"
                    name="stopLoss"
                    value={formData.stopLoss}
                    onChange={handleFormChange}
                    placeholder="e.g., 2"
                    min="0.1"
                    max="10"
                    step="0.1"
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label>Take Profit (%)</label>
                  <input
                    type="number"
                    name="takeProfit"
                    value={formData.takeProfit}
                    onChange={handleFormChange}
                    placeholder="e.g., 5"
                    min="0.1"
                    max="20"
                    step="0.1"
                    className="form-input"
                  />
                </div>
              </div>

              <div className="form-actions">
                <button className="btn-secondary" onClick={() => setFormData({
                  name: '',
                  type: 'moving-average',
                  entryCondition: '',
                  exitCondition: '',
                  stopLoss: '',
                  takeProfit: '',
                })}>Reset</button>
                <button className="btn-primary" onClick={handleCreateStrategy}>Create Strategy</button>
              </div>
            </div>

            <div className="help-section">
              <h3>Quick Help</h3>
              <div className="help-content">
                <div className="help-item">
                  <h4>Common Indicators</h4>
                  <ul>
                    <li><strong>MA</strong> - Moving Average</li>
                    <li><strong>RSI</strong> - Relative Strength Index</li>
                    <li><strong>MACD</strong> - Moving Avg Convergence</li>
                    <li><strong>BB</strong> - Bollinger Bands</li>
                    <li><strong>ATR</strong> - Average True Range</li>
                  </ul>
                </div>

                <div className="help-item">
                  <h4>Example Entry</h4>
                  <code>MA(50) > MA(200) AND RSI < 50</code>
                </div>

                <div className="help-item">
                  <h4>Example Exit</h4>
                  <code>RSI > 70 OR Time > 4H</code>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STRATEGIES TAB */}
        {activeTab === 'strategies' && (
          <div className="strategies-list">
            <div className="list-header">
              <h2>Your Strategies</h2>
              <span className="count">{strategies.length} strategies</span>
            </div>

            {strategies.length === 0 ? (
              <div className="empty-state">
                <p>No strategies created yet. Create your first strategy to get started!</p>
              </div>
            ) : (
              <div className="strategies-grid">
                {strategies.map((strategy) => (
                  <div
                    key={strategy.id}
                    className="strategy-card"
                    onClick={() => setSelectedStrategy(strategy)}
                  >
                    <div className="strategy-header">
                      <h3>{strategy.name}</h3>
                      <span className="strategy-type">{strategy.type}</span>
                    </div>

                    <div className="strategy-metrics">
                      <div className="metric">
                        <span className="metric-label">Win Rate</span>
                        <span className="metric-value">{strategy.winRate.toFixed(1)}%</span>
                        <div className="metric-bar">
                          <div className="metric-fill" style={{ width: `${strategy.winRate}%` }}></div>
                        </div>
                      </div>
                      <div className="metric">
                        <span className="metric-label">Risk/Trade</span>
                        <span className="metric-value">{strategy.risk.toFixed(2)}%</span>
                      </div>
                    </div>

                    <div className="strategy-conditions">
                      <div className="condition">
                        <span className="label">Entry:</span>
                        <span className="value">{strategy.entryCondition}</span>
                      </div>
                      <div className="condition">
                        <span className="label">Exit:</span>
                        <span className="value">{strategy.exitCondition}</span>
                      </div>
                      <div className="condition-row">
                        <span>SL: {strategy.stopLoss}</span>
                        <span>TP: {strategy.takeProfit}</span>
                      </div>
                    </div>

                    <p className="strategy-created">Created {strategy.created}</p>

                    <div className="strategy-actions">
                      <button className="btn-small">Edit</button>
                      <button className="btn-small">Backtest</button>
                      <button
                        className="btn-small btn-danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteStrategy(strategy.id);
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {selectedStrategy && (
              <div className="strategy-detail">
                <div className="detail-header">
                  <h3>{selectedStrategy.name}</h3>
                  <button className="btn-close" onClick={() => setSelectedStrategy(null)}>✕</button>
                </div>
                <div className="detail-content">
                  <p><strong>Type:</strong> {selectedStrategy.type}</p>
                  <p><strong>Entry:</strong> {selectedStrategy.entryCondition}</p>
                  <p><strong>Exit:</strong> {selectedStrategy.exitCondition}</p>
                  <p><strong>Stop Loss:</strong> {selectedStrategy.stopLoss}</p>
                  <p><strong>Take Profit:</strong> {selectedStrategy.takeProfit}</p>
                  <p><strong>Win Rate:</strong> {selectedStrategy.winRate.toFixed(1)}%</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* BACKTEST TAB */}
        {activeTab === 'backtest' && (
          <div className="backtest-section">
            <div className="backtest-config">
              <h2>Backtest Configuration</h2>

              <div className="form-row">
                <div className="form-group">
                  <label>Select Strategy</label>
                  <select className="form-input">
                    <option value="">Choose a strategy...</option>
                    {strategies.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label>Asset</label>
                  <select className="form-input">
                    <option>AAPL</option>
                    <option>GOOGL</option>
                    <option>MSFT</option>
                    <option>BTCUSD</option>
                    <option>EURUSD</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Start Date</label>
                  <input type="date" className="form-input" />
                </div>

                <div className="form-group">
                  <label>End Date</label>
                  <input type="date" className="form-input" />
                </div>

                <div className="form-group">
                  <label>Initial Capital ($)</label>
                  <input
                    type="number"
                    placeholder="10000"
                    min="1000"
                    step="1000"
                    className="form-input"
                  />
                </div>
              </div>

              <button className="btn-primary">Run Backtest</button>
            </div>

            <div className="backtest-results">
              <h3>Results</h3>
              <div className="results-grid">
                <div className="result-card">
                  <span className="result-label">Total Trades</span>
                  <span className="result-value">45</span>
                </div>
                <div className="result-card">
                  <span className="result-label">Winning Trades</span>
                  <span className="result-value win">30 (66.7%)</span>
                </div>
                <div className="result-card">
                  <span className="result-label">Losing Trades</span>
                  <span className="result-value loss">15 (33.3%)</span>
                </div>
                <div className="result-card">
                  <span className="result-label">Total Profit</span>
                  <span className="result-value win">+$3,450.00</span>
                </div>
                <div className="result-card">
                  <span className="result-label">ROI</span>
                  <span className="result-value win">+34.5%</span>
                </div>
                <div className="result-card">
                  <span className="result-label">Sharpe Ratio</span>
                  <span className="result-value">1.85</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export default TradingEditor;
