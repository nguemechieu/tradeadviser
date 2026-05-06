import { useNavigate, Link } from "react-router-dom";
import Logo from "./Logo";
import './ErrorPage.css';

const AccessDenied = () => {
  const navigate = useNavigate();
  const goBack = () => navigate(-1);

  return (
    <div className="error-container">
      <div className="error-content">
        <div className="error-logo">
          <Logo size="large" showText={true} />
        </div>

        <div className="error-card">
          <div className="error-code">403</div>
          <h1 className="error-title">Access Denied</h1>
          <p className="error-subtitle">You don't have permission to access this resource</p>

          <div className="error-illustration">
            <svg viewBox="0 0 200 200" fill="none">
              <rect x="60" y="70" width="80" height="80" rx="8" stroke="url(#grad)" strokeWidth="2" />
              <path d="M 100 95 L 100 125" stroke="url(#grad)" strokeWidth="2" strokeLinecap="round" />
              <circle cx="100" cy="110" r="3" fill="url(#grad)" />
              <defs>
                <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style={{ stopColor: '#ff6b6b' }} />
                  <stop offset="100%" style={{ stopColor: '#ffa500' }} />
                </linearGradient>
              </defs>
            </svg>
          </div>

          <p className="error-message">Your account doesn't have the required permissions. Contact support for assistance.</p>

          <button onClick={goBack} className="btn btn-primary">
            Go Back
          </button>
          <Link to="/" className="btn btn-secondary">
            Back to Home
          </Link>
        </div>
      </div>
    </div>
  );
};

export default AccessDenied;
