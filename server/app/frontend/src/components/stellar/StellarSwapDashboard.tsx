import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './StellarDashboard.css';

const StellarSwapDashboard: React.FC = () => {
  const [swaps] = useState([
    { id: 'SWAP-0001', from: 'USDC', to: 'EUR', amount: 1000, rate: 0.92, status: 'Completed', date: '2024-05-04' },
    { id: 'SWAP-0002', from: 'BTC', to: 'ETH', amount: 0.5, rate: 16.2, status: 'Completed', date: '2024-05-03' },
    { id: 'SWAP-0003', from: 'ETH', to: 'USDC', amount: 10, rate: 2684, status: 'Pending', date: '2024-05-04' },
  ]);

  const swapMetrics = {
    totalSwaps: 156,
    volume24h: 45230,
    avgRate: 0.98,
    pendingSwaps: 1,
  };

  return (
    <div className="dashboard stellar-swap-dashboard">
      <h1>Stellar Swaps</h1>

      <div className="swap-metrics">
        <MetricBox label="Total Swaps" value={swapMetrics.totalSwaps} />
        <MetricBox label="24h Volume" value={`$${swapMetrics.volume24h.toLocaleString()}`} tone="success" />
        <MetricBox label="Avg Rate" value={swapMetrics.avgRate.toFixed(2)} />
        <MetricBox label="Pending" value={swapMetrics.pendingSwaps} />
      </div>

      <Card title="Recent Swaps" subtitle="Atomic swap history">
        <div className="swaps-table">
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>From</th>
                <th>To</th>
                <th>Amount</th>
                <th>Rate</th>
                <th>Status</th>
                <th>Date</th>
              </tr>
            </thead>
            <tbody>
              {swaps.map((swap) => (
                <tr key={swap.id} className={`status-${swap.status.toLowerCase()}`}>
                  <td className="swap-id">{swap.id}</td>
                  <td>{swap.from}</td>
                  <td>{swap.to}</td>
                  <td>{swap.amount}</td>
                  <td className="positive">{swap.rate.toFixed(2)}</td>
                  <td><span className={`status-badge ${swap.status.toLowerCase()}`}>{swap.status}</span></td>
                  <td>{swap.date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default StellarSwapDashboard;
