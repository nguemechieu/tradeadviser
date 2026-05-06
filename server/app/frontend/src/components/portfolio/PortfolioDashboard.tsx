import React, { useState, useEffect } from 'react';
import { Card, MetricBox, Alert } from '../shared';
import './PortfolioDashboard.css';

const PortfolioDashboard: React.FC = () => {
  const [portfolioData] = useState({
    totalValue: 125400,
    dayChange: 2340,
    dayChangePercent: 1.89,
    allocation: [
      { asset: 'Equities', value: 45000, percent: 36 },
      { asset: 'Crypto', value: 32500, percent: 26 },
      { asset: 'Fixed Income', value: 28900, percent: 23 },
      { asset: 'Cash', value: 19000, percent: 15 },
    ],
    performance: [
      { period: 'Day', return: 1.89 },
      { period: 'Week', return: 5.23 },
      { period: 'Month', return: 12.45 },
      { period: 'YTD', return: 28.67 },
    ],
  });

  return (
    <div className="dashboard portfolio-dashboard">
      <h1>Portfolio Overview</h1>

      {portfolioData.dayChange > 0 ? (
        <Alert type="success" title="Portfolio Up" message={`+$${portfolioData.dayChange.toLocaleString()} (+${portfolioData.dayChangePercent}%)`} dismissible={false} />
      ) : (
        <Alert type="warning" title="Portfolio Down" message={`-$${Math.abs(portfolioData.dayChange).toLocaleString()} (-${Math.abs(portfolioData.dayChangePercent)}%)`} dismissible={false} />
      )}

      <div className="portfolio-metrics">
        <MetricBox label="Total Value" value={`$${portfolioData.totalValue.toLocaleString()}`} tone="neutral" />
        <MetricBox label="Day Return" value={`${portfolioData.dayChangePercent}%`} tone="success" />
        <MetricBox label="Open Positions" value="12" />
        <MetricBox label="Cash Available" value={`$${portfolioData.allocation[3].value.toLocaleString()}`} />
      </div>

      <Card title="Asset Allocation" subtitle="Current portfolio distribution">
        <div className="allocation-chart">
          {portfolioData.allocation.map((alloc) => (
            <div key={alloc.asset} className="allocation-item">
              <div className="allocation-bar">
                <div className="allocation-fill" style={{ width: `${alloc.percent}%` }}></div>
              </div>
              <span className="allocation-label">{alloc.asset}: {alloc.percent}%</span>
              <span className="allocation-value">${alloc.value.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Performance Summary" subtitle="Returns across different time periods">
        <div className="performance-grid">
          {portfolioData.performance.map((perf) => (
            <div key={perf.period} className="performance-item">
              <p className="performance-period">{perf.period}</p>
              <p className={`performance-return ${perf.return > 0 ? 'positive' : 'negative'}`}>
                {perf.return > 0 ? '+' : ''}{perf.return}%
              </p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

export default PortfolioDashboard;
