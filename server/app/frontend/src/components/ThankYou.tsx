import React from "react";
import { Link } from "react-router-dom";
import Logo from "./Logo";
import './SuccessPage.css';

const ThankYou = () => (
  <div className="success-container">
    <div className="success-content">
      <div className="success-logo">
        <Logo size="large" showText={true} />
      </div>

      <div className="success-card">
        <div className="success-checkmark">✓</div>
        <h1 className="success-title">Thank You!</h1>
        <p className="success-subtitle">Your request has been received successfully</p>

        <div className="success-details">
          <p>We've received your submission and will review it shortly.</p>
          <p>We'll follow up with you via email at your earliest convenience.</p>
        </div>

        <div className="success-actions">
          <Link to="/dashboard" className="btn btn-primary">
            Go to Dashboard
          </Link>
          <Link to="/" className="btn btn-secondary">
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  </div>
);
