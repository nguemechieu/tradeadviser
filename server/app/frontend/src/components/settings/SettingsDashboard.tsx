import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, MetricBox } from '../shared';
import './SettingsDashboard.css';

const SettingsDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [preferences] = useState({
    theme: 'dark',
    notifications: 'all',
    timezone: 'EST',
    riskProfile: 'moderate',
    twoFactor: true,
    apiAccess: true,
    paperTrading: false,
  });

  const sections = [
    {
      name: 'Notifications',
      icon: '🔔',
      description: 'Email, SMS, and push notifications',
      status: 'Enabled',
      path: '/settings/notifications',
    },
    {
      name: 'Security',
      icon: '🔒',
      description: 'Two-factor authentication, API keys',
      status: 'Active',
      path: '/settings/security',
    },
    {
      name: 'Trading',
      icon: '📈',
      description: 'Risk limits, strategies, brokers',
      status: 'Configured',
      path: '/settings/trading',
    },
    {
      name: 'Integrations',
      icon: '🔗',
      description: 'External APIs and webhooks',
      status: preferences.apiAccess ? 'Enabled' : 'Disabled',
      path: '/settings/integrations',
    },
  ];

  return (
    <div className="dashboard settings-dashboard">
      <h1>Settings</h1>

      <div className="preferences-grid">
        <MetricBox label="Theme" value={preferences.theme} />
        <MetricBox label="Risk Profile" value={preferences.riskProfile} />
        <MetricBox label="Two-Factor Auth" value={preferences.twoFactor ? 'On' : 'Off'} />
        <MetricBox label="Paper Trading" value={preferences.paperTrading ? 'Active' : 'Off'} />
      </div>

      <Card title="Settings Sections" subtitle="Configure your account preferences">
        <div className="settings-sections">
          {sections.map((section) => (
            <div
              key={section.name}
              className="settings-item"
              onClick={() => navigate(section.path)}
              style={{ cursor: 'pointer' }}
            >
              <div className="settings-icon">{section.icon}</div>
              <div className="settings-content">
                <h3 className="settings-title">{section.name}</h3>
                <p className="settings-description">{section.description}</p>
              </div>
              <div className="settings-status">
                <span className="status-badge">{section.status}</span>
                <span className="settings-arrow">→</span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card title="Preferences" subtitle="User account preferences">
        <div className="preferences-list">
          <div className="preference-item">
            <span className="pref-label">Language</span>
            <span className="pref-value">English</span>
          </div>
          <div className="preference-item">
            <span className="pref-label">Timezone</span>
            <span className="pref-value">{preferences.timezone}</span>
          </div>
          <div className="preference-item">
            <span className="pref-label">Date Format</span>
            <span className="pref-value">MM/DD/YYYY</span>
          </div>
          <div className="preference-item">
            <span className="pref-label">Currency</span>
            <span className="pref-value">USD</span>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default SettingsDashboard;
