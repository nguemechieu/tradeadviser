import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './StrategyDashboard.css';

const StrategyAssignmentDashboard: React.FC = () => {
  const [assignments] = useState([
    { strategy: 'Mean Reversion', allocation: 35, status: 'Active', capital: 43750 },
    { strategy: 'Momentum Factor', allocation: 30, status: 'Active', capital: 37500 },
    { strategy: 'ML Classifier', allocation: 25, status: 'Active', capital: 31250 },
    { strategy: 'Pairs Trading', allocation: 10, status: 'Testing', capital: 12500 },
  ]);

  const totalCapital = assignments.reduce((sum, a) => sum + a.capital, 0);

  return (
    <div className="dashboard strategy-assignment-dashboard">
      <h1>Strategy Assignment</h1>

      <div className="assignment-metrics">
        <MetricBox label="Active Strategies" value={assignments.filter(a => a.status === 'Active').length} />
        <MetricBox label="Total Allocated" value={`$${totalCapital.toLocaleString()}`} />
        <MetricBox label="Diversification" value="4 Strategies" />
        <MetricBox label="Rebalance Due" value="7 days" />
      </div>

      <Card title="Strategy Allocation" subtitle="Current portfolio strategy distribution">
        <div className="allocation-list">
          {assignments.map((assign) => (
            <div key={assign.strategy} className="allocation-row">
              <div className="allocation-info">
                <p className="allocation-strategy">{assign.strategy}</p>
                <span className={`status-badge ${assign.status.toLowerCase()}`}>{assign.status}</span>
              </div>
              <div className="allocation-bar-container">
                <div className="allocation-bar">
                  <div className="allocation-fill" style={{ width: `${assign.allocation}%` }}></div>
                </div>
                <span className="allocation-percent">{assign.allocation}%</span>
              </div>
              <span className="allocation-capital">${assign.capital.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

export default StrategyAssignmentDashboard;
