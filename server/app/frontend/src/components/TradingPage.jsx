import { useContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AuthContext from '../context/AuthProvider';
import axiosInstance from '../api/axiosConfig';
import '../styles.css';

const TradingPage = () => {
  const { auth } = useContext(AuthContext);
  const navigate = useNavigate();
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showNewTradeForm, setShowNewTradeForm] = useState(false);
  const [formData, setFormData] = useState({
    symbol: '',
    side: 'BUY',
    amount: '',
    price: '',
    stopLoss: '',
    takeProfit: ''
  });

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    try {
      setLoading(true);
      const { data } = await axiosInstance.get('/trades');
      setTrades(Array.isArray(data) ? data : data.trades || []);
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching trades:', err);
      if (err.response?.status === 401) {
        navigate('/login');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      const { data: newTrade } = await axiosInstance.post('/trades', {
        symbol: formData.symbol.toUpperCase(),
        side: formData.side,
        amount: parseFloat(formData.amount),
        entry_price: parseFloat(formData.price),
        stop_loss: formData.stopLoss ? parseFloat(formData.stopLoss) : null,
        take_profit: formData.takeProfit ? parseFloat(formData.takeProfit) : null
      });
      setTrades(prev => [newTrade, ...prev]);
      setFormData({
        symbol: '',
        side: 'BUY',
        amount: '',
        price: '',
        stopLoss: '',
        takeProfit: ''
      });
      setShowNewTradeForm(false);
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error('Error creating trade:', err);
    } finally {
      setLoading(false);
    }
  };

  const closeTrade = async (tradeId) => {
    try {
      await axiosInstance.post(`/trades/${tradeId}/close`);
      setTrades(prev => prev.filter(trade => trade.id !== tradeId));
    } catch (err) {
      setError(err.message);
      console.error('Error closing trade:', err);
    }
  };

  return (
    <section className="trading-page">
      <div className="trading-container">
        <div className="trading-header">
          <h1>Trading</h1>
          <p>Execute and manage your trades</p>
          <button 
            onClick={() => setShowNewTradeForm(!showNewTradeForm)}
            className="btn btn-primary"
          >
            {showNewTradeForm ? 'Cancel' : 'New Trade'}
          </button>
        </div>

        {error && <div className="error-message">{error}</div>}

        {showNewTradeForm && (
          <div className="new-trade-form-container">
            <form onSubmit={handleSubmit} className="form-group">
              <h2>Create New Trade</h2>

              <div className="form-row">
                <div className="form-field">
                  <label>Symbol *</label>
                  <input 
                    type="text" 
                    name="symbol" 
                    value={formData.symbol}
                    onChange={handleInputChange}
                    placeholder="e.g., EURUSD"
                    className="input-field"
                    required
                  />
                </div>

                <div className="form-field">
                  <label>Side *</label>
                  <select 
                    name="side" 
                    value={formData.side}
                    onChange={handleInputChange}
                    className="input-field"
                  >
                    <option value="BUY">BUY</option>
                    <option value="SELL">SELL</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-field">
                  <label>Amount (Lots) *</label>
                  <input 
                    type="number" 
                    name="amount" 
                    value={formData.amount}
                    onChange={handleInputChange}
                    placeholder="0.1"
                    step="0.01"
                    className="input-field"
                    required
                  />
                </div>

                <div className="form-field">
                  <label>Entry Price *</label>
                  <input 
                    type="number" 
                    name="price" 
                    value={formData.price}
                    onChange={handleInputChange}
                    placeholder="1.0000"
                    step="0.0001"
                    className="input-field"
                    required
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-field">
                  <label>Stop Loss</label>
                  <input 
                    type="number" 
                    name="stopLoss" 
                    value={formData.stopLoss}
                    onChange={handleInputChange}
                    placeholder="0.9900"
                    step="0.0001"
                    className="input-field"
                  />
                </div>

                <div className="form-field">
                  <label>Take Profit</label>
                  <input 
                    type="number" 
                    name="takeProfit" 
                    value={formData.takeProfit}
                    onChange={handleInputChange}
                    placeholder="1.0100"
                    step="0.0001"
                    className="input-field"
                  />
                </div>
              </div>

              <button 
                type="submit" 
                disabled={loading}
                className="btn btn-primary"
              >
                {loading ? 'Creating...' : 'Create Trade'}
              </button>
            </form>
          </div>
        )}

        <div className="trades-list">
          <h2>Open Trades</h2>
          
          {loading && !trades.length ? (
            <div className="loading">Loading trades...</div>
          ) : trades.length === 0 ? (
            <div className="empty-state">
              <p>No open trades</p>
              <button 
                onClick={() => setShowNewTradeForm(true)}
                className="btn btn-primary"
              >
                Create your first trade
              </button>
            </div>
          ) : (
            <div className="trades-table">
              <table>
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Amount</th>
                    <th>Entry Price</th>
                    <th>Current Price</th>
                    <th>P&L</th>
                    <th>Stop Loss</th>
                    <th>Take Profit</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map(trade => (
                    <tr key={trade.id} className={trade.side === 'BUY' ? 'buy' : 'sell'}>
                      <td className="symbol">{trade.symbol}</td>
                      <td className={`side ${trade.side.toLowerCase()}`}>{trade.side}</td>
                      <td>{trade.amount}</td>
                      <td>{trade.entry_price?.toFixed(4)}</td>
                      <td>{trade.current_price?.toFixed(4) || 'N/A'}</td>
                      <td className={trade.pnl >= 0 ? 'profit' : 'loss'}>
                        {trade.pnl?.toFixed(2) || 'N/A'}
                      </td>
                      <td>{trade.stop_loss?.toFixed(4) || 'N/A'}</td>
                      <td>{trade.take_profit?.toFixed(4) || 'N/A'}</td>
                      <td>
                        <button 
                          onClick={() => closeTrade(trade.id)}
                          className="btn btn-danger"
                        >
                          Close
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};

export default TradingPage;
