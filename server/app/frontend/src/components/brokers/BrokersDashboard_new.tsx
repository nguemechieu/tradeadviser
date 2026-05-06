import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './BrokersDashboard.css';

const BrokersDashboard: React.FC = () => {
  const [brokers] = useState([
    { name: 'Interactive Brokers', status: 'connected', balance: 156300, available: 142800, usedMargin: 13500, apiHealth: 'Good' },
    { name: 'TD Ameritrade', status: 'connected', balance: 89500, available: 82100, usedMargin: 7400, apiHealth: 'Good' },
    { name: 'Coinbase', status: 'connected', balance: 45200, available: 45200, usedMargin: 0, apiHealth: 'Good' },
    { name: 'Kraken', status: 'connected', balance: 23400, available: 21800, usedMargin: 1600, apiHealth: 'Degraded' },
  ]);

  const totalBalance = brokers.reduce((sum: number, b: any) => sum + b.balance, 0);
  const connectedBrokers = brokers.filter((b: any) => b.status === 'connected').length;

  return (
    <div className="dashboard brokers-dashboard">
      <h1>Brokers & Exchanges</h1>

      <div className="broker-metrics">
        <MetricBox label="Connected Brokers" value={connectedBrokers} tone="success" />
        <MetricBox label="Total Balance" value={`$${totalBalance.toLocaleString()}`} />
        <MetricBox label="Available Capital" value={`$${(totalBalance * 0.95).toLocaleString()}`} />
        <MetricBox label="Margin Used" value={`${((totalBalance * 0.05) / totalBalance * 100).toFixed(1)}%`} />
      </div>

      <Card title="Broker Connections" subtitle="Status and balance of all connected brokers">
        <div className="brokers-table">
          <table>
            <thead>
              <tr>
                <th>Broker</th>
                <th>Status</th>
                <th>Balance</th>
                <th>Available</th>
                <th>Used Margin</th>
                <th>API Health</th>
              </tr>
            </thead>
            <tbody>
              {brokers.map((broker: any) => (
                <tr key={broker.name} className={`status-${broker.status}`}>
                  <td className="broker-name">{broker.name}</td>
                  <td><span className={`status-badge ${broker.status}`}>{broker.status}</span></td>
                  <td>${broker.balance.toLocaleString()}</td>
                  <td className="positive">${broker.available.toLocaleString()}</td>
                  <td className="negative">${broker.usedMargin.toLocaleString()}</td>
                  <td><span className={`health-badge ${broker.apiHealth.toLowerCase().replace(' ', '-')}`}>{broker.apiHealth}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default BrokersDashboard;
