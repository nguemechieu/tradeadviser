import { useContext } from 'react';
import { Link } from 'react-router-dom';
import AuthContext from '../context/AuthProvider';
import './ImprovedDashboard.css';

interface AuthState {
  user?: string;
  email?: string;
  firstname?: string;
  lastname?: string;
  role?: string;
  accessToken?: string;
  isLoggedIn?: boolean;
}

interface DashboardCard {
  title: string;
  description: string;
  icon: string;
  link: string;
  roles: string[];
  color: string;
}

const ImprovedDashboard = () => {
  const { auth } = useContext(AuthContext) as {
    auth: AuthState;
  };

  const userRole = auth?.role || '';

  const dashboardCards: DashboardCard[] = [
    {
      title: 'Trading Editor',
      description: 'Create and manage trading strategies',
      icon: '✏️',
      link: '/trading-editor',
      roles: ['trader', 'admin', 'super_admin'],
      color: 'blue',
    },
    {
      title: 'Community',
      description: 'Connect with other traders',
      icon: '👥',
      link: '/community',
      roles: ['trader', 'admin', 'super_admin'],
      color: 'purple',
    },
    {
      title: 'Operations',
      description: 'System health and monitoring',
      icon: '🔧',
      link: '/admin/operations',
      roles: ['operations', 'admin', 'super_admin'],
      color: 'green',
    },
    {
      title: 'Risk Management',
      description: 'Portfolio risk limits and monitoring',
      icon: '⚠️',
      link: '/admin/risk',
      roles: ['risk_manager', 'admin', 'super_admin'],
      color: 'red',
    },
    {
      title: 'Users & Licenses',
      description: 'Manage user accounts and licenses',
      icon: '🎫',
      link: '/admin/users-licenses',
      roles: ['admin', 'super_admin'],
      color: 'yellow',
    },
    {
      title: 'AI Agents',
      description: 'Deploy and manage trading agents',
      icon: '🤖',
      link: '/admin/agents',
      roles: ['admin', 'super_admin'],
      color: 'cyan',
    },
    {
      title: 'Performance Audit',
      description: 'Detailed performance metrics and audit logs',
      icon: '📋',
      link: '/admin/performance-audit',
      roles: ['admin', 'super_admin'],
      color: 'indigo',
    },
    {
      title: 'API Documentation',
      description: 'View all available API routes',
      icon: '🗺️',
      link: '/docs/routes',
      roles: ['admin', 'super_admin'],
      color: 'gray',
    },
  ];

  const displayName = auth?.firstname && auth?.lastname
    ? `${auth.firstname} ${auth.lastname}`
    : auth?.user || 'User';

  const visibleCards = dashboardCards.filter((card) =>
    card.roles.includes(userRole)
  );

  return (
    <section className="dashboard-improved">
      {/* Header */}
      <div className="dashboard-header-section">
        <div className="dashboard-header-content">
          <h1 className="dashboard-title">Welcome to TradeAdviser</h1>
          <p className="dashboard-subtitle">Intelligent Trading Advisory Platform</p>
        </div>
        <div className="dashboard-avatar">
          <div className="avatar-placeholder">
            {displayName.charAt(0).toUpperCase()}
          </div>
        </div>
      </div>

      {/* User Info Card */}
      <div className="dashboard-user-card">
        <div className="user-card-content">
          <div>
            <h2 className="user-name">Welcome, {displayName}! 👋</h2>
            <p className="user-email">
              <span className="email-label">Email:</span> {auth?.email}
            </p>
            {auth?.user && (
              <p className="user-username">
                <span className="username-label">Username:</span> {auth.user}
              </p>
            )}
            <div className="user-role-badge">
              <span className="role-text">{userRole.toUpperCase()}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="dashboard-stats">
        <div className="stat-item">
          <span className="stat-icon">🎯</span>
          <div className="stat-content">
            <p className="stat-label">Accessible Modules</p>
            <p className="stat-value">{visibleCards.length}</p>
          </div>
        </div>
        <div className="stat-item">
          <span className="stat-icon">🔐</span>
          <div className="stat-content">
            <p className="stat-label">Role</p>
            <p className="stat-value">{userRole}</p>
          </div>
        </div>
        <div className="stat-item">
          <span className="stat-icon">✅</span>
          <div className="stat-content">
            <p className="stat-label">Status</p>
            <p className="stat-value">Active</p>
          </div>
        </div>
      </div>

      {/* Navigation Grid */}
      <div className="dashboard-section">
        <h3 className="section-title">Available Modules</h3>
        <div className="dashboard-grid">
          {visibleCards.map((card) => (
            <Link key={card.link} to={card.link} className={`dashboard-card card-${card.color}`}>
              <div className="card-icon">{card.icon}</div>
              <h4 className="card-title">{card.title}</h4>
              <p className="card-description">{card.description}</p>
              <div className="card-arrow">→</div>
            </Link>
          ))}
        </div>
      </div>

      {/* Quick Links */}
      <div className="dashboard-section">
        <h3 className="section-title">Quick Links</h3>
        <div className="quick-links">
          <a href="/docs/routes" className="quick-link">
            📚 View API Routes
          </a>
          <a href="/docs/guide" className="quick-link">
            📖 User Guide
          </a>
          <a href="https://github.com/tradeadviser" className="quick-link" target="_blank" rel="noopener noreferrer">
            💻 GitHub Repository
          </a>
          <a href="/community" className="quick-link">
            👥 Join Community
          </a>
        </div>
      </div>

      {/* Features Overview */}
      <div className="dashboard-section">
        <h3 className="section-title">Platform Features</h3>
        <div className="features-list">
          <div className="feature-item">
            <span className="feature-icon">📊</span>
            <div className="feature-content">
              <h4>Real-time Analytics</h4>
              <p>Monitor your portfolio with real-time data and advanced analytics</p>
            </div>
          </div>
          <div className="feature-item">
            <span className="feature-icon">🤖</span>
            <div className="feature-content">
              <h4>AI-Powered Agents</h4>
              <p>Deploy intelligent trading agents for automated trading strategies</p>
            </div>
          </div>
          <div className="feature-item">
            <span className="feature-icon">⚠️</span>
            <div className="feature-content">
              <h4>Risk Management</h4>
              <p>Advanced risk monitoring and limit management tools</p>
            </div>
          </div>
          <div className="feature-item">
            <span className="feature-icon">🔒</span>
            <div className="feature-content">
              <h4>Enterprise Security</h4>
              <p>Enterprise-grade security with role-based access control</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default ImprovedDashboard;
