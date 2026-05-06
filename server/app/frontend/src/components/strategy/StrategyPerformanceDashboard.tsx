import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './StrategyDashboard.css';

const StrategyPerformanceDashboard: React.FC = () => {
  const [performance] = useState([
    { strategy: 'Mean Reversion', ytd: 28.5, mtd: 5.2, wtd: 1.3, winRate: 72, sharpe: 1.92, roi: 2.85 },
    { strategy: 'Momentum Factor', ytd: 22.1, mtd: 3.8, wtd: 0.9, winRate: 68, sharpe: 1.76, roi: 2.21 },
    { strategy: 'ML Classifier', ytd: 19.8, mtd: 2.4, wtd: 0.6, winRate: 65, sharpe: 1.68, roi: 1.98 },
    { strategy: 'Pairs Trading', ytd: 12.3, mtd: 1.9, wtd: 0.4, winRate: 62, sharpe: 1.45, roi: 1.23 },
  ]);

  const avgReturn = (performance.reduce((sum, p) => sum + p.ytd, 0) / performance.length).toFixed(2);

  return (
    <div className="dashboard strategy-performance-dashboard">
      <h1>Strategy Performance</h1>

      <div className="performance-metrics">
        <MetricBox label="Portfolio YTD" value={`${avgReturn}%`} tone="success" />
        <MetricBox label="Avg Sharpe" value="1.70" />
        <MetricBox label="Best Performer" value="Mean Reversion" />
        <MetricBox label="Avg Win Rate" value="66.75%" />
      </div>

      <Card title="Performance Comparison" subtitle="Metrics across all active strategies">
        <div className="performance-table">
          <table>
            <thead>
              <tr>
                <th>Strategy</th>
                <th>YTD Return</th>
                <th>MTD</th>
                <th>WTD</th>
                <th>Win Rate</th>
                <th>Sharpe</th>
                <th>ROI %</th>
              </tr>
            </thead>
            <tbody>
              {performance.map((perf) => (
                <tr key={perf.strategy}>
                  <td className="strategy-name">{perf.strategy}</td>
                  <td className="positive">+{perf.ytd.toFixed(1)}%</td>
                  <td className="positive">+{perf.mtd.toFixed(1)}%</td>
                  <td className="positive">+{perf.wtd.toFixed(1)}%</td>
                  <td>{perf.winRate}%</td>
                  <td>{perf.sharpe.toFixed(2)}</td>
                  <td>{perf.roi.toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default StrategyPerformanceDashboard;
