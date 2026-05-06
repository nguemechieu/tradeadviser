import React, { useState } from 'react';
import './BrokersDashboard.css';

interface Broker {
  id: string;
  name: string;
  exchange: string;
  status: 'connected' | 'disconnected' | 'error';
  apiKey?: string;
  apiSecret?: string;
  connected: boolean;
  tradingPairs: number;
  lastSync: string;
  balance: number;
  tradingVolume: number;
  fees: number;
  region: string;
}

interface TradingPair {
  id: string;
  brokerId: string;
  symbol: string;
  baseAsset: string;
  quoteAsset: string;
  available: boolean;
  minNotional: number;
  takerFee: number;
  makerFee: number;
  volume24h: number;
}

interface ExchangeStatus {
  id: string;
  name: string;
  status: 'operational' | 'degraded' | 'maintenance';
  uptime: number;
  avgLatency: number;
  supported: number;
  lastChecked: string;
}

const BrokersDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'brokers' | 'exchanges' | 'pairs' | 'api'>('brokers');
  const [selectedBroker, setSelectedBroker] = useState<Broker | null>(null);
  const [showAddBroker, setShowAddBroker] = useState(false);
  const [newApiKey, setNewApiKey] = useState('');
  const [newApiSecret, setNewApiSecret] = useState('');

  const [brokers] = useState<Broker[]>([
    {
      id: '1',
      name: 'Binance',
      exchange: 'Binance',
      status: 'connected',
      connected: true,
      tradingPairs: 1500,
      lastSync: '2 minutes ago',
      balance: 15240.50,
      tradingVolume: 245000.00,
      fees: 12.50,
      region: 'Global',
    },
    {
      id: '2',
      name: 'Coinbase',
      exchange: 'Coinbase',
      status: 'connected',
      connected: true,
      tradingPairs: 320,
      lastSync: '5 minutes ago',
      balance: 8750.25,
      tradingVolume: 125000.00,
      fees: 8.75,
      region: 'US/EU',
    },
    {
      id: '3',
      name: 'Kraken',
      exchange: 'Kraken',
      status: 'connected',
      connected: true,
      tradingPairs: 350,
      lastSync: '1 minute ago',
      balance: 5230.75,
      tradingVolume: 85000.00,
      fees: 5.20,
      region: 'Global',
    },
    {
      id: '4',
      name: 'Bybit',
      exchange: 'Bybit',
      status: 'disconnected',
      connected: false,
      tradingPairs: 800,
      lastSync: '2 hours ago',
      balance: 0,
      tradingVolume: 0,
      fees: 0,
      region: 'Asia',
    },
  ]);

  const [exchanges] = useState<ExchangeStatus[]>([
    {
      id: '1',
      name: 'Binance',
      status: 'operational',
      uptime: 99.98,
      avgLatency: 45,
      supported: 1500,
      lastChecked: '1 minute ago',
    },
    {
      id: '2',
      name: 'Coinbase',
      status: 'operational',
      uptime: 99.95,
      avgLatency: 120,
      supported: 320,
      lastChecked: '2 minutes ago',
    },
    {
      id: '3',
      name: 'Kraken',
      status: 'operational',
      uptime: 99.92,
      avgLatency: 85,
      supported: 350,
      lastChecked: '1 minute ago',
    },
    {
      id: '4',
      name: 'Bybit',
      status: 'degraded',
      uptime: 98.50,
      avgLatency: 200,
      supported: 800,
      lastChecked: '3 minutes ago',
    },
  ]);

  const [tradingPairs] = useState<TradingPair[]>([
    {
      id: '1',
      brokerId: '1',
      symbol: 'BTCUSDT',
      baseAsset: 'BTC',
      quoteAsset: 'USDT',
      available: true,
      minNotional: 10,
      takerFee: 0.1,
      makerFee: 0.1,
      volume24h: 850000,
    },
    {
      id: '2',
      brokerId: '1',
      symbol: 'ETHUSDT',
      baseAsset: 'ETH',
      quoteAsset: 'USDT',
      available: true,
      minNotional: 10,
      takerFee: 0.1,
      makerFee: 0.1,
      volume24h: 450000,
    },
    {
      id: '3',
      brokerId: '2',
      symbol: 'BTCUSD',
      baseAsset: 'BTC',
      quoteAsset: 'USD',
      available: true,
      minNotional: 50,
      takerFee: 0.5,
      makerFee: 0.5,
      volume24h: 320000,
    },
    {
      id: '4',
      brokerId: '2',
      symbol: 'ETHUSD',
      baseAsset: 'ETH',
      quoteAsset: 'USD',
      available: true,
      minNotional: 50,
      takerFee: 0.5,
      makerFee: 0.5,
      volume24h: 180000,
    },
  ]);

  const totalBalance = brokers.reduce((sum, broker) => sum + broker.balance, 0);
  const totalVolume = brokers.reduce((sum, broker) => sum + broker.tradingVolume, 0);
  const totalFees = brokers.reduce((sum, broker) => sum + broker.fees, 0);
  const connectedBrokers = brokers.filter(b => b.connected).length;

  return (
    <section className="brokers-dashboard">
      {/* Header */}
      <div className="brokers-header">
        <div className="header-content">
          <h1>🏦 Brokers & Exchanges</h1>
          <p>Manage multiple broker connections and monitor exchange status</p>
        </div>
        <div className="header-stats">
          <div className="stat">
            <span className="stat-label">Connected</span>
            <span className="stat-value">{connectedBrokers}/{brokers.length}</span>
          </div>
          <div className="stat">
            <span className="stat-label">Total Balance</span>
            <span className="stat-value">${totalBalance.toFixed(2)}</span>
          </div>
          <div className="stat">
            <span className="stat-label">24h Volume</span>
            <span className="stat-value">${(totalVolume / 1000000).toFixed(2)}M</span>
          </div>
          <div className="stat">
            <span className="stat-label">Total Fees</span>
            <span className="stat-value">${totalFees.toFixed(2)}</span>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="brokers-tabs">
        <button
          className={`tab ${activeTab === 'brokers' ? 'active' : ''}`}
          onClick={() => setActiveTab('brokers')}
        >
          🏢 Brokers ({brokers.length})
        </button>
        <button
          className={`tab ${activeTab === 'exchanges' ? 'active' : ''}`}
          onClick={() => setActiveTab('exchanges')}
        >
          📊 Exchanges ({exchanges.length})
        </button>
        <button
          className={`tab ${activeTab === 'pairs' ? 'active' : ''}`}
          onClick={() => setActiveTab('pairs')}
        >
          💱 Trading Pairs ({tradingPairs.length})
        </button>
        <button
          className={`tab ${activeTab === 'api' ? 'active' : ''}`}
          onClick={() => setActiveTab('api')}
        >
          🔑 API Management
        </button>
      </div>

      <div className="brokers-content">
        {/* BROKERS TAB */}
        {activeTab === 'brokers' && (
          <div className="brokers-section">
            <div className="section-header">
              <h2>Connected Brokers</h2>
              <button className="btn-primary" onClick={() => setShowAddBroker(!showAddBroker)}>
                + Add Broker
              </button>
            </div>

            {showAddBroker && (
              <div className="add-broker-panel">
                <h3>Connect New Broker</h3>
                <div className="broker-form">
                  <div className="form-group">
                    <label>Select Exchange</label>
                    <select className="form-input">
                      <option>Binance</option>
                      <option>Coinbase</option>
                      <option>Kraken</option>
                      <option>Bybit</option>
                      <option>OKX</option>
                      <option>Gate.io</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>API Key</label>
                    <input
                      type="password"
                      className="form-input"
                      placeholder="Enter API Key"
                      value={newApiKey}
                      onChange={(e) => setNewApiKey(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>API Secret</label>
                    <input
                      type="password"
                      className="form-input"
                      placeholder="Enter API Secret"
                      value={newApiSecret}
                      onChange={(e) => setNewApiSecret(e.target.value)}
                    />
                  </div>
                  <div className="form-actions">
                    <button className="btn-secondary">Test Connection</button>
                    <button className="btn-primary">Connect Broker</button>
                  </div>
                </div>
              </div>
            )}

            <div className="brokers-grid">
              {brokers.map((broker) => (
                <div
                  key={broker.id}
                  className={`broker-card ${broker.status} ${selectedBroker?.id === broker.id ? 'selected' : ''}`}
                  onClick={() => setSelectedBroker(broker)}
                >
                  <div className="card-header">
                    <h3>{broker.name}</h3>
                    <span className={`status-badge ${broker.status}`}>
                      {broker.status === 'connected' ? '🟢' : broker.status === 'error' ? '🔴' : '⚫'} {broker.status}
                    </span>
                  </div>

                  <div className="card-info">
                    <div className="info-row">
                      <span>Region</span>
                      <strong>{broker.region}</strong>
                    </div>
                    <div className="info-row">
                      <span>Trading Pairs</span>
                      <strong>{broker.tradingPairs}</strong>
                    </div>
                    <div className="info-row">
                      <span>Last Sync</span>
                      <strong>{broker.lastSync}</strong>
                    </div>
                  </div>

                  <div className="card-metrics">
                    <div className="metric">
                      <span className="label">Balance</span>
                      <span className="value">${broker.balance.toFixed(2)}</span>
                    </div>
                    <div className="metric">
                      <span className="label">Volume</span>
                      <span className="value">${(broker.tradingVolume / 1000).toFixed(0)}K</span>
                    </div>
                  </div>

                  <div className="card-actions">
                    <button className="btn-small">Manage</button>
                    <button className="btn-small">Test</button>
                    {!broker.connected && <button className="btn-small delete">Remove</button>}
                  </div>
                </div>
              ))}
            </div>

            {/* Broker Details */}
            {selectedBroker && (
              <div className="broker-details">
                <h3>Broker Details - {selectedBroker.name}</h3>
                <div className="details-grid">
                  <div className="detail-item">
                    <label>Exchange</label>
                    <p>{selectedBroker.exchange}</p>
                  </div>
                  <div className="detail-item">
                    <label>Status</label>
                    <p className={`status-text ${selectedBroker.status}`}>{selectedBroker.status.toUpperCase()}</p>
                  </div>
                  <div className="detail-item">
                    <label>Account Balance</label>
                    <p className="value-large">${selectedBroker.balance.toFixed(2)}</p>
                  </div>
                  <div className="detail-item">
                    <label>24h Trading Volume</label>
                    <p>${selectedBroker.tradingVolume.toFixed(2)}</p>
                  </div>
                  <div className="detail-item">
                    <label>Total Fees (24h)</label>
                    <p>${selectedBroker.fees.toFixed(2)}</p>
                  </div>
                  <div className="detail-item">
                    <label>Available Pairs</label>
                    <p>{selectedBroker.tradingPairs}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* EXCHANGES TAB */}
        {activeTab === 'exchanges' && (
          <div className="exchanges-section">
            <h2>Exchange Status Monitor</h2>
            <div className="exchanges-grid">
              {exchanges.map((exchange) => (
                <div key={exchange.id} className={`exchange-card ${exchange.status}`}>
                  <div className="exchange-header">
                    <h3>{exchange.name}</h3>
                    <span className={`status-badge ${exchange.status}`}>
                      {exchange.status === 'operational' ? '✓ Operational' : exchange.status === 'degraded' ? '⚠ Degraded' : '🔧 Maintenance'}
                    </span>
                  </div>

                  <div className="exchange-metrics">
                    <div className="metric">
                      <span className="label">Uptime</span>
                      <span className="value">{exchange.uptime.toFixed(2)}%</span>
                    </div>
                    <div className="metric">
                      <span className="label">Avg Latency</span>
                      <span className="value">{exchange.avgLatency}ms</span>
                    </div>
                    <div className="metric">
                      <span className="label">Supported Pairs</span>
                      <span className="value">{exchange.supported}</span>
                    </div>
                  </div>

                  <div className="uptime-bar">
                    <div className="uptime-fill" style={{ width: `${exchange.uptime}%` }}></div>
                  </div>

                  <div className="exchange-footer">
                    <span className="last-check">Last checked: {exchange.lastChecked}</span>
                    <button className="btn-link">View Details</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TRADING PAIRS TAB */}
        {activeTab === 'pairs' && (
          <div className="pairs-section">
            <h2>Trading Pairs & Instruments</h2>
            <div className="pairs-table">
              <table>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Base Asset</th>
                    <th>Quote Asset</th>
                    <th>Broker</th>
                    <th>Min Notional</th>
                    <th>Maker Fee</th>
                    <th>Taker Fee</th>
                    <th>24h Volume</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {tradingPairs.map((pair) => {
                    const broker = brokers.find(b => b.id === pair.brokerId);
                    return (
                      <tr key={pair.id}>
                        <td className="symbol-cell">
                          <strong>{pair.symbol}</strong>
                        </td>
                        <td>{pair.baseAsset}</td>
                        <td>{pair.quoteAsset}</td>
                        <td>{broker?.name}</td>
                        <td>${pair.minNotional.toFixed(2)}</td>
                        <td>{pair.makerFee.toFixed(3)}%</td>
                        <td>{pair.takerFee.toFixed(3)}%</td>
                        <td>${(pair.volume24h / 1000).toFixed(0)}K</td>
                        <td>
                          <span className={`pair-status ${pair.available ? 'available' : 'unavailable'}`}>
                            {pair.available ? '✓ Available' : '✗ Unavailable'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* API MANAGEMENT TAB */}
        {activeTab === 'api' && (
          <div className="api-section">
            <h2>API Key Management</h2>
            <div className="api-grid">
              {brokers.filter(b => b.connected).map((broker) => (
                <div key={broker.id} className="api-card">
                  <div className="api-header">
                    <h3>{broker.name} API</h3>
                    <span className="api-status connected">🔐 Active</span>
                  </div>

                  <div className="api-details">
                    <div className="api-key-row">
                      <label>API Key (Hidden)</label>
                      <div className="key-display">
                        ••••••••••••••••••••••••••••••••
                        <button className="btn-icon">👁️</button>
                      </div>
                    </div>

                    <div className="api-key-row">
                      <label>Last Used</label>
                      <p>5 minutes ago</p>
                    </div>

                    <div className="api-key-row">
                      <label>Permissions</label>
                      <div className="permissions">
                        <span className="permission-badge">Read</span>
                        <span className="permission-badge">Trade</span>
                        <span className="permission-badge">Withdraw</span>
                      </div>
                    </div>
                  </div>

                  <div className="api-actions">
                    <button className="btn-secondary">Regenerate Key</button>
                    <button className="btn-danger">Revoke Key</button>
                  </div>
                </div>
              ))}
            </div>

            <div className="api-security">
              <h3>🔒 Security Best Practices</h3>
              <ul>
                <li>Never share your API keys with anyone</li>
                <li>Use API keys with restricted permissions (Read & Trade only)</li>
                <li>Disable withdrawal permissions if not needed</li>
                <li>Rotate your API keys regularly (every 3 months)</li>
                <li>Monitor API usage for suspicious activity</li>
                <li>Use IP whitelisting when available</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export default BrokersDashboard;
