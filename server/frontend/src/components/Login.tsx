import { useRef, useState, useEffect, FormEvent, ChangeEvent, FC } from 'react';
import useAuth from '../hooks/useAuth';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import axiosInstance from '../api/axios';
import './Auth.css';

const LOGIN_URL = '/api/auth/login';

interface LoginRequest {
  identifier: string;
  password: string;
  remember_me?: boolean;
}

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id?: string;
    email: string;
    username: string;
    display_name?: string;
    firstname?: string;
    lastname?: string;
    role: string;
  };
}

const Login: FC = () => {
  const { setAuth } = useAuth();

  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as any)?.from?.pathname || '/';

  const userRef = useRef<HTMLInputElement>(null);
  const errRef = useRef<HTMLDivElement>(null);

  const [identifier, setIdentifier] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [rememberMe, setRememberMe] = useState<boolean>(false);
  const [errMsg, setErrMsg] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [showPassword, setShowPassword] = useState<boolean>(false);

  useEffect(() => {
    userRef.current?.focus();
  }, []);

  useEffect(() => {
    setErrMsg('');
  }, [identifier, password]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!identifier || !password) {
      setErrMsg('Please enter both username/email and password');
      errRef.current?.focus();
      return;
    }

    if (password.length < 6) {
      setErrMsg('Password must be at least 6 characters');
      errRef.current?.focus();
      return;
    }

    setLoading(true);

    try {
      const payload: LoginRequest = {
        identifier,
        password,
        remember_me: rememberMe
      };

      const response = await axiosInstance.post<LoginResponse>(LOGIN_URL, payload);

      const { access_token, refresh_token, user } = response.data;

      // Store tokens and user info in auth context
      setAuth({
        user: user.username,
        email: user.email,
        id: user.id,
        display_name: user.display_name,
        firstname: user.firstname,
        lastname: user.lastname,
        role: user.role,
        accessToken: access_token,
        refreshToken: refresh_token,
        tokenType: 'Bearer',
        isLoggedIn: true
      });

      // Store tokens in localStorage for persistence
      localStorage.setItem('accessToken', access_token);
      localStorage.setItem('refreshToken', refresh_token);
      localStorage.setItem('user', JSON.stringify(user));
      localStorage.setItem('rememberMe', rememberMe.toString());

      setIdentifier('');
      setPassword('');
      setRememberMe(false);
      navigate(from, { replace: true });
    } catch (err: any) {
      let errorMessage = 'An error occurred while attempting to login. Please try again.';
      
      if (!err?.response) {
        errorMessage = 'No Server Response';
      } else if (err.response?.status === 400) {
        errorMessage = 'Invalid username/email or password';
      } else if (err.response?.status === 401) {
        errorMessage = 'Invalid credentials';
      } else if (err.response?.status === 403) {
        errorMessage = 'Access Denied. You are not authorized to access this page.';
      } else {
        errorMessage = err.response?.data?.detail || errorMessage;
      }
      
      setErrMsg(errorMessage);
      errRef.current?.focus();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-wrapper">
        {/* Left side - Branding */}
        <div className="auth-branding">
          <div className="branding-content">
            <h2>TradeAdviser</h2>
            <p>Professional Trading Platform</p>
            <ul className="features">
              <li>✓ Real-time trading signals</li>
              <li>✓ Advanced risk management</li>
              <li>✓ Multi-broker support</li>
              <li>✓ AI-powered analysis</li>
            </ul>
          </div>
        </div>

        {/* Right side - Login Form */}
        <div className="auth-card">
          <div className="auth-header">
            <h1>Welcome Back</h1>
            <p>Sign in to your account to continue</p>
          </div>

          {errMsg && (
            <div
              ref={errRef}
              className="auth-error"
              role="alert"
              aria-live="assertive"
            >
              <span className="error-icon">⚠️</span>
              <span>{errMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="auth-form">
            {/* Username/Email Field */}
            <div className="form-group">
              <label htmlFor="identifier">Username or Email</label>
              <div className="input-wrapper">
                <span className="input-icon">👤</span>
                <input
                  type="text"
                  id="identifier"
                  ref={userRef}
                  autoComplete="off"
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setIdentifier(e.target.value)
                  }
                  value={identifier}
                  placeholder="Enter username or email"
                  required
                  disabled={loading}
                  className="form-input"
                />
              </div>
            </div>

            {/* Password Field */}
            <div className="form-group">
              <label htmlFor="password">Password</label>
              <div className="input-wrapper">
                <span className="input-icon">🔐</span>
                <input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setPassword(e.target.value)
                  }
                  value={password}
                  placeholder="Enter your password"
                  required
                  disabled={loading}
                  className="form-input"
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
            </div>

            {/* Remember Me & Forgot Password */}
            <div className="form-options">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setRememberMe(e.target.checked)
                  }
                  disabled={loading}
                />
                <span>Remember me for 30 days</span>
              </label>
              <Link to="/forgot-password" className="forgot-password-link">
                Forgot password?
              </Link>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={loading}
              className="submit-button"
            >
              {loading ? (
                <>
                  <span className="spinner"></span>
                  Signing in...
                </>
              ) : (
                'Sign In'
              )}
            </button>

            {/* Sign Up Link */}
            <p className="signup-link">
              Don't have an account?{' '}
              <Link to="/register">Create one now</Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Login;
