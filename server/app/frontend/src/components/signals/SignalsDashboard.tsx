import React, { useState } from 'react';
import { Card, MetricBox, Badge } from '../shared';
import './SignalsDashboard.css';

const SignalsDashboard: React.FC = () => {
  const [signals] = useState([
    { symbol: 'AAPL', type: 'BUY', confidence: 87, reason: 'Bullish crossover detected', timestamp: '2 minutes ago' },
    { symbol: 'NVDA', type: 'STRONG_BUY', confidence: 94, reason: 'Breakout above resistance', timestamp: '5 minutes ago' },
    { symbol: 'TSLA', type: 'SELL', confidence: 76, reason: 'Bearish divergence', timestamp: '8 minutes ago' },
    { symbol: 'GOOGL', type: 'HOLD', confidence: 65, reason: 'Consolidation pattern', timestamp: '12 minutes ago' },
    { symbol: 'MSFT', type: 'BUY', confidence: 81, reason: 'Support bounce confirmed', timestamp: '15 minutes ago' },
  ]);

  const signalStats = {
    activeSignals: signals.length,
    buySignals: signals.filter(s => s.type.includes('BUY')).length,
    sellSignals: signals.filter(s => s.type.includes('SELL')).length,
    avgConfidence: (signals.reduce((sum, s) => sum + s.confidence, 0) / signals.length).toFixed(1),
  };

  return (
    <div className="dashboard signals-dashboard">
      <h1>AI Trading Signals</h1>

      <div className="signal-metrics">
        <MetricBox label="Active Signals" value={signalStats.activeSignals} />
        <MetricBox label="Buy Signals" value={signalStats.buySignals} tone="success" />
        <MetricBox label="Sell Signals" value={signalStats.sellSignals} />
        <MetricBox label="Avg Confidence" value={`${signalStats.avgConfidence}%`} />
      </div>

      <Card title="Recent Signals" subtitle="Latest AI-generated trading signals">
        <div className="signals-list">
          {signals.map((signal, idx) => (
            <div key={idx} className="signal-item">
              <div className="signal-symbol">{signal.symbol}</div>
              <div className="signal-details">
                <p className="signal-reason">{signal.reason}</p>
                <p className="signal-time">{signal.timestamp}</p>
              </div>
              <div className="signal-info">
                <Badge type={signal.type.toLowerCase()}>{signal.type.replace('_', ' ')}</Badge>
                <span className="signal-confidence" title="Confidence Score">{signal.confidence}%</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Signal Statistics" subtitle="Performance metrics">
        <div className="signal-stats-grid">
          <div className="stat-box">
            <span className="stat-label">Win Rate</span>
            <span className="stat-value">72.5%</span>
            <span className="stat-meta">Last 30 signals</span>
          </div>
          <div className="stat-box">
            <span className="stat-label">Avg Return</span>
            <span className="stat-value">2.34%</span>
            <span className="stat-meta">Per executed signal</span>
          </div>
          <div className="stat-box">
            <span className="stat-label">False Positives</span>
            <span className="stat-value">27.5%</span>
            <span className="stat-meta">Of all signals</span>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default SignalsDashboard;
