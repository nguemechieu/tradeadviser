import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './OperationsDashboard.css';

const DeploymentDashboard: React.FC = () => {
  const [deployments] = useState([
    { version: 'v2.4.1', environment: 'production', status: 'active', deployedAt: '2024-05-03 14:30', commits: 8, health: 'healthy' },
    { version: 'v2.4.0', environment: 'production', status: 'previous', deployedAt: '2024-05-01 09:15', commits: 12, health: 'healthy' },
    { version: 'v2.5.0-rc1', environment: 'staging', status: 'active', deployedAt: '2024-05-04 18:00', commits: 23, health: 'testing' },
  ]);

  const deploymentStats = {
    activeDeployments: deployments.filter(d => d.status === 'active').length,
    totalRollouts: 156,
    avgDeployTime: 45,
    failureRate: 0.2,
  };

  return (
    <div className="dashboard deployment-dashboard">
      <h1>Deployment Management</h1>

      <div className="deployment-metrics">
        <MetricBox label="Active Deployments" value={deploymentStats.activeDeployments} tone="success" />
        <MetricBox label="Total Rollouts" value={deploymentStats.totalRollouts} />
        <MetricBox label="Avg Deploy Time" value={`${deploymentStats.avgDeployTime}s`} />
        <MetricBox label="Failure Rate" value={`${deploymentStats.failureRate}%`} tone="success" />
      </div>

      <Card title="Deployment History" subtitle="Recent application deployments">
        <div className="deployment-table">
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Environment</th>
                <th>Status</th>
                <th>Deployed At</th>
                <th>Commits</th>
                <th>Health</th>
              </tr>
            </thead>
            <tbody>
              {deployments.map((deployment) => (
                <tr key={deployment.version} className={`status-${deployment.health}`}>
                  <td className="version">{deployment.version}</td>
                  <td><span className={`env-badge ${deployment.environment}`}>{deployment.environment}</span></td>
                  <td><span className={`status-badge ${deployment.status}`}>{deployment.status}</span></td>
                  <td className="timestamp">{deployment.deployedAt}</td>
                  <td>{deployment.commits}</td>
                  <td><span className={`health-badge ${deployment.health}`}>{deployment.health}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};

export default DeploymentDashboard;
