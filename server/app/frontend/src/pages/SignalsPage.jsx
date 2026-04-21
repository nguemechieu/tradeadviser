import React, { useState, useEffect } from 'react';
import { signalsService } from '../api/services';

export default function SignalsPage() {
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(true);
  const token = localStorage.getItem('tradeadviser-token');

  useEffect(() => {
    const fetchSignals = async () => {
      try {
        const data = await signalsService.getAll(token);
        setSignals(Array.isArray(data) ? data : data.signals || []);
      } catch (err) {
        console.error('Error fetching signals:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchSignals();
  }, [token]);

  if (loading) return <div>Loading...</div>;

  return (
    <div style={{ padding: '20px' }}>
      <h1>Trading Signals</h1>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #ddd' }}>
            <th style={{ textAlign: 'left', padding: '10px' }}>ID</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Symbol</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Signal</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Strength</th>
            <th style={{ textAlign: 'left', padding: '10px' }}>Timestamp</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((signal) => (
            <tr key={signal.id} style={{ borderBottom: '1px solid #eee' }}>
              <td style={{ padding: '10px' }}>{signal.id}</td>
              <td style={{ padding: '10px' }}>{signal.symbol}</td>
              <td style={{ padding: '10px' }}>{signal.signal}</td>
              <td style={{ padding: '10px' }}>{signal.strength}</td>
              <td style={{ padding: '10px' }}>{signal.timestamp}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
