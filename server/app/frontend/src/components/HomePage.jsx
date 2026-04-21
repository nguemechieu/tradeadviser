import { useNavigate, Link } from 'react-router-dom';
import { useContext, useState, useEffect } from 'react';
import AuthContext from '../context/AuthProvider';
import axiosInstance from '../api/axiosConfig';
import '../styles.css';

const HomePage = () => {
  const context = useContext(AuthContext);
  
  // Defensive check for context
  if (!context) {
    return <div style={{ color: '#fff', padding: '2rem' }}>Error: Auth context not available</div>;
  }

  const { auth, setAuth } = context;
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!auth?.user && !auth?.token) {
      const savedToken = localStorage.getItem('tradeadviser-token');
      if (!savedToken) {
        navigate('/login', { replace: true });
      }
    }
  }, [auth, navigate]);

  const logout = async () => {
    try {
      setLoading(true);
      await axiosInstance.post('/auth/logout');
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      localStorage.removeItem('tradeadviser-token');
      localStorage.removeItem('tradeadviser-user');
      setAuth({});
      navigate('/login', { replace: true });
      setLoading(false);
    }
  };

  return (
    <section className="home-page">
      <div className="home-container">
        <div className="home-header">
          <h1>Welcome to TradeAdviser</h1>
          <p className="subtitle">Intelligent Trading Advisory Platform</p>
        </div>

        {auth?.user && (
          <div className="user-greeting">
            <h2>Welcome, {auth.user.email}!</h2>
          </div>
        )}

        <div className="home-grid">
          <div className="card">
            <h3>Dashboard</h3>
            <p>View your trading performance and portfolio overview</p>
            <Link to="/dashboard" className="btn btn-primary">
              Go to Dashboard
            </Link>
          </div>

          <div className="card">
            <h3>Trading</h3>
            <p>Execute trades and monitor your positions</p>
            <Link to="/trading" className="btn btn-primary">
              Go to Trading
            </Link>
          </div>

          <div className="card">
            <h3>Account</h3>
            <p>Manage your account settings and preferences</p>
            <Link to="/account" className="btn btn-primary">
              Go to Account
            </Link>
          </div>

          <div className="card">
            <h3>Editor</h3>
            <p>Create and edit trading strategies</p>
            <Link to="/trading-editor" className="btn btn-primary">
              Go to Editor
            </Link>
          </div>
        </div>

        <div className="home-actions">
          <button 
            onClick={logout} 
            disabled={loading}
            className="btn btn-secondary"
          >
            {loading ? 'Logging out...' : 'Sign Out'}
          </button>
        </div>
      </div>
    </section>
  );
};

export default HomePage;
