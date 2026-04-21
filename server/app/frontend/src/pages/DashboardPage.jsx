import React, { useState, useEffect } from 'react';
import { portfolioService, performanceService } from '../api/services';

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const token = localStorage.getItem('tradeadviser-token');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [portfolio, performance] = await Promise.all([
          portfolioService.getDashboard(token),
          performanceService.getDashboard(token),
        ]);
        setData({ portfolio, performance });
      } catch (err) {
        console.error('Error fetching dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [token]);

  if (loading) return <div>Loading...</div>;

  return (
    <div style={{ padding: '20px' }}>
      <h1>Dashboard</h1>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        <div style={{ padding: '20px', border: '1px solid #ddd', borderRadius: '8px' }}>
          <h2>Portfolio Overview</h2>
          <pre>{JSON.stringify(data?.portfolio, null, 2)}</pre>
        </div>
        <div style={{ padding: '20px', border: '1px solid #ddd', borderRadius: '8px' }}>
          <h2>Performance</h2>
          <pre>{JSON.stringify(data?.performance, null, 2)}</pre>
        </div>
      </div>
    </div>
  );
}
