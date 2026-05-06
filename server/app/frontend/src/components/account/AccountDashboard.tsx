import React, { useState } from 'react';
import { Card, MetricBox, Badge } from '../shared';
import './AccountDashboard.css';

const AccountDashboard: React.FC = () => {
  const [accountInfo] = useState({
    username: 'trader_pro_2024',
    email: 'trader@example.com',
    status: 'verified',
    accountType: 'premium',
    createdDate: '2022-06-15',
    lastLogin: '2024-05-04 14:32',
    subscriptionStatus: 'active',
    subscriptionTier: 'Premium',
  });

  const accountStats = [
    { label: 'Total Trades', value: 1247, icon: '📊' },
    { label: 'Win Rate', value: '68.5%', icon: '✓' },
    { label: 'Followers', value: '342', icon: '👥' },
    { label: 'Monthly P&L', value: '+$12,450', icon: '💰' },
  ];

  return (
    <div className="dashboard account-dashboard">
      <h1>My Account</h1>

      <Card title="Account Information" subtitle="Your profile details and account status">
        <div className="account-info">
          <div className="account-avatar">T</div>
          <div className="account-details">
            <h2 className="account-username">{accountInfo.username}</h2>
            <p className="account-email">{accountInfo.email}</p>
            <div className="account-badges">
              <Badge type={accountInfo.status}>{accountInfo.status}</Badge>
              <Badge type="info">{accountInfo.accountType}</Badge>
            </div>
          </div>
        </div>
      </Card>

      <div className="stats-grid">
        {accountStats.map((stat) => (
          <MetricBox key={stat.label} label={stat.label} value={stat.value} />
        ))}
      </div>

      <Card title="Subscription" subtitle="Current subscription and billing">
        <div className="subscription-info">
          <div className="subscription-item">
            <span className="subscription-label">Current Tier</span>
            <span className="subscription-value">{accountInfo.subscriptionTier}</span>
          </div>
          <div className="subscription-item">
            <span className="subscription-label">Status</span>
            <span className={`subscription-status ${accountInfo.subscriptionStatus}`}>{accountInfo.subscriptionStatus}</span>
          </div>
          <div className="subscription-item">
            <span className="subscription-label">Renewal Date</span>
            <span className="subscription-value">2024-06-04</span>
          </div>
          <div className="subscription-item">
            <span className="subscription-label">Member Since</span>
            <span className="subscription-value">{accountInfo.createdDate}</span>
          </div>
        </div>
      </Card>

      <Card title="Account Activity" subtitle="Recent account access and changes">
        <div className="activity-list">
          <div className="activity-item">
            <span className="activity-time">Last Login</span>
            <span className="activity-value">{accountInfo.lastLogin}</span>
          </div>
          <div className="activity-item">
            <span className="activity-time">Last Password Change</span>
            <span className="activity-value">45 days ago</span>
          </div>
          <div className="activity-item">
            <span className="activity-time">Last API Key Generated</span>
            <span className="activity-value">30 days ago</span>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default AccountDashboard;
