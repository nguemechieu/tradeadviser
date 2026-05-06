import React, { useState } from 'react';
import './AdminPanel.css';

interface User {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'premium' | 'user';
  status: 'active' | 'inactive';
  joined: string;
}

interface License {
  id: string;
  type: 'starter' | 'professional' | 'enterprise';
  user: string;
  expiryDate: string;
  status: 'active' | 'expiring' | 'expired';
}

interface SystemMetric {
  name: string;
  value: string;
  status: 'healthy' | 'warning' | 'critical';
  percentage: number;
}

const AdminPanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'licenses' | 'system' | 'audit'>('overview');
  const [users] = useState<User[]>([
    { id: '1', name: 'Alice Johnson', email: 'alice@example.com', role: 'admin', status: 'active', joined: '2023-01-15' },
    { id: '2', name: 'Bob Chen', email: 'bob@example.com', role: 'premium', status: 'active', joined: '2023-06-20' },
    { id: '3', name: 'Sarah Williams', email: 'sarah@example.com', role: 'user', status: 'active', joined: '2024-01-10' },
    { id: '4', name: 'James Wilson', email: 'james@example.com', role: 'user', status: 'inactive', joined: '2024-02-01' },
    { id: '5', name: 'Emma Davis', email: 'emma@example.com', role: 'premium', status: 'active', joined: '2024-03-05' },
  ]);

  const [licenses] = useState<License[]>([
    { id: '1', type: 'enterprise', user: 'Alice Johnson', expiryDate: '2025-12-31', status: 'active' },
    { id: '2', type: 'professional', user: 'Bob Chen', expiryDate: '2024-06-30', status: 'expiring' },
    { id: '3', type: 'starter', user: 'Sarah Williams', expiryDate: '2024-05-15', status: 'expired' },
  ]);

  const [systemMetrics] = useState<SystemMetric[]>([
    { name: 'CPU Usage', value: '45%', status: 'healthy', percentage: 45 },
    { name: 'Memory Usage', value: '62%', status: 'healthy', percentage: 62 },
    { name: 'Disk Space', value: '78%', status: 'warning', percentage: 78 },
    { name: 'API Response Time', value: '245ms', status: 'healthy', percentage: 0 },
    { name: 'Database Connections', value: '156/200', status: 'healthy', percentage: 78 },
  ]);

  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  const handleUserAction = (userId: string, action: string) => {
    alert(`${action} user ${userId}`);
  };

  return (
    <section className="admin-panel">
      {/* Header */}
      <div className="admin-header">
        <div className="header-content">
          <h1>Admin Control Panel</h1>
          <p>Manage users, licenses, system health, and operations</p>
        </div>
        <div className="header-controls">
          <button className="btn-icon">🔔 Alerts</button>
          <button className="btn-icon">⚙️ Settings</button>
          <button className="btn-icon">📊 Reports</button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="admin-tabs">
        <button
          className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          📊 Overview
        </button>
        <button
          className={`tab ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          👥 Users
        </button>
        <button
          className={`tab ${activeTab === 'licenses' ? 'active' : ''}`}
          onClick={() => setActiveTab('licenses')}
        >
          🔑 Licenses
        </button>
        <button
          className={`tab ${activeTab === 'system' ? 'active' : ''}`}
          onClick={() => setActiveTab('system')}
        >
          🖥️ System
        </button>
        <button
          className={`tab ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          📋 Audit Log
        </button>
      </div>

      <div className="admin-container">
        {/* OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <div className="overview-section">
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-icon">👥</div>
                <div className="stat-info">
                  <h3>Total Users</h3>
                  <p className="stat-value">2,543</p>
                  <span className="stat-change positive">+12% this month</span>
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-icon">💎</div>
                <div className="stat-info">
                  <h3>Active Licenses</h3>
                  <p className="stat-value">1,234</p>
                  <span className="stat-change neutral">3 expiring soon</span>
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-icon">⚡</div>
                <div className="stat-info">
                  <h3>System Uptime</h3>
                  <p className="stat-value">99.98%</p>
                  <span className="stat-change positive">All systems operational</span>
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-icon">🔒</div>
                <div className="stat-info">
                  <h3>Security Score</h3>
                  <p className="stat-value">94/100</p>
                  <span className="stat-change warning">3 vulnerabilities found</span>
                </div>
              </div>
            </div>

            <div className="overview-charts">
              <div className="chart-card">
                <h3>User Activity (Last 7 Days)</h3>
                <div className="chart-placeholder">
                  <div className="bar-chart">
                    <div className="bar" style={{ height: '60%' }}>
                      <span>Mon</span>
                    </div>
                    <div className="bar" style={{ height: '72%' }}>
                      <span>Tue</span>
                    </div>
                    <div className="bar" style={{ height: '81%' }}>
                      <span>Wed</span>
                    </div>
                    <div className="bar" style={{ height: '68%' }}>
                      <span>Thu</span>
                    </div>
                    <div className="bar" style={{ height: '85%' }}>
                      <span>Fri</span>
                    </div>
                    <div className="bar" style={{ height: '73%' }}>
                      <span>Sat</span>
                    </div>
                    <div className="bar" style={{ height: '55%' }}>
                      <span>Sun</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="chart-card">
                <h3>Revenue Breakdown</h3>
                <div className="chart-placeholder">
                  <div className="pie-chart">
                    <div className="pie-segment" style={{ background: 'conic-gradient(from 0deg, #78e6c8 0deg, #78e6c8 118.8deg, #53b4ff 118.8deg, #53b4ff 234deg, #ff6b6b 234deg, #ff6b6b 360deg)' }}></div>
                    <div className="pie-legend">
                      <div><span style={{ background: '#78e6c8' }}></span> Starter: 33%</div>
                      <div><span style={{ background: '#53b4ff' }}></span> Professional: 45%</div>
                      <div><span style={{ background: '#ff6b6b' }}></span> Enterprise: 22%</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="recent-activity">
              <h3>Recent Activities</h3>
              <div className="activity-list">
                <div className="activity-item">
                  <span className="activity-icon">✅</span>
                  <div className="activity-content">
                    <p className="activity-text">New user registered: <strong>John Smith</strong></p>
                    <span className="activity-time">2 minutes ago</span>
                  </div>
                </div>

                <div className="activity-item">
                  <span className="activity-icon">⚠️</span>
                  <div className="activity-content">
                    <p className="activity-text">License expiration warning: <strong>3 licenses</strong> expiring in 30 days</p>
                    <span className="activity-time">1 hour ago</span>
                  </div>
                </div>

                <div className="activity-item">
                  <span className="activity-icon">🔄</span>
                  <div className="activity-content">
                    <p className="activity-text">System backup completed successfully</p>
                    <span className="activity-time">3 hours ago</span>
                  </div>
                </div>

                <div className="activity-item">
                  <span className="activity-icon">💳</span>
                  <div className="activity-content">
                    <p className="activity-text">Payment received from <strong>Alice Johnson</strong> - $499.00</p>
                    <span className="activity-time">5 hours ago</span>
                  </div>
                </div>

                <div className="activity-item">
                  <span className="activity-icon">🚀</span>
                  <div className="activity-content">
                    <p className="activity-text">New feature deployment: <strong>Advanced Analytics</strong></p>
                    <span className="activity-time">1 day ago</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* USERS TAB */}
        {activeTab === 'users' && (
          <div className="users-section">
            <div className="section-header">
              <h2>User Management</h2>
              <button className="btn-primary">+ Add User</button>
            </div>

            <div className="table-container">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Joined</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id} onClick={() => setSelectedUser(user)}>
                      <td>
                        <div className="user-cell">
                          <div className="user-avatar">👤</div>
                          <span>{user.name}</span>
                        </div>
                      </td>
                      <td>{user.email}</td>
                      <td>
                        <span className={`badge badge-${user.role}`}>{user.role}</span>
                      </td>
                      <td>
                        <span className={`badge badge-${user.status}`}>
                          {user.status === 'active' ? '🟢' : '🔴'} {user.status}
                        </span>
                      </td>
                      <td>{new Date(user.joined).toLocaleDateString()}</td>
                      <td>
                        <div className="action-buttons">
                          <button
                            className="btn-action edit"
                            onClick={() => handleUserAction(user.id, 'Edit')}
                          >
                            Edit
                          </button>
                          <button
                            className="btn-action delete"
                            onClick={() => handleUserAction(user.id, 'Delete')}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {selectedUser && (
              <div className="user-detail-panel">
                <div className="detail-header">
                  <h3>User Details</h3>
                  <button className="btn-close" onClick={() => setSelectedUser(null)}>✕</button>
                </div>
                <div className="detail-body">
                  <p><strong>Name:</strong> {selectedUser.name}</p>
                  <p><strong>Email:</strong> {selectedUser.email}</p>
                  <p><strong>Role:</strong> {selectedUser.role}</p>
                  <p><strong>Status:</strong> {selectedUser.status}</p>
                  <p><strong>Joined:</strong> {new Date(selectedUser.joined).toLocaleDateString()}</p>
                  <div className="detail-actions">
                    <button className="btn-secondary">Edit User</button>
                    <button className="btn-danger">Suspend User</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* LICENSES TAB */}
        {activeTab === 'licenses' && (
          <div className="licenses-section">
            <div className="section-header">
              <h2>License Management</h2>
              <button className="btn-primary">+ Issue License</button>
            </div>

            <div className="licenses-grid">
              {licenses.map((license) => (
                <div key={license.id} className={`license-card ${license.status}`}>
                  <div className="license-icon">
                    {license.status === 'expired' ? '❌' : license.status === 'expiring' ? '⚠️' : '✅'}
                  </div>
                  <div className="license-info">
                    <h3>{license.type.toUpperCase()}</h3>
                    <p className="license-user">{license.user}</p>
                  </div>

                  <div className="license-dates">
                    <span className="label">Expires:</span>
                    <span className="date">{new Date(license.expiryDate).toLocaleDateString()}</span>
                  </div>

                  <div className={`license-status ${license.status}`}>
                    {license.status === 'active' && 'ACTIVE'}
                    {license.status === 'expiring' && 'EXPIRING SOON'}
                    {license.status === 'expired' && 'EXPIRED'}
                  </div>

                  <div className="license-actions">
                    <button className="btn-small">Renew</button>
                    <button className="btn-small">Revoke</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SYSTEM TAB */}
        {activeTab === 'system' && (
          <div className="system-section">
            <h2>System Health</h2>

            <div className="metrics-grid">
              {systemMetrics.map((metric) => (
                <div key={metric.name} className={`metric-card ${metric.status}`}>
                  <div className="metric-header">
                    <h4>{metric.name}</h4>
                    <span className={`status-indicator ${metric.status}`}></span>
                  </div>

                  {metric.percentage > 0 ? (
                    <>
                      <div className="metric-value">{metric.value}</div>
                      <div className="metric-bar-wrapper">
                        <div className="metric-bar">
                          <div
                            className="metric-bar-fill"
                            style={{
                              width: `${metric.percentage}%`,
                              background:
                                metric.status === 'healthy'
                                  ? 'linear-gradient(90deg, #78e6c8, #53b4ff)'
                                  : metric.status === 'warning'
                                  ? 'linear-gradient(90deg, #fbbf24, #f59e0b)'
                                  : 'linear-gradient(90deg, #ff6b6b, #dc2626)',
                            }}
                          ></div>
                        </div>
                        <span className="percentage">{metric.percentage}%</span>
                      </div>
                    </>
                  ) : (
                    <div className="metric-value">{metric.value}</div>
                  )}
                </div>
              ))}
            </div>

            <div className="system-info">
              <h3>Server Information</h3>
              <div className="info-grid">
                <div className="info-item">
                  <span className="info-label">Uptime</span>
                  <span className="info-value">99.98%</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Server OS</span>
                  <span className="info-value">Ubuntu 22.04 LTS</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Python Version</span>
                  <span className="info-value">3.11.5</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Last Backup</span>
                  <span className="info-value">3 hours ago</span>
                </div>
              </div>
            </div>

            <div className="system-actions">
              <h3>Actions</h3>
              <div className="action-grid">
                <button className="btn-action-large">🔄 Restart Server</button>
                <button className="btn-action-large">💾 Backup Now</button>
                <button className="btn-action-large">🧹 Clear Cache</button>
                <button className="btn-action-large">🔧 Maintenance Mode</button>
              </div>
            </div>
          </div>
        )}

        {/* AUDIT LOG TAB */}
        {activeTab === 'audit' && (
          <div className="audit-section">
            <h2>Audit Log</h2>

            <div className="audit-filters">
              <select className="filter-select">
                <option>All Events</option>
                <option>User Activity</option>
                <option>System Events</option>
                <option>License Changes</option>
              </select>
              <select className="filter-select">
                <option>Last 7 Days</option>
                <option>Last 30 Days</option>
                <option>Last 90 Days</option>
              </select>
            </div>

            <div className="audit-log">
              <div className="log-entry">
                <div className="log-time">10:45 AM</div>
                <div className="log-icon">👤</div>
                <div className="log-content">
                  <p className="log-message">User <strong>Alice Johnson</strong> logged in from <strong>192.168.1.100</strong></p>
                  <span className="log-category">User Login</span>
                </div>
              </div>

              <div className="log-entry">
                <div className="log-time">10:30 AM</div>
                <div className="log-icon">💳</div>
                <div className="log-content">
                  <p className="log-message">License <strong>ENT-2024-001</strong> issued to <strong>Bob Chen</strong></p>
                  <span className="log-category">License Management</span>
                </div>
              </div>

              <div className="log-entry">
                <div className="log-time">09:15 AM</div>
                <div className="log-icon">⚙️</div>
                <div className="log-content">
                  <p className="log-message">System configuration updated by <strong>admin</strong></p>
                  <span className="log-category">System Change</span>
                </div>
              </div>

              <div className="log-entry">
                <div className="log-time">08:00 AM</div>
                <div className="log-icon">🔒</div>
                <div className="log-content">
                  <p className="log-message">Security scan completed - <strong>0 threats</strong> detected</p>
                  <span className="log-category">Security</span>
                </div>
              </div>

              <div className="log-entry">
                <div className="log-time">Yesterday 11:30 PM</div>
                <div className="log-icon">💾</div>
                <div className="log-content">
                  <p className="log-message">Automated backup completed - <strong>5.2 GB</strong> backed up</p>
                  <span className="log-category">System Maintenance</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export default AdminPanel;
