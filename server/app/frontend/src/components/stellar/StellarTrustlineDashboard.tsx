import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './StellarDashboard.css';

const StellarTrustlineDashboard: React.FC = () => {
  const [trustlines] = useState([
    { asset: 'USDC', issuer: 'Centre', limit: 100000, balance: 50000, status: 'Active' },
    { asset: 'EUR', issuer: 'Tempo', limit: 50000, balance: 35000, status: 'Active' },
    { asset: 'BTC', issuer: 'Stellar Development Fund', limit: 10, balance: 2.5, status: 'Active' },
    { asset: 'ETH', issuer: 'Stellar Development Fund', limit: 100, balance: 15.3, status: 'Active' },
  ]);

  const metrics = {
    totalTrustlines: trustlines.length,
    activeTrustlines: trustlines.filter(t => t.status === 'Active').length,
    avgUtilization: 65.2,
  };

  return (
    <div className="dashboard stellar-trustline-dashboard">
      <h1>Stellar Trustlines</h1>

      <div className="trustline-metrics">
        <MetricBox label="Total Trustlines" value={metrics.totalTrustlines} />
        <MetricBox label="Active" value={metrics.activeTrustlines} tone="success" />
        <MetricBox label="Avg Utilization" value={`${metrics.avgUtilization}%`} />
        <MetricBox label="Capacity" value="420K XLM" />
      </div>

      <Card title="Trustline Configuration" subtitle="Asset trustlines and limits">
        <div className="trustlines-table">
          <table>
            <thead>
              <tr>
                <th>Asset</th>
                <th>Issuer</th>
                <th>Limit</th>
                <th>Balance</th>
                <th>Utilization</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {trustlines.map((tl) => {
                const util = (tl.balance / tl.limit * 100).toFixed(1);
                return (
                  <tr key={tl.asset}>
                    <td className="asset-name">{tl.asset}</td>
                    <td className="issuer-name">{tl.issuer}</td>
                    <td>{tl.limit}</td>
                    <td className="positive">{tl.balance}</td>
                    <td>
                      <div className="util-bar">
                        <div className="util-fill" style={{ width: `${util}%` }}></div>
                      </div>
                      <span>{util}%</span>
                    </td>
                    <td><span className="status-active">{tl.status}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default StellarTrustlineDashboard;
