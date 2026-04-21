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
  const [currentTime, setCurrentTime] = useState(new Date());

  // Redirect to login if not authenticated
  useEffect(() => {
    if (!auth?.user && !auth?.token) {
      const savedToken = localStorage.getItem('tradeadviser-token');
      if (!savedToken) {
        navigate('/login', { replace: true });
      } else {
        console.debug('HomePage: token exists in localStorage but auth context empty, may need re-hydration');
      }
    } else {
      console.debug('HomePage: user authenticated', { email: auth?.user?.email, role: auth?.role });
    }
  }, [auth, navigate]);

  // Update time every second
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

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

  const getGreetingMessage = () => {
    const hour = currentTime.getHours();
    if (hour < 12) return 'Good Morning';
    if (hour < 18) return 'Good Afternoon';
    return 'Good Evening';
  };

  const navigationCards = [
    {
      id: 'dashboard',
      title: 'Dashboard',
      description: 'View your trading performance and portfolio overview',
      path: '/dashboard',
      icon: '📊',
      color: '#53b4ff'
    },
    {
      id: 'trading',
      title: 'Trading',
      description: 'Execute trades and monitor your positions',
      path: '/trading',
      icon: '💹',
      color: '#78e6c8'
    },
    {
      id: 'portfolio',
      title: 'Portfolio',
      description: 'Manage your investment portfolio and allocations',
      path: '/portfolio',
      icon: '💼',
      color: '#a78bfa'
    },
    {
      id: 'account',
      title: 'Account Settings',
      description: 'Manage your account settings and preferences',
      path: '/account',
      icon: '⚙️',
      color: '#f97316'
    }
  ];

  return (
    <section className="home-page">
      <div className="home-container">
        <div className="home-header">
          <h1>Welcome to TradeAdviser</h1>
          <p className="subtitle">Intelligent Trading Advisory Platform</p>
        </div>

        {auth?.user && (
          <div className="user-greeting" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h2 style={{ margin: '0 0 0.5rem 0' }}>{getGreetingMessage()}, {auth.user.email}! 👋</h2>
              <p style={{ margin: '0.25rem 0', color: '#a0aec0', fontSize: '0.95rem' }}>
                {currentTime.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })}
              </p>
              {auth.role && (
                <p style={{ margin: '0.25rem 0', color: '#78e6c8', fontSize: '0.9rem', fontWeight: '500' }}>
                  Role: <span style={{ textTransform: 'capitalize' }}>{auth.role}</span>
                </p>
              )}
            </div>
          </div>
        )}

        <div style={{ margin: '2rem 0' }}>
          <h3 style={{ color: '#a0aec0', fontSize: '0.95rem', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '1.5rem' }}>
            Quick Actions
          </h3>
        </div>

        <div className="home-grid">
          {navigationCards.map((card) => (
            <Link 
              key={card.id}
              to={card.path} 
              style={{ textDecoration: 'none' }}
            >
              <div 
                className="card" 
                style={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  cursor: 'pointer',
                  transition: 'all 0.3s ease',
                  borderLeft: `4px solid ${card.color}`,
                  position: 'relative'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-4px)';
                  e.currentTarget.style.boxShadow = `0 8px 16px rgba(${parseInt(card.color.slice(1, 3), 16)}, ${parseInt(card.color.slice(3, 5), 16)}, ${parseInt(card.color.slice(5, 7), 16)}, 0.2)`;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = 'none';
                }}
              >
                <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>
                  {card.icon}
                </div>
                <h3 style={{ color: card.color, margin: '0 0 0.5rem 0', fontSize: '1.25rem', fontWeight: '600' }}>
                  {card.title}
                </h3>
                <p style={{ color: '#a0aec0', margin: '0 0 1rem 0', fontSize: '0.95rem', flex: '1' }}>
                  {card.description}
                </p>
                <button 
                  className="btn btn-primary" 
                  style={{
                    marginTop: 'auto',
                    alignSelf: 'flex-start',
                    fontSize: '0.9rem',
                    padding: '0.6rem 1.2rem'
                  }}
                >
                  Access →
                </button>
              </div>
            </Link>
          ))}
        </div>

        <div style={{ margin: '3rem 0', padding: '1.5rem', backgroundColor: 'rgba(83, 180, 255, 0.05)', borderRadius: '8px', borderLeft: '4px solid #53b4ff' }}>
          <h3 style={{ color: '#53b4ff', margin: '0 0 0.5rem 0' }}>📚 Need Help?</h3>
          <p style={{ color: '#a0aec0', margin: 0, fontSize: '0.95rem' }}>
            Visit our documentation or contact support for assistance with trading strategies, account management, or platform features.
          </p>
        </div>

        <div className="home-actions">
          <button 
            onClick={logout} 
            disabled={loading}
            className="btn btn-secondary"
            style={{ marginLeft: 'auto' }}
          >
            {loading ? 'Logging out...' : 'Sign Out'}
          </button>
        </div>
      </div>
    </section>
  );
};

export default HomePage;
