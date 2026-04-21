import { useEffect, useState, useContext } from 'react';
import AuthContext from '../context/AuthProvider';
import './RoutesDocumentation.css';

interface ApiRoute {
  method: string;
  endpoint: string;
  description: string;
  roles: string[];
  parameters?: string;
  example?: string;
}

interface ApiCategory {
  category: string;
  routes: ApiRoute[];
}

const RoutesDocumentation = () => {
  const { auth } = useContext(AuthContext) as any;
  const [routes, setRoutes] = useState<ApiCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const mockRoutes: ApiCategory[] = [
    {
      category: 'Authentication',
      routes: [
        {
          method: 'POST',
          endpoint: '/api/auth/login',
          description: 'User login with credentials',
          roles: ['public'],
          parameters: 'identifier (email/username), password, remember_me (boolean)',
          example: '{ "identifier": "user@example.com", "password": "pass", "remember_me": true }',
        },
        {
          method: 'POST',
          endpoint: '/api/auth/register',
          description: 'Create new user account',
          roles: ['public'],
          parameters: 'email, password, username (optional), display_name (optional)',
          example: '{ "email": "user@example.com", "password": "securepass", "username": "john" }',
        },
        {
          method: 'POST',
          endpoint: '/api/auth/refresh',
          description: 'Refresh access token',
          roles: ['public'],
          parameters: 'refresh_token, remember_me (boolean)',
          example: '{ "refresh_token": "token_here", "remember_me": true }',
        },
        {
          method: 'GET',
          endpoint: '/api/auth/me',
          description: 'Get current user profile',
          roles: ['all'],
          example: 'Response: { user: {...}, role: "trader" }',
        },
      ],
    },
    {
      category: 'Admin - Operations',
      routes: [
        {
          method: 'GET',
          endpoint: '/api/admin/operations/health',
          description: 'System health status',
          roles: ['operations', 'admin', 'super_admin'],
        },
        {
          method: 'GET',
          endpoint: '/api/admin/operations/broker-status',
          description: 'Broker connectivity status',
          roles: ['operations', 'admin', 'super_admin'],
        },
        {
          method: 'GET',
          endpoint: '/api/admin/operations/active-connections',
          description: 'List of active connections',
          roles: ['operations', 'admin', 'super_admin'],
        },
        {
          method: 'GET',
          endpoint: '/api/admin/operations/deployment-status',
          description: 'Current deployment status',
          roles: ['operations', 'admin', 'super_admin'],
        },
      ],
    },
    {
      category: 'Admin - Risk Management',
      routes: [
        {
          method: 'GET',
          endpoint: '/api/admin/risk/overview',
          description: 'Portfolio risk overview',
          roles: ['risk_manager', 'admin', 'super_admin'],
        },
        {
          method: 'GET',
          endpoint: '/api/admin/risk/breaches',
          description: 'Risk limit breaches',
          roles: ['risk_manager', 'admin', 'super_admin'],
        },
        {
          method: 'GET',
          endpoint: '/api/admin/risk/limits/{user_id}',
          description: 'Get user risk limits',
          roles: ['risk_manager', 'admin', 'super_admin'],
          parameters: 'user_id (URL parameter)',
        },
        {
          method: 'PUT',
          endpoint: '/api/admin/risk/limits/{user_id}',
          description: 'Update user risk limits',
          roles: ['admin', 'super_admin'],
          parameters: 'max_position_size, max_daily_loss, max_leverage',
        },
      ],
    },
    {
      category: 'Admin - Users & Licenses',
      routes: [
        {
          method: 'GET',
          endpoint: '/api/admin/users',
          description: 'List all users',
          roles: ['admin', 'super_admin'],
        },
        {
          method: 'POST',
          endpoint: '/api/admin/users',
          description: 'Create new user',
          roles: ['admin', 'super_admin'],
          parameters: 'email, password, role, display_name',
        },
        {
          method: 'GET',
          endpoint: '/api/admin/users/{user_id}',
          description: 'Get user details',
          roles: ['admin', 'super_admin'],
        },
        {
          method: 'PUT',
          endpoint: '/api/admin/users/{user_id}/status',
          description: 'Update user status (active/inactive)',
          roles: ['admin', 'super_admin'],
        },
        {
          method: 'PUT',
          endpoint: '/api/admin/users/{user_id}/role',
          description: 'Update user role',
          roles: ['admin', 'super_admin'],
        },
        {
          method: 'GET',
          endpoint: '/api/admin/users-licenses/licenses',
          description: 'List all licenses',
          roles: ['admin', 'super_admin'],
        },
        {
          method: 'POST',
          endpoint: '/api/admin/users-licenses/licenses',
          description: 'Create new license',
          roles: ['admin', 'super_admin'],
        },
      ],
    },
    {
      category: 'Admin - AI Agents',
      routes: [
        {
          method: 'GET',
          endpoint: '/api/admin/agents',
          description: 'List all agents',
          roles: ['admin', 'super_admin'],
        },
        {
          method: 'POST',
          endpoint: '/api/admin/agents',
          description: 'Deploy new agent',
          roles: ['admin', 'super_admin'],
          parameters: 'name, strategy, config (JSON)',
        },
        {
          method: 'PUT',
          endpoint: '/api/admin/agents/{agent_id}',
          description: 'Update agent',
          roles: ['admin', 'super_admin'],
        },
        {
          method: 'DELETE',
          endpoint: '/api/admin/agents/{agent_id}',
          description: 'Remove agent',
          roles: ['admin', 'super_admin'],
        },
      ],
    },
    {
      category: 'Admin - Performance & Audit',
      routes: [
        {
          method: 'GET',
          endpoint: '/api/admin/performance-audit/overview',
          description: 'Performance audit overview',
          roles: ['admin', 'super_admin'],
        },
        {
          method: 'GET',
          endpoint: '/api/admin/performance-audit/audit-logs',
          description: 'System audit logs',
          roles: ['admin', 'super_admin'],
        },
        {
          method: 'GET',
          endpoint: '/api/admin/performance-audit/audit-trail',
          description: 'Detailed audit trail',
          roles: ['admin', 'super_admin'],
        },
      ],
    },
  ];

  useEffect(() => {
    setLoading(false);
    setRoutes(mockRoutes);
    if (mockRoutes.length > 0) {
      setSelectedCategory(mockRoutes[0].category);
    }
  }, []);

  const canViewRoute = (roles: string[]) => {
    if (roles.includes('public')) return true;
    if (roles.includes('all')) return true;
    return roles.includes(auth?.role || '');
  };

  const userRole = auth?.role || '';

  const visibleRoutes = routes
    .map((category) => ({
      ...category,
      routes: category.routes.filter((route) => canViewRoute(route.roles)),
    }))
    .filter((category) => category.routes.length > 0);

  const getMethodColor = (method: string) => {
    switch (method) {
      case 'GET':
        return 'method-get';
      case 'POST':
        return 'method-post';
      case 'PUT':
        return 'method-put';
      case 'DELETE':
        return 'method-delete';
      default:
        return 'method-default';
    }
  };

  return (
    <div className="routes-documentation">
      <div className="routes-header">
        <h1>API Routes Documentation</h1>
        <p>Complete reference of all available API endpoints</p>
        <div className="route-info">
          <span className="info-badge">Your Role: {userRole.toUpperCase()}</span>
          <span className="info-badge">Visible Routes: {visibleRoutes.reduce((sum, cat) => sum + cat.routes.length, 0)}</span>
        </div>
      </div>

      <div className="routes-container">
        {/* Categories Sidebar */}
        <div className="categories-sidebar">
          <h3 className="sidebar-title">Categories</h3>
          <div className="categories-list">
            {visibleRoutes.map((category) => (
              <button
                key={category.category}
                className={`category-item ${selectedCategory === category.category ? 'active' : ''}`}
                onClick={() => setSelectedCategory(category.category)}
              >
                <span className="category-name">{category.category}</span>
                <span className="route-count">{category.routes.length}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Routes Content */}
        <div className="routes-content">
          {loading ? (
            <div className="loading">Loading routes...</div>
          ) : (
            visibleRoutes.map((category) => (
              selectedCategory === category.category && (
                <div key={category.category} className="category-section">
                  <h2 className="category-title">{category.category}</h2>

                  <div className="routes-list">
                    {category.routes.map((route, index) => (
                      <div key={index} className="route-item">
                        <div className="route-header">
                          <span className={`method-badge ${getMethodColor(route.method)}`}>
                            {route.method}
                          </span>
                          <code className="endpoint">{route.endpoint}</code>
                        </div>

                        <p className="route-description">{route.description}</p>

                        {route.parameters && (
                          <div className="route-details">
                            <strong>Parameters:</strong>
                            <p>{route.parameters}</p>
                          </div>
                        )}

                        {route.example && (
                          <div className="route-details">
                            <strong>Example:</strong>
                            <pre className="example-code">{route.example}</pre>
                          </div>
                        )}

                        <div className="route-roles">
                          {route.roles.map((role) => (
                            <span key={role} className="role-tag">
                              {role}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )
            ))
          )}
        </div>
      </div>

      {/* API Guide */}
      <div className="api-guide">
        <h3>Getting Started with the API</h3>
        <div className="guide-section">
          <h4>1. Authentication</h4>
          <p>
            Send a POST request to <code>/api/auth/login</code> with your credentials to get an access token
            and refresh token.
          </p>
          <pre className="guide-code">{`curl -X POST http://localhost:8000/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"identifier":"user@example.com","password":"pass","remember_me":true}'`}</pre>
        </div>

        <div className="guide-section">
          <h4>2. Using the Access Token</h4>
          <p>Include the access token in the Authorization header for all protected routes:</p>
          <pre className="guide-code">{`curl -X GET http://localhost:8000/api/auth/me \\
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"`}</pre>
        </div>

        <div className="guide-section">
          <h4>3. Token Refresh</h4>
          <p>
            When your access token expires (30 minutes), use the refresh token to get a new one:
          </p>
          <pre className="guide-code">{`curl -X POST http://localhost:8000/api/auth/refresh \\
  -H "Content-Type: application/json" \\
  -d '{"refresh_token":"YOUR_REFRESH_TOKEN","remember_me":true}'`}</pre>
        </div>
      </div>
    </div>
  );
};

export default RoutesDocumentation;
