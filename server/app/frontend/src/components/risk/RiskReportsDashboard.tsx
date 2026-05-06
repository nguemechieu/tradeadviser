import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './RiskDashboard.css';

const RiskReportsDashboard: React.FC = () => {
  const [reports] = useState([
    { metric: 'Value at Risk (VaR)', value: 2.34, unit: '%', threshold: 5.0 },
    { metric: 'Conditional VaR (CVaR)', value: 3.87, unit: '%', threshold: 8.0 },
    { metric: 'Beta to Market', value: 0.87, unit: '', threshold: 1.5 },
    { metric: 'Maximum Drawdown', value: -8.5, unit: '%', threshold: -15.0 },
    { metric: 'Correlation to SPY', value: 0.58, unit: '', threshold: 0.8 },
    { metric: 'Diversification Ratio', value: 1.24, unit: '', threshold: 1.0 },
  ]);

  const riskMetrics = {
    overallScore: 82,
    concentration: 23,
    systemicRisk: 12,
  };

  return (
    <div className="dashboard risk-reports-dashboard">
      <h1>Risk Reports</h1>

      <div className="report-metrics">
        <MetricBox label="Risk Score" value={riskMetrics.overallScore} tone="success" />
        <MetricBox label="Concentration Risk" value={`${riskMetrics.concentration}%`} />
        <MetricBox label="Systemic Risk" value={`${riskMetrics.systemicRisk}%`} tone="success" />
        <MetricBox label="Last Updated" value="5 min ago" />
      </div>

      <Card title="Risk Metrics" subtitle="Comprehensive portfolio risk analysis">
        <div className="metrics-table">
          <table>
            <thead>
              <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>Threshold</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => {
                const isHealthy = Math.abs(report.value) <= Math.abs(report.threshold);
                return (
                  <tr key={report.metric} className={isHealthy ? 'healthy' : 'warning'}>
                    <td className="metric-name">{report.metric}</td>
                    <td>{report.value}{report.unit}</td>
                    <td>{report.threshold}{report.unit}</td>
                    <td><span className={`status-indicator ${isHealthy ? 'healthy' : 'warning'}`}>{isHealthy ? '✓' : '⚠'}</span></td>
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

export default RiskReportsDashboard;
