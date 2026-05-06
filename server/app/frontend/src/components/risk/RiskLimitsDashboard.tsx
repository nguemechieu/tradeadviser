import React, { useState } from 'react';
import { Card, MetricBox, Alert } from '../shared';
import './RiskDashboard.css';

const RiskLimitsDashboard: React.FC = () => {
  const [limits] = useState([
    { name: 'Daily Loss Limit', limit: 5000, current: 2340, used: 46.8, status: 'normal' },
    { name: 'Position Size', limit: 100000, current: 78600, used: 78.6, status: 'normal' },
    { name: 'Leverage', limit: 3.0, current: 2.15, used: 71.7, status: 'normal' },
    { name: 'Volatility Threshold', limit: 35, current: 28, used: 80, status: 'warning' },
  ]);

  const warningLimit = limits.filter(l => l.status === 'warning').length;

  return (
    <div className="dashboard risk-limits-dashboard">
      <h1>Risk Limits</h1>

      {warningLimit > 0 && (
        <Alert type="warning" title={`${warningLimit} Limit(s) at Risk`} message="Some risk limits are approaching thresholds." dismissible={false} />
      )}

      <div className="limits-metrics">
        <MetricBox label="Active Limits" value={limits.length} />
        <MetricBox label="Within Safe Range" value={limits.filter(l => l.used < 75).length} tone="success" />
        <MetricBox label="Approaching Limit" value={warningLimit} />
        <MetricBox label="Portfolio Health" value="Good" />
      </div>

      <Card title="Risk Limit Configuration" subtitle="Current risk limits and usage">
        <div className="limits-list">
          {limits.map((limit) => (
            <div key={limit.name} className={`limit-item ${limit.status}`}>
              <div className="limit-name">{limit.name}</div>
              <div className="limit-bar-container">
                <div className="limit-bar">
                  <div className="limit-fill" style={{ width: `${limit.used}%` }}></div>
                </div>
              </div>
              <div className="limit-info">
                <span className="limit-current">{limit.current}</span>
                <span className="limit-divider">/</span>
                <span className="limit-max">{limit.limit}</span>
                <span className="limit-percent">{limit.used.toFixed(1)}%</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

export default RiskLimitsDashboard;
