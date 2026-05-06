import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './OperationsDashboard.css';

const SystemHealthDashboard: React.FC = () => {
  const [services] = useState([
    { name: 'Trading Engine', status: 'healthy', uptime: 99.98, latency: 45, cpu: 32 },
    { name: 'Data Pipeline', status: 'healthy', uptime: 99.95, latency: 125, cpu: 48 },
    { name: 'Risk Engine', status: 'healthy', uptime: 99.99, latency: 78, cpu: 28 },
    { name: 'API Server', status: 'healthy', uptime: 99.92, latency: 234, cpu: 56 },
    { name: 'Database', status: 'degraded', uptime: 99.88, latency: 567, cpu: 78 },
  ]);

  const overallHealth = {
    uptime: 99.94,
    responseTime: 210,
    cpuUsage: 48.4,
    memoryUsage: 62.1,
  };

  return (
    <div className="dashboard system-health-dashboard">
      <h1>System Health</h1>

      <div className="health-metrics">
        <MetricBox label="Overall Uptime" value={`${overallHealth.uptime}%`} tone="success" />
        <MetricBox label="Avg Response Time" value={`${overallHealth.responseTime}ms`} />
        <MetricBox label="CPU Usage" value={`${overallHealth.cpuUsage}%`} />
        <MetricBox label="Memory Usage" value={`${overallHealth.memoryUsage}%`} />
      </div>

      <Card title="Service Status" subtitle="Real-time system health monitoring">
        <div className="services-table">
          <table>
            <thead>
              <tr>
                <th>Service</th>
                <th>Status</th>
                <th>Uptime</th>
                <th>Latency</th>
                <th>CPU</th>
              </tr>
            </thead>
            <tbody>
              {services.map((service) => (
                <tr key={service.name} className={`status-${service.status}`}>
                  <td className="service-name">{service.name}</td>
                  <td><span className={`status-badge ${service.status}`}>{service.status}</span></td>
                  <td>{service.uptime}%</td>
                  <td className={service.latency > 300 ? 'warning' : ''}>{service.latency}ms</td>
                  <td><span className={`cpu-usage ${service.cpu > 70 ? 'high' : ''}`}>{service.cpu}%</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default SystemHealthDashboard;
