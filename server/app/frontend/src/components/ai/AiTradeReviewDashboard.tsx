import React, { useState } from 'react';
import { Card, MetricBox } from '../shared';
import './AiDashboard.css';

const AiTradeReviewDashboard: React.FC = () => {
  const [reviews] = useState([
    { tradeId: 'TRADE-0234', symbol: 'AAPL', type: 'BUY', confidence: 92, status: 'Approved', reason: 'Strong uptrend + support bounce' },
    { tradeId: 'TRADE-0233', symbol: 'TSLA', type: 'SELL', confidence: 78, status: 'Flagged', reason: 'Potential overvaluation detected' },
    { tradeId: 'TRADE-0232', symbol: 'GOOGL', type: 'BUY', confidence: 85, status: 'Approved', reason: 'Technical breakout confirmed' },
    { tradeId: 'TRADE-0231', symbol: 'NVDA', type: 'BUY', confidence: 88, status: 'Approved', reason: 'Momentum bullish continuation' },
  ]);

  const stats = {
    pendingReview: 3,
    approved: 156,
    flagged: 12,
    avgConfidence: 84.8,
  };

  return (
    <div className="dashboard ai-trade-review-dashboard">
      <h1>AI Trade Review</h1>

      <div className="review-stats">
        <MetricBox label="Pending Review" value={stats.pendingReview} />
        <MetricBox label="Approved Trades" value={stats.approved} tone="success" />
        <MetricBox label="Flagged Trades" value={stats.flagged} />
        <MetricBox label="Avg Confidence" value={`${stats.avgConfidence}%`} />
      </div>

      <Card title="Recent Reviews" subtitle="AI analysis of recent trades">
        <div className="reviews-list">
          {reviews.map((review) => (
            <div key={review.tradeId} className="review-item">
              <div className="review-header">
                <span className="trade-id">{review.tradeId}</span>
                <span className={`review-status ${review.status.toLowerCase()}`}>{review.status}</span>
              </div>
              <div className="review-details">
                <div className="symbol-type">
                  <span className="symbol">{review.symbol}</span>
                  <span className={`type-badge ${review.type.toLowerCase()}`}>{review.type}</span>
                </div>
                <p className="review-reason">{review.reason}</p>
                <span className="confidence-score">Confidence: {review.confidence}%</span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};

export default AiTradeReviewDashboard;
