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
  category: string;
  tags?: string[];
}

const ImprovedDashboard = () => {
  const { auth } = useContext(AuthContext) as {
    auth: AuthState;
  };

  const userRole = auth?.role || '';

  const dashboardCards: DashboardCard[] = [
    {
      title: 'Pro Trading Terminal',
      description: 'Automated trading with AI bots, real-time signals, and trade management',
      icon: '🚀',
      link: '/trading-terminal',
      roles: ['trader', 'admin', 'super_admin'],
      color: 'cyan',
      category: 'trading',
      tags: ['bots', 'automation', 'signals', 'terminal'],
    },
    {
      title: 'Trading Editor',
      description: 'Create and manage trading strategies with advanced tools',
      icon: '✏️',
      link: '/trading-editor',
      roles: ['trader', 'admin', 'super_admin'],
      color: 'blue',
      category: 'trading',
      tags: ['strategies', 'editor', 'tools'],
    },
    {
      title: 'Live Signals',
      description: 'Real-time trading signals powered by advanced technical analysis',
      icon: '⚡',
      link: '/signals',
      roles: ['trader', 'admin', 'super_admin'],
      color: 'yellow',
      category: 'trading',
      tags: ['signals', 'alerts', 'analysis'],
    },
    {
      title: 'Community',
      description: 'Connect with other traders and share insights',
      icon: '👥',
      link: '/community',
      roles: ['trader', 'admin', 'super_admin'],
      color: 'purple',
      category: 'community',
      tags: ['social', 'discussion', 'network'],
    },
    {
      title: 'Operations',
      description: 'System health monitoring and infrastructure management',
      icon: '🔧',
      link: '/admin/operations',
      roles: ['operations', 'admin', 'super_admin'],
      color: 'green',
      category: 'admin',
      tags: ['system', 'monitoring', 'health'],
    },
    {
      title: 'Risk Management',
      description: 'Portfolio risk limits, monitoring, and alerts',
      icon: '⚠️',
      link: '/admin/risk',
      roles: ['risk_manager', 'admin', 'super_admin'],
      color: 'red',
      category: 'portfolio',
      tags: ['risk', 'limits', 'monitoring'],
    },
    {
      title: 'Users & Licenses',
      description: 'Manage user accounts, permissions, and licenses',
      icon: '🎫',
      link: '/admin/users-licenses',
      roles: ['admin', 'super_admin'],
      color: 'yellow',
      category: 'admin',
      tags: ['users', 'management', 'licenses'],
    },
    {
      title: 'AI Agents',
      description: 'Deploy and manage intelligent trading agents',
      icon: '🤖',
      link: '/admin/agents',
      roles: ['admin', 'super_admin'],
      color: 'cyan',
      category: 'ai',
      tags: ['ai', 'automation', 'agents'],
    },
    {
      title: 'Performance Audit',
      description: 'Detailed performance metrics and compliance audit logs',
      icon: '📋',
      link: '/admin/performance-audit',
      roles: ['admin', 'super_admin'],
      color: 'indigo',
      category: 'admin',
      tags: ['audit', 'performance', 'logs'],
    },
    {
      title: 'API Documentation',
      description: 'View all available API routes and integration guides',
      icon: '🗺️',
      link: '/docs/routes',
      roles: ['admin', 'super_admin'],
      color: 'gray',
      category: 'documentation',
      tags: ['api', 'docs', 'integration'],
    },
  ];

  const displayName = auth?.firstname && auth?.lastname
    ? `${auth.firstname} ${auth.lastname}`
    : auth?.user || 'User';

  const visibleCards = dashboardCards.filter((card) =>
    card.roles.includes(userRole)
  );

  // Group cards by category
  const groupedCards = visibleCards.reduce((acc, card) => {
    if (!acc[card.category]) {
      acc[card.category] = [];
    }
    acc[card.category].push(card);
    return acc;
  }, {} as Record<string, DashboardCard[]>);

  const categoryLabels: Record<string, { title: string; icon: string }> = {
    trading: { title: 'Trading Tools', icon: '📊' },
    portfolio: { title: 'Portfolio Management', icon: '💼' },
    community: { title: 'Community', icon: '🌐' },
    admin: { title: 'Administration', icon: '⚙️' },
    ai: { title: 'AI & Automation', icon: '🚀' },
    documentation: { title: 'Resources', icon: '📚' },
  };

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

      {/* Available Modules - New Grouped Layout */}
      <div className="dashboard-section">
        <div className="section-header">
          <h3 className="section-title">Available Modules</h3>
          <p className="section-subtitle">Access all features available to your role</p>
        </div>
        
        {Object.entries(groupedCards).map(([category, cards], categoryIndex) => (
          <div key={category} className="module-category" style={{ animationDelay: `${categoryIndex * 0.1}s` }}>
            <div className="category-header">
              <span className="category-icon">{categoryLabels[category]?.icon || '📦'}</span>
              <h4 className="category-title">{categoryLabels[category]?.title || category}</h4>
              <span className="category-count">{cards.length}</span>
            </div>
            
            <div className="modules-grid">
              {cards.map((card) => (
                <Link key={card.link} to={card.link} className={`module-card card-${card.color}`}>
                  <div className="card-background"></div>
                  
                  <div className="card-header">
                    <div className="card-icon-wrapper">
                      <div className="card-icon">{card.icon}</div>
                    </div>
                    <div className="card-meta">
                      <h4 className="card-title">{card.title}</h4>
                      <div className="card-tags">
                        {card.tags?.slice(0, 2).map((tag) => (
                          <span key={tag} className="tag">{tag}</span>
                        ))}
                      </div>
                    </div>
                  </div>

                  <p className="card-description">{card.description}</p>

                  <div className="card-footer">
                    <div className="card-role">
                      <span className="role-indicator">🔐</span>
                    </div>
                    <div className="card-cta">
                      <span className="cta-text">Access</span>
                      <span className="cta-arrow">→</span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        ))}
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
