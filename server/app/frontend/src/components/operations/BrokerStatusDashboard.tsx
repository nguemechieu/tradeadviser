import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './OperationsDashboard.css';

const BrokerStatusDashboard: React.FC = () => {
  const [brokerStatus] = useState([
    { broker: 'Interactive Brokers', status: 'operational', apiLatency: 45, connectionTime: '2024-05-04 09:30', issues: 0 },
    { broker: 'TD Ameritrade', status: 'operational', apiLatency: 62, connectionTime: '2024-05-04 09:25', issues: 0 },
    { broker: 'Coinbase', status: 'operational', apiLatency: 89, connectionTime: '2024-05-04 09:28', issues: 0 },
    { broker: 'Kraken', status: 'degraded', apiLatency: 234, connectionTime: '2024-05-04 09:15', issues: 1 },
  ]);

  const statusSummary = {
    connected: 4,
    operational: 3,
    degraded: 1,
    apiCalls24h: 45230,
  };

  return (
    <div className="dashboard broker-status-dashboard">
      <h1>Broker Status</h1>

      <div className="status-metrics">
        <MetricBox label="Connected Brokers" value={statusSummary.connected} tone="success" />
        <MetricBox label="Operational" value={statusSummary.operational} tone="success" />
        <MetricBox label="Degraded" value={statusSummary.degraded} />
        <MetricBox label="API Calls (24h)" value={statusSummary.apiCalls24h.toLocaleString()} />
      </div>

      <Card title="Broker Connectivity" subtitle="Real-time broker API status">
        <div className="status-table">
          <table>
            <thead>
              <tr>
                <th>Broker</th>
                <th>Status</th>
                <th>API Latency</th>
                <th>Last Connection</th>
                <th>Issues</th>
              </tr>
            </thead>
            <tbody>
              {brokerStatus.map((broker) => (
                <tr key={broker.broker} className={`status-${broker.status}`}>
                  <td className="broker-name">{broker.broker}</td>
                  <td><span className={`status-badge ${broker.status}`}>{broker.status}</span></td>
                  <td className={broker.apiLatency > 200 ? 'warning' : ''}>{broker.apiLatency}ms</td>
                  <td className="timestamp">{broker.connectionTime}</td>
                  <td>{broker.issues === 0 ? '✓ None' : `⚠ ${broker.issues}`}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default BrokerStatusDashboard;
