import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './AiDashboard.css';

const AiPositionManagerDashboard: React.FC = () => {
  const [recommendations] = useState([
    { position: 'AAPL', current: 'HOLD', suggested: 'INCREASE', reason: 'Reduce portfolio concentration', impact: '+1.2%' },
    { position: 'BTC', current: 'HOLD', suggested: 'HOLD', reason: 'Optimal position size', impact: 'Neutral' },
    { position: 'TSLA', current: 'LONG', suggested: 'TRIM', reason: 'Risk reduction recommended', impact: '-0.8%' },
    { position: 'GLD', current: 'SMALL', suggested: 'INCREASE', reason: 'Hedge portfolio volatility', impact: '+0.5%' },
  ]);

  const stats = {
    totalPositions: 12,
    optimized: 8,
    riskScore: 34,
    efficiency: 87.3,
  };

  return (
    <div className="dashboard ai-position-manager-dashboard">
      <h1>AI Position Manager</h1>

      <div className="pm-stats">
        <MetricBox label="Total Positions" value={stats.totalPositions} />
        <MetricBox label="Optimized" value={stats.optimized} tone="success" />
        <MetricBox label="Risk Score" value={stats.riskScore} />
        <MetricBox label="Efficiency" value={`${stats.efficiency}%`} tone="success" />
      </div>

      <Card title="Position Recommendations" subtitle="AI-suggested position adjustments">
        <div className="recommendations-table">
          <table>
            <thead>
              <tr>
                <th>Position</th>
                <th>Current</th>
                <th>Suggested</th>
                <th>Reason</th>
                <th>Est. Impact</th>
              </tr>
            </thead>
            <tbody>
              {recommendations.map((rec) => (
                <tr key={rec.position}>
                  <td className="position-name">{rec.position}</td>
                  <td>{rec.current}</td>
                  <td className="suggested-action">{rec.suggested}</td>
                  <td className="reason">{rec.reason}</td>
                  <td className={rec.impact.includes('-') ? 'negative' : 'positive'}>{rec.impact}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default AiPositionManagerDashboard;
