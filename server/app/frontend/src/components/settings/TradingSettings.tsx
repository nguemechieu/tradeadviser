import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, MetricBox } from '../shared';
import './SettingsPage.css';

const TradingSettings: React.FC = () => {
  const navigate = useNavigate();
  const [settings, setSettings] = useState({
    riskProfile: 'moderate',
    maxPositionSize: 10000,
    dailyLossLimit: 5000,
    paperTradingEnabled: false,
    autoExecute: false,
    confirmOrders: true,
    defaultBroker: 'coinbase',
    strategyMode: 'manual',
  });

  const handleChange = (key: keyof typeof settings, value: any) => {
    setSettings(prev => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleToggle = (key: keyof typeof settings) => {
    setSettings(prev => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleSave = () => {
    console.log('Saving trading settings:', settings);
    alert('Trading settings saved successfully!');
  };

  return (
    <div className="settings-page">
      <div className="settings-header">
        <button className="back-btn" onClick={() => navigate('/settings')}>← Back</button>
        <h1>Trading Settings</h1>
        <p>Configure your trading preferences and risk limits</p>
      </div>

      <div className="settings-content">
        <Card title="Risk Management" subtitle="Set your trading risk parameters">
          <div className="settings-field">
            <label>Risk Profile</label>
            <select
              value={settings.riskProfile}
              onChange={(e) => handleChange('riskProfile', e.target.value)}
              className="input-field"
            >
              <option value="conservative">Conservative</option>
              <option value="moderate">Moderate</option>
              <option value="aggressive">Aggressive</option>
            </select>
            <p className="field-description">Choose your overall trading risk tolerance</p>
          </div>

          <div className="settings-field">
            <label>Maximum Position Size ($)</label>
            <input
              type="number"
              value={settings.maxPositionSize}
              onChange={(e) => handleChange('maxPositionSize', parseInt(e.target.value))}
              className="input-field"
            />
            <p className="field-description">Largest single position you can open</p>
          </div>

          <div className="settings-field">
            <label>Daily Loss Limit ($)</label>
            <input
              type="number"
              value={settings.dailyLossLimit}
              onChange={(e) => handleChange('dailyLossLimit', parseInt(e.target.value))}
              className="input-field"
            />
            <p className="field-description">Stop trading when daily losses reach this amount</p>
          </div>
        </Card>

        <Card title="Trading Mode" subtitle="Choose your trading execution mode">
          <div className="settings-options">
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.paperTradingEnabled}
                  onChange={() => handleToggle('paperTradingEnabled')}
                />
                <span className="checkbox-text">Paper Trading</span>
              </label>
              <p className="option-description">Practice with virtual money (no real funds)</p>
            </div>
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.autoExecute}
                  onChange={() => handleToggle('autoExecute')}
                />
                <span className="checkbox-text">Auto-Execute Orders</span>
              </label>
              <p className="option-description">Automatically execute valid trades</p>
            </div>
            <div className="option-item">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={settings.confirmOrders}
                  onChange={() => handleToggle('confirmOrders')}
                />
                <span className="checkbox-text">Require Order Confirmation</span>
              </label>
              <p className="option-description">Always ask for confirmation before executing</p>
            </div>
          </div>
        </Card>

        <Card title="Default Settings" subtitle="Set your default trading preferences">
          <div className="settings-field">
            <label>Default Broker</label>
            <select
              value={settings.defaultBroker}
              onChange={(e) => handleChange('defaultBroker', e.target.value)}
              className="input-field"
            >
              <option value="coinbase">Coinbase</option>
              <option value="kraken">Kraken</option>
              <option value="binance">Binance</option>
              <option value="interactive">Interactive Brokers</option>
            </select>
          </div>

          <div className="settings-field">
            <label>Strategy Mode</label>
            <select
              value={settings.strategyMode}
              onChange={(e) => handleChange('strategyMode', e.target.value)}
              className="input-field"
            >
              <option value="manual">Manual</option>
              <option value="semi-automated">Semi-Automated</option>
              <option value="fully-automated">Fully Automated</option>
            </select>
          </div>
        </Card>

        <Card title="Connected Brokers" subtitle="Manage your broker integrations">
          <div className="brokers-list">
            <div className="broker-item">
              <div>
                <h4>Coinbase</h4>
                <p className="broker-status">✓ Connected</p>
              </div>
              <button className="btn-small btn-danger">Disconnect</button>
            </div>
          </div>
          <button className="btn-secondary">Add Broker Account</button>
        </Card>

        <div className="settings-actions">
          <button className="btn-secondary" onClick={() => navigate('/settings')}>Cancel</button>
          <button className="btn-primary" onClick={handleSave}>Save Changes</button>
        </div>
      </div>
    </div>
  );
};

export default TradingSettings;
