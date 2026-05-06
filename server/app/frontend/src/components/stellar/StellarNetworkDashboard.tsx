import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './StellarDashboard.css';

const StellarNetworkDashboard: React.FC = () => {
  const [assets] = useState([
    { code: 'USDC', issuer: 'Centre', balance: 50000, value: 50000, status: 'Active' },
    { code: 'BTC', issuer: 'Stellar Development Fund', balance: 2.5, value: 121250, status: 'Active' },
    { code: 'ETH', issuer: 'Stellar Development Fund', balance: 15.3, value: 41004, status: 'Active' },
    { code: 'EURT', issuer: 'Tempo', balance: 5000, value: 5350, status: 'Active' },
  ]);

  const networkMetrics = {
    totalAssets: 4,
    totalValue: assets.reduce((sum, a) => sum + a.value, 0),
    transactions24h: 234,
    networkHealth: 'Optimal',
  };

  return (
    <div className="dashboard stellar-network-dashboard">
      <h1>Stellar Network</h1>

      <div className="stellar-metrics">
        <MetricBox label="Assets Held" value={networkMetrics.totalAssets} />
        <MetricBox label="Total Value" value={`$${networkMetrics.totalValue.toLocaleString()}`} tone="success" />
        <MetricBox label="Transactions (24h)" value={networkMetrics.transactions24h} />
        <MetricBox label="Network Health" value={networkMetrics.networkHealth} />
      </div>

      <Card title="Stellar Assets" subtitle="Assets and balances on Stellar network">
        <div className="assets-table">
          <table>
            <thead>
              <tr>
                <th>Asset Code</th>
                <th>Issuer</th>
                <th>Balance</th>
                <th>Value</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => (
                <tr key={asset.code}>
                  <td className="asset-code">{asset.code}</td>
                  <td>{asset.issuer}</td>
                  <td>{asset.balance.toLocaleString()}</td>
                  <td className="positive">${asset.value.toLocaleString()}</td>
                  <td><span className="status-active">{asset.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default StellarNetworkDashboard;
