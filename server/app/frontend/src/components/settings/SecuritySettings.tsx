import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../shared';
import './SettingsPage.css';

const SecuritySettings: React.FC = () => {
  const navigate = useNavigate();
  const [settings, setSettings] = useState({
    twoFactorAuth: true,
    biometricAuth: false,
    sessionTimeout: 30,
    ipWhitelist: false,
    deviceTrust: true,
  });

  const [showPassword, setShowPassword] = useState(false);

  const handleToggle = (key: keyof typeof settings) => {
    setSettings(prev => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleSave = () => {
    console.log('Saving security settings:', settings);
    alert('Security settings saved successfully!');
  };

  return (
    <div className="settings-page">
      <div className="settings-header">
        <button className="back-btn" onClick={() => navigate('/settings')}>← Back</button>
        <h1>Security</h1>
        <p>Manage your account security and access</p>
      </div>

      <div className="settings-content">
        <Card title="Authentication" subtitle="Manage how you access your account">
          <div className="settings-options">
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.twoFactorAuth}
                  onChange={() => handleToggle('twoFactorAuth')}
                />
                <span className="checkbox-text">Two-Factor Authentication</span>
              </label>
              <p className="option-description">Require both password and authentication code to sign in</p>
            </div>
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.biometricAuth}
                  onChange={() => handleToggle('biometricAuth')}
                />
                <span className="checkbox-text">Biometric Authentication</span>
              </label>
              <p className="option-description">Use fingerprint or face recognition to sign in</p>
            </div>
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.deviceTrust}
                  onChange={() => handleToggle('deviceTrust')}
                />
                <span className="checkbox-text">Trust This Device</span>
              </label>
              <p className="option-description">Don't require authentication on this device for 30 days</p>
            </div>
          </div>
        </Card>

        <Card title="Session Settings" subtitle="Control your login sessions">
          <div className="settings-field">
            <label>Session Timeout (minutes)</label>
            <input
              type="number"
              value={settings.sessionTimeout}
              onChange={(e) => setSettings(prev => ({ ...prev, sessionTimeout: parseInt(e.target.value) }))}
              min="5"
              max="480"
              className="input-field"
            />
            <p className="field-description">Automatically log out after this period of inactivity</p>
          </div>
        </Card>

        <Card title="IP & Location" subtitle="Restrict access by location and IP address">
          <div className="settings-options">
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.ipWhitelist}
                  onChange={() => handleToggle('ipWhitelist')}
                />
                <span className="checkbox-text">IP Whitelist</span>
              </label>
              <p className="option-description">Only allow access from specific IP addresses</p>
            </div>
          </div>
        </Card>

        <Card title="API Keys" subtitle="Manage your API access credentials">
          <div className="api-keys-list">
            <div className="api-key-item">
              <div>
                <h4>Primary API Key</h4>
                <p className="key-created">Created: Jan 15, 2024</p>
              </div>
              <div className="key-actions">
                <button className="btn-small">Regenerate</button>
                <button className="btn-small btn-danger">Revoke</button>
              </div>
            </div>
          </div>
          <button className="btn-secondary">Generate New API Key</button>
        </Card>

        <Card title="Change Password" subtitle="Update your account password">
          <div className="settings-field">
            <label>Current Password</label>
            <div className="password-input">
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="Enter current password"
                className="input-field"
              />
              <button onClick={() => setShowPassword(!showPassword)} className="toggle-password">
                {showPassword ? '👁️' : '👁️‍🗨️'}
              </button>
            </div>
          </div>
          <div className="settings-field">
            <label>New Password</label>
            <input
              type="password"
              placeholder="Enter new password"
              className="input-field"
            />
          </div>
          <div className="settings-field">
            <label>Confirm Password</label>
            <input
              type="password"
              placeholder="Confirm new password"
              className="input-field"
            />
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

export default SecuritySettings;
