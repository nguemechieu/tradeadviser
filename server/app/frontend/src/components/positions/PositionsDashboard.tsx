import React from 'react';
import { Card } from '../shared';

const PositionsDashboard: React.FC = () => {
  return (
    <div className="dashboard positions-dashboard">
      <h1>Open Positions</h1>
      <Card title="Current Positions" subtitle="Active trades and holdings">
        <p>Open positions monitoring coming soon...</p>
      </Card>
    </div>
  );
};

export default PositionsDashboard;
