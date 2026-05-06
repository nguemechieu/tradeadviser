import React from "react";
import { Link, useNavigate } from "react-router-dom";
import Logo from "./Logo";
import './ErrorPage.css';

const Unauthorized = () => {
  const navigate = useNavigate();
  const goBack = () => navigate(-1);

  return (
    <div className="error-container">
      <div className="error-content">
        <div className="error-logo">
          <Logo size="large" showText={true} />
        </div>

        <div className="error-card">
          <div className="error-code">401</div>
          <h1 className="error-title">Unauthorized</h1>
          <p className="error-subtitle">Your session has expired or authentication is required</p>

          <div className="error-illustration">
            <svg viewBox="0 0 200 200" fill="none">
              <circle cx="100" cy="100" r="70" stroke="url(#grad)" strokeWidth="2" opacity="0.3" />
              <path d="M 85 85 L 115 115 M 115 85 L 85 115" stroke="url(#grad)" strokeWidth="3" strokeLinecap="round" />
              <defs>
                <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style={{ stopColor: '#ff6b6b' }} />
                  <stop offset="100%" style={{ stopColor: '#ffa500' }} />
                </linearGradient>
              </defs>
            </svg>
          </div>

          <p className="error-message">Please sign in again to continue using TradeAdviser</p>

          <button onClick={goBack} className="btn btn-primary">
            Go Back
          </button>
          <Link to="/login" className="btn btn-secondary">
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Unauthorized;
