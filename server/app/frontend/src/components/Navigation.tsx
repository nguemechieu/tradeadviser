import { useState, useContext } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import AuthContext from '../context/AuthProvider';
import './Navigation.css';

interface NavItem {
  label: string;
  path: string;
  icon: string;
  roles?: string[];
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const Navigation = () => {
  const { auth, setAuth } = useContext(AuthContext) as any;
  const location = useLocation();
  const navigate = useNavigate();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const userRole = auth?.role || '';

  const navigationGroups: NavGroup[] = [
    {
      title: '📊 Dashboard',
      items: [
        { label: 'Home', path: '/', icon: '🏠' },
        { label: 'Trading Editor', path: '/trading-editor', icon: '✏️', roles: ['trader', 'admin', 'super_admin'] },
        { label: 'Community', path: '/community', icon: '👥' },
      ],
    },
    {
      title: '⚙️ Admin Panel',
      items: [
        { label: 'Operations', path: '/admin/operations', icon: '🔧', roles: ['operations', 'admin', 'super_admin'] },
        { label: 'Risk Management', path: '/admin/risk', icon: '⚠️', roles: ['risk_manager', 'admin', 'super_admin'] },
        { label: 'Users & Licenses', path: '/admin/users-licenses', icon: '🎫', roles: ['admin', 'super_admin'] },
        { label: 'AI Agents', path: '/admin/agents', icon: '🤖', roles: ['admin', 'super_admin'] },
        { label: 'Performance Audit', path: '/admin/performance-audit', icon: '📋', roles: ['admin', 'super_admin'] },
      ],
    },
    {
      title: '📚 Documentation',
      items: [
        { label: 'API Routes', path: '/docs/routes', icon: '🗺️', roles: ['admin', 'super_admin'] },
        { label: 'User Guide', path: '/docs/guide', icon: '📖' },
      ],
    },
  ];

  const canAccessItem = (roles?: string[]) => {
    if (!roles || roles.length === 0) return true;
    return roles.includes(userRole);
  };

  const handleLogout = () => {
    setAuth({});
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
    navigate('/login');
    setIsMenuOpen(false);
  };

  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className="navigation">
      <div className="nav-container">
        {/* Logo & Brand */}
        <Link to="/" className="nav-brand">
          <img src="/logo192.png" alt="TradeAdviser Logo" className="nav-logo" />
          <span className="nav-title">TradeAdviser</span>
        </Link>

        {/* Menu Toggle Button */}
        <button
          className="nav-toggle"
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          aria-label="Toggle navigation"
        >
          <span className={`hamburger ${isMenuOpen ? 'active' : ''}`}>
            <span></span>
            <span></span>
            <span></span>
          </span>
        </button>

        {/* Navigation Menu */}
        <div className={`nav-menu ${isMenuOpen ? 'active' : ''}`}>
          {navigationGroups.map((group) => {
            const visibleItems = group.items.filter((item) => canAccessItem(item.roles));
            if (visibleItems.length === 0) return null;

            return (
              <div key={group.title} className="nav-group">
                <h3 className="nav-group-title">{group.title}</h3>
                <ul className="nav-items">
                  {visibleItems.map((item) => (
                    <li key={item.path}>
                      <Link
                        to={item.path}
                        className={`nav-item ${isActive(item.path) ? 'active' : ''}`}
                        onClick={() => setIsMenuOpen(false)}
                      >
                        <span className="nav-icon">{item.icon}</span>
                        <span className="nav-label">{item.label}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}

          {/* User Info */}
          <div className="nav-footer">
            {auth?.isLoggedIn && (
              <>
                <div className="nav-user-info">
                  <p className="nav-user-name">
                    {auth?.firstname} {auth?.lastname}
                  </p>
                  <p className="nav-user-role">{userRole.toUpperCase()}</p>
                </div>
                <button className="nav-logout" onClick={handleLogout}>
                  🚪 Logout
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Overlay */}
      {isMenuOpen && (
        <div className="nav-overlay" onClick={() => setIsMenuOpen(false)} />
      )}
    </nav>
  );
};

export default Navigation;
