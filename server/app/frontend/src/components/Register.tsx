import React, { useState, FormEvent, ChangeEvent, FC } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { axiosPublic } from '../api/axios';
import Logo from './Logo';
import './Register.css';

const REGEX = {
  USER: /^[A-z][A-z0-9-_]{3,23}$/,
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  PWD: /^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%]).{8,24}$/,
};

interface RegisterData {
  username: string;
  email: string;
  password: string;
  matchPwd: string;
  firstname: string;
  lastname: string;
  phone?: string;
}

const Register: FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<RegisterData>({
    username: '',
    email: '',
    password: '',
    matchPwd: '',
    firstname: '',
    lastname: '',
    phone: '',
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [errMsg, setErrMsg] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const validateField = (name: string, value: string): string => {
    switch (name) {
      case 'username':
        return !REGEX.USER.test(value)
          ? 'Username: 4-24 chars, starts with letter, alphanumeric/dash/underscore only'
          : '';
      case 'email':
        return !REGEX.EMAIL.test(value) ? 'Please enter a valid email' : '';
      case 'password':
        return !REGEX.PWD.test(value)
          ? 'Password: 8-24 chars, must include uppercase, lowercase, number, and special char (!@#$%)'
          : '';
      case 'matchPwd':
        return value !== formData.password ? 'Passwords do not match' : '';
      case 'firstname':
      case 'lastname':
        return !value.trim() ? `${name === 'firstname' ? 'First' : 'Last'} name is required` : '';
      default:
        return '';
    }
  };

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Real-time validation
    const error = validateField(name, value);
    setErrors((prev) => ({
      ...prev,
      [name]: error,
    }));
    setErrMsg('');
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};
    Object.entries(formData).forEach(([key, value]) => {
      if (key !== 'phone') {
        const error = validateField(key, value);
        if (error) newErrors[key] = error;
      }
    });

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!validateForm()) {
      setErrMsg('Please fix validation errors');
      return;
    }

    setLoading(true);
    try {
      const payload = {
        username: formData.username,
        email: formData.email,
        password: formData.password,
        firstname: formData.firstname,
        lastname: formData.lastname,
      };

      const response = await axiosPublic.post('/api/v3/auth/register', payload);

      if ([200, 201].includes(response.status)) {
        setSuccess(true);
        setTimeout(() => {
          navigate('/login', { replace: true });
        }, 2000);
      }
    } catch (err: any) {
      const message =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        'Registration failed. Please try again.';
      setErrMsg(message);
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="auth-container">
        <div className="success-message">
          <div className="success-content">
            <div className="success-icon">✓</div>
            <h2>Welcome to TradeAdviser!</h2>
            <p>Your account has been created successfully</p>
            <p style={{ fontSize: '0.9rem', color: '#a0a0a0', marginTop: '20px' }}>
              Redirecting to login in a moment...
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-container">
      <div className="auth-wrapper auth-wrapper-register">
        {/* Left side - Branding */}
        <div className="auth-branding">
          <div className="branding-content">
            <Logo size="large" showText={true} />
            <p>Join thousands of professional traders</p>
            <ul className="features">
              <li>✓ Create an account in minutes</li>
              <li>✓ Secure & encrypted platform</li>
              <li>✓ 24/7 customer support</li>
              <li>✓ Risk management tools included</li>
            </ul>
          </div>
        </div>

        {/* Right side - Registration Form */}
        <div className="auth-card auth-card-register">
          <div className="register-header-section">
            <div className="auth-header">
              <h1>Create Account</h1>
              <p>Join the trading community and start analyzing</p>
            </div>

            {errMsg && (
              <div className="auth-error" role="alert" aria-live="assertive">
                <span className="error-icon">⚠️</span>
                <span>{errMsg}</span>
              </div>
            )}
          </div>

          <div className="register-content">
            <form id="register-form" onSubmit={handleSubmit} className="auth-form register-form">
            {/* Username */}
            <div className="form-group">
              <label htmlFor="username">Username</label>
              <div className="input-wrapper">
                <span className="input-icon">👤</span>
                <input
                  type="text"
                  id="username"
                  name="username"
                  value={formData.username}
                  onChange={handleInputChange}
                  placeholder="Choose a username"
                  required
                  disabled={loading}
                  className={`form-input ${errors.username ? 'has-error' : ''}`}
                />
              </div>
              {errors.username && <span className="error-text">{errors.username}</span>}
            </div>

            {/* Email */}
            <div className="form-group">
              <label htmlFor="email">Email Address</label>
              <div className="input-wrapper">
                <span className="input-icon">✉️</span>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleInputChange}
                  placeholder="your@email.com"
                  required
                  disabled={loading}
                  className={`form-input ${errors.email ? 'has-error' : ''}`}
                />
              </div>
              {errors.email && <span className="error-text">{errors.email}</span>}
            </div>

            {/* First & Last Name */}
            <div className="form-row">
              <div className="form-group">
                <label htmlFor="firstname">First Name</label>
                <div className="input-wrapper">
                  <span className="input-icon">📝</span>
                  <input
                    type="text"
                    id="firstname"
                    name="firstname"
                    value={formData.firstname}
                    onChange={handleInputChange}
                    placeholder="John"
                    required
                    disabled={loading}
                    className={`form-input ${errors.firstname ? 'has-error' : ''}`}
                  />
                </div>
                {errors.firstname && <span className="error-text">{errors.firstname}</span>}
              </div>

              <div className="form-group">
                <label htmlFor="lastname">Last Name</label>
                <div className="input-wrapper">
                  <span className="input-icon">📝</span>
                  <input
                    type="text"
                    id="lastname"
                    name="lastname"
                    value={formData.lastname}
                    onChange={handleInputChange}
                    placeholder="Doe"
                    required
                    disabled={loading}
                    className={`form-input ${errors.lastname ? 'has-error' : ''}`}
                  />
                </div>
                {errors.lastname && <span className="error-text">{errors.lastname}</span>}
              </div>
            </div>

            {/* Password */}
            <div className="form-group">
              <label htmlFor="password">Password</label>
              <div className="input-wrapper">
                <span className="input-icon">🔐</span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  placeholder="Create a strong password"
                  required
                  disabled={loading}
                  className={`form-input ${errors.password ? 'has-error' : ''}`}
                />
                <button
                  type="button"
                  className="toggle-password"
                  onClick={() => setShowPassword(!showPassword)}
                  title={showPassword ? 'Hide password' : 'Show password'}
                  disabled={loading}
                >
                  {showPassword ? '👁️‍🗨️' : '👁️'}
                </button>
              </div>
              {errors.password && <span className="error-text error-text-small">{errors.password}</span>}
            </div>

            {/* Confirm Password */}
            <div className="form-group">
              <label htmlFor="matchPwd">Confirm Password</label>
              <div className="input-wrapper">
                <span className="input-icon">🔐</span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  id="matchPwd"
                  name="matchPwd"
                  value={formData.matchPwd}
                  onChange={handleInputChange}
                  placeholder="Confirm password"
                  required
                  disabled={loading}
                  className={`form-input ${errors.matchPwd ? 'has-error' : ''}`}
                />
              </div>
              {errors.matchPwd && <span className="error-text">{errors.matchPwd}</span>}
            </div>

            </form>
          </div>

          {/* Button Section - Always Visible */}
          <div className="register-button-section">
            <button
              type="submit"
              form="register-form"
              disabled={loading}
              className="submit-button submit-button-register"
            >
              {loading ? (
                <>
                  <span className="spinner"></span>
                  Creating account...
                </>
              ) : (
                'Create Account'
              )}
            </button>

            {/* Login Link */}
            <p className="signup-link signup-link-register">
              Already have an account?{' '}
              <Link to="/login">Sign in here</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Register;
