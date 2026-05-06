import React from 'react';
import { Card } from '../shared';

const BacktestingDashboard: React.FC = () => {
  return (
    <div className="dashboard backtesting-dashboard">
      <h1>Backtesting</h1>
      <Card title="Strategy Backtesting" subtitle="Historical performance analysis and simulation">
        <p>Backtesting tools coming soon...</p>
      </Card>
    </div>
  );
};

export default BacktestingDashboard;
