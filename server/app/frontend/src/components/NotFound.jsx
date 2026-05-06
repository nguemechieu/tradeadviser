import { Link } from "react-router-dom";
import Logo from "./Logo";
import './ErrorPage.css';

const NotFound = () => {
  return (
    <div className="error-container">
      <div className="error-content">
        <div className="error-logo">
          <Logo size="large" showText={true} />
        </div>

        <div className="error-card">
          <div className="error-code">404</div>
          <h1 className="error-title">Page Not Found</h1>
          <p className="error-subtitle">Sorry, we couldn't find the page you're looking for</p>

          <div className="error-illustration">
            <svg viewBox="0 0 200 200" fill="none">
              <circle cx="100" cy="100" r="90" stroke="url(#grad)" strokeWidth="2" opacity="0.2" />
              <path d="M 60 100 Q 100 60 140 100" stroke="url(#grad)" strokeWidth="2" />
              <circle cx="75" cy="90" r="5" fill="url(#grad)" />
              <circle cx="125" cy="90" r="5" fill="url(#grad)" />
              <defs>
                <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style={{ stopColor: '#00d4ff' }} />
                  <stop offset="100%" style={{ stopColor: '#0099ff' }} />
                </linearGradient>
              </defs>
            </svg>
          </div>

          <Link to="/" className="btn btn-primary">
            Back to Home
          </Link>
          <Link to="/login" className="btn btn-secondary">
            Go to Login
          </Link>
        </div>
      </div>
    </div>
  );
};

export default NotFound;
