import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../shared';
import './SettingsPage.css';

const IntegrationsSettings: React.FC = () => {
  const navigate = useNavigate();
  const [integrations, setIntegrations] = useState([
    {
      name: 'Slack',
      description: 'Get alerts and notifications in Slack',
      icon: '💬',
      connected: true,
      status: 'Active',
    },
    {
      name: 'Telegram',
      description: 'Receive alerts via Telegram bot',
      icon: '📱',
      connected: false,
      status: 'Not Connected',
    },
    {
      name: 'Discord',
      description: 'Join our Discord community for trading signals',
      icon: '🎮',
      connected: false,
      status: 'Not Connected',
    },
    {
      name: 'Email',
      description: 'Email notifications and reports',
      icon: '📧',
      connected: true,
      status: 'Active',
    },
  ]);

  const [webhooks, setWebhooks] = useState([
    {
      id: 1,
      url: 'https://example.com/webhook',
      events: ['trade.executed', 'risk.alert'],
      active: true,
    },
  ]);

  const handleToggleIntegration = (index: number) => {
    const updated = [...integrations];
    updated[index].connected = !updated[index].connected;
    updated[index].status = updated[index].connected ? 'Active' : 'Not Connected';
    setIntegrations(updated);
  };

  const handleAddWebhook = () => {
    const newWebhook = {
      id: Math.max(...webhooks.map(w => w.id), 0) + 1,
      url: '',
      events: [],
      active: true,
    };
    setWebhooks([...webhooks, newWebhook]);
  };

  const handleRemoveWebhook = (id: number) => {
    setWebhooks(webhooks.filter(w => w.id !== id));
  };

  const handleSave = () => {
    console.log('Saving integration settings:', { integrations, webhooks });
    alert('Integration settings saved successfully!');
  };

  return (
    <div className="settings-page">
      <div className="settings-header">
        <button className="back-btn" onClick={() => navigate('/settings')}>← Back</button>
        <h1>Integrations</h1>
        <p>Connect external services and APIs</p>
      </div>

      <div className="settings-content">
        <Card title="Third-Party Integrations" subtitle="Connect with external messaging and notification services">
          <div className="integrations-list">
            {integrations.map((integration, idx) => (
              <div key={integration.name} className="integration-item">
                <div className="integration-icon">{integration.icon}</div>
                <div className="integration-info">
                  <h4>{integration.name}</h4>
                  <p>{integration.description}</p>
                </div>
                <div className="integration-status">
                  <span className={`status-badge ${integration.connected ? 'active' : 'inactive'}`}>
                    {integration.status}
                  </span>
                  <label className="toggle-switch">
                    <input
                      type="checkbox"
                      checked={integration.connected}
                      onChange={() => handleToggleIntegration(idx)}
                    />
                    <span className="toggle-slider"></span>
                  </label>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card title="API Access" subtitle="Manage your API credentials and access">
          <div className="api-section">
            <div className="api-credential">
              <div>
                <h4>REST API</h4>
                <p>Direct API access to TradeAdviser</p>
              </div>
              <button className="btn-small">View Docs</button>
            </div>
            <div className="api-credential">
              <div>
                <h4>WebSocket API</h4>
                <p>Real-time data streaming</p>
              </div>
              <button className="btn-small">View Docs</button>
            </div>
            <div className="api-credential">
              <div>
                <h4>FIX Protocol</h4>
                <p>Financial Information Exchange</p>
              </div>
              <button className="btn-small">View Docs</button>
            </div>
          </div>
        </Card>

        <Card title="Webhooks" subtitle="Receive real-time events to your endpoints">
          <div className="webhooks-list">
            {webhooks.length === 0 ? (
              <p className="empty-state">No webhooks configured. Create your first webhook to get started.</p>
            ) : (
              webhooks.map((webhook) => (
                <div key={webhook.id} className="webhook-item">
                  <div className="webhook-info">
                    <h4>Webhook #{webhook.id}</h4>
                    <p className="webhook-url">{webhook.url || 'Not configured'}</p>
                    <p className="webhook-events">Events: {webhook.events.join(', ') || 'None selected'}</p>
                  </div>
                  <div className="webhook-actions">
                    <label className="toggle-switch">
                      <input type="checkbox" checked={webhook.active} readOnly />
                      <span className="toggle-slider"></span>
                    </label>
                    <button
                      className="btn-small btn-danger"
                      onClick={() => handleRemoveWebhook(webhook.id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
          <button className="btn-secondary" onClick={handleAddWebhook}>Add Webhook</button>
        </Card>

        <Card title="OAuth Connections" subtitle="Apps and services authorized to access your account">
          <div className="oauth-list">
            <div className="oauth-item">
              <div>
                <h4>Trading Bot Pro</h4>
                <p className="oauth-scope">Scope: Read portfolio, Execute trades</p>
                <p className="oauth-created">Authorized: Dec 15, 2024</p>
              </div>
              <button className="btn-small btn-danger">Revoke</button>
            </div>
          </div>
        </Card>

        <div className="settings-actions">
          <button className="btn-secondary" onClick={() => navigate('/settings')}>Cancel</button>
          <button className="btn-primary" onClick={handleSave}>Save Changes</button>
        </div>
      </div>
    </div>
  );
};

export default IntegrationsSettings;
