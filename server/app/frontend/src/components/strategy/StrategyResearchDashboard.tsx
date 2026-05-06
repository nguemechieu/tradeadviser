import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './StrategyDashboard.css';

const StrategyResearchDashboard: React.FC = () => {
  const [research] = useState({
    backtests: [
      { name: 'Mean Reversion 50/200', sharpe: 1.92, returns: 28.5, maxDD: -12.3, trades: 247 },
      { name: 'Momentum + Filter', sharpe: 1.76, returns: 22.1, maxDD: -8.9, trades: 156 },
      { name: 'ML Ensemble v2', sharpe: 1.68, returns: 19.8, maxDD: -10.5, trades: 312 },
    ],
    topMetrics: {
      totalBacktests: 42,
      avgSharpe: 1.72,
      bestReturn: 45.3,
      winRate: 68.5,
    },
  });

  return (
    <div className="dashboard strategy-research-dashboard">
      <h1>Strategy Research</h1>

      <div className="research-metrics">
        <MetricBox label="Total Backtests" value={research.topMetrics.totalBacktests} />
        <MetricBox label="Avg Sharpe" value={research.topMetrics.avgSharpe.toFixed(2)} tone="success" />
        <MetricBox label="Best Return" value={`${research.topMetrics.bestReturn}%`} tone="success" />
        <MetricBox label="Win Rate" value={`${research.topMetrics.winRate}%`} />
      </div>

      <Card title="Recent Backtests" subtitle="Latest strategy analysis results">
        <div className="backtest-table">
          <table>
            <thead>
              <tr>
                <th>Strategy Name</th>
                <th>Sharpe Ratio</th>
                <th>Total Return</th>
                <th>Max Drawdown</th>
                <th>Trades</th>
              </tr>
            </thead>
            <tbody>
              {research.backtests.map((test) => (
                <tr key={test.name}>
                  <td className="strategy-name">{test.name}</td>
                  <td>{test.sharpe.toFixed(2)}</td>
                  <td className="positive">+{test.returns.toFixed(1)}%</td>
                  <td className="negative">{test.maxDD.toFixed(1)}%</td>
                  <td>{test.trades}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default StrategyResearchDashboard;
