import React, { useState, useEffect } from 'react';
import { portfolioService } from '../api/services';

export default function PortfolioPage() {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const token = localStorage.getItem('tradeadviser-token');

  useEffect(() => {
    const fetchPositions = async () => {
      try {
        const data = await portfolioService.getPositions(token);
        setPositions(Array.isArray(data) ? data : data.positions || []);
      } catch (err) {
        console.error('Error fetching positions:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPositions();
  }, [token]);

  if (loading) return <div>Loading...</div>;

  return (
    <div style={{ padding: '20px' }}>
      <h1>Portfolio</h1>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #ddd' }}>
            <th style={{ textAlign: 'left', padding: '10px' }}>Symbol</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Quantity</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Price</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Value</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>P&L</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((pos, idx) => (
            <tr key={idx} style={{ borderBottom: '1px solid #eee' }}>
              <td style={{ padding: '10px' }}>{pos.symbol}</td>
              <td style={{ padding: '10px' }}>{pos.quantity}</td>
              <td style={{ padding: '10px' }}>${pos.price}</td>
              <td style={{ padding: '10px' }}>${pos.value}</td>
              <td style={{ padding: '10px', color: pos.pnl > 0 ? 'green' : 'red' }}>
                ${pos.pnl}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
