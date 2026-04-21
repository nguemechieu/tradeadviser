import React, { useState, useEffect } from 'react';
import { tradesService } from '../api/services';

export default function TradesPage() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const token = localStorage.getItem('tradeadviser-token');

  useEffect(() => {
    const fetchTrades = async () => {
      try {
        const data = await tradesService.getAll(token);
        setTrades(Array.isArray(data) ? data : data.trades || []);
      } catch (err) {
        console.error('Error fetching trades:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchTrades();
  }, [token]);

  if (loading) return <div>Loading...</div>;

  return (
    <div style={{ padding: '20px' }}>
      <h1>Trades</h1>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #ddd' }}>
            <th style={{ textAlign: 'left', padding: '10px' }}>ID</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Symbol</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Status</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Entry Price</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Exit Price</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>P&L</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => (
            <tr key={trade.id} style={{ borderBottom: '1px solid #eee' }}>
              <td style={{ padding: '10px' }}>{trade.id}</td>
              <td style={{ padding: '10px' }}>{trade.symbol}</td>
              <td style={{ padding: '10px' }}>{trade.status}</td>
              <td style={{ padding: '10px' }}>${trade.entry_price}</td>
              <td style={{ padding: '10px' }}>${trade.exit_price}</td>
              <td style={{ padding: '10px', color: trade.pnl > 0 ? 'green' : 'red' }}>
                ${trade.pnl}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
