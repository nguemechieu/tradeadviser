import { Link } from "react-router-dom";
import Logo from "./Logo";
import './VerifyLink.css';

const VerifyLink = () => {
  return (
    <div className="verify-container">
      <div className="verify-content">
        {/* Logo */}
        <div className="verify-logo">
          <Logo size="large" showText={true} />
        </div>

        {/* Main Message */}
        <div className="verify-card">
          <div className="verify-icon">✉️</div>
          
          <h1 className="verify-title">Check Your Email</h1>
          <p className="verify-subtitle">
            We've sent a verification link to your email address
          </p>

          <div className="verify-instructions">
            <p className="instruction-step">
              <span className="step-number">1</span>
              Open your email inbox
            </p>
            <p className="instruction-step">
              <span className="step-number">2</span>
              Click the verification link
            </p>
            <p className="instruction-step">
              <span className="step-number">3</span>
              Return here to complete setup
            </p>
          </div>

          <div className="verify-tips">
            <p className="tip-title">💡 Didn't receive the email?</p>
            <ul className="tip-list">
              <li>Check your spam or junk folder</li>
              <li>Make sure to use the correct email address</li>
              <li>Resend the verification email if needed</li>
            </ul>
          </div>

          <div className="verify-actions">
            <Link to="/login" className="btn btn-primary">
              Back to Login
            </Link>
            <Link to="/" className="btn btn-secondary">
              Home
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VerifyLink;
