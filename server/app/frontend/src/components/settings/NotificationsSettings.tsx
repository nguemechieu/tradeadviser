import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, MetricBox } from '../shared';
import './SettingsPage.css';

const NotificationsSettings: React.FC = () => {
  const navigate = useNavigate();
  const [settings, setSettings] = useState({
    emailNotifications: true,
    smsNotifications: false,
    pushNotifications: true,
    tradeAlerts: true,
    priceAlerts: true,
    riskAlerts: true,
    systemAlerts: true,
    dailyDigest: true,
  });

  const handleToggle = (key: keyof typeof settings) => {
    setSettings(prev => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleSave = () => {
    console.log('Saving notification settings:', settings);
    alert('Notification settings saved successfully!');
  };

  return (
    <div className="settings-page">
      <div className="settings-header">
        <button className="back-btn" onClick={() => navigate('/settings')}>← Back</button>
        <h1>Notifications</h1>
        <p>Manage your notification preferences</p>
      </div>

      <div className="settings-content">
        <Card title="Notification Channels" subtitle="Choose how you receive notifications">
          <div className="settings-options">
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.emailNotifications}
                  onChange={() => handleToggle('emailNotifications')}
                />
                <span className="checkbox-text">Email Notifications</span>
              </label>
              <p className="option-description">Receive updates via email</p>
            </div>
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.smsNotifications}
                  onChange={() => handleToggle('smsNotifications')}
                />
                <span className="checkbox-text">SMS Notifications</span>
              </label>
              <p className="option-description">Receive critical alerts via SMS</p>
            </div>
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.pushNotifications}
                  onChange={() => handleToggle('pushNotifications')}
                />
                <span className="checkbox-text">Push Notifications</span>
              </label>
              <p className="option-description">Receive in-app push notifications</p>
            </div>
          </div>
        </Card>

        <Card title="Alert Types" subtitle="Configure which alerts you want to receive">
          <div className="settings-options">
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.tradeAlerts}
                  onChange={() => handleToggle('tradeAlerts')}
                />
                <span className="checkbox-text">Trade Alerts</span>
              </label>
              <p className="option-description">Alerts for new trade opportunities</p>
            </div>
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.priceAlerts}
                  onChange={() => handleToggle('priceAlerts')}
                />
                <span className="checkbox-text">Price Alerts</span>
              </label>
              <p className="option-description">Alerts when prices hit targets</p>
            </div>
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.riskAlerts}
                  onChange={() => handleToggle('riskAlerts')}
                />
                <span className="checkbox-text">Risk Alerts</span>
              </label>
              <p className="option-description">Alerts for risk limit violations</p>
            </div>
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.systemAlerts}
                  onChange={() => handleToggle('systemAlerts')}
                />
                <span className="checkbox-text">System Alerts</span>
              </label>
              <p className="option-description">Alerts for system maintenance and status</p>
            </div>
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.dailyDigest}
                  onChange={() => handleToggle('dailyDigest')}
                />
                <span className="checkbox-text">Daily Digest</span>
              </label>
              <p className="option-description">Summary of daily activity and alerts</p>
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

export default NotificationsSettings;
