import { useRef, useState, useEffect, FormEvent, ChangeEvent, FC } from 'react';
import useAuth from '../hooks/useAuth';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import axiosInstance from '../api/axios';
import './Auth.css';

const LOGIN_URL = '/auth/login';

interface LoginRequest {
  identifier: string;
  password: string;
}

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: {
    email: string;
    username: string;
    firstname?: string;
    lastname?: string;
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
  const [errMsg, setErrMsg] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);

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
      return;
    }

    setLoading(true);

    try {
      const payload: LoginRequest = {
        identifier,
        password
      };

      const response = await axiosInstance.post<LoginResponse>(LOGIN_URL, payload);

      console.log('Login successful:', response.data);

      const { access_token, refresh_token, user } = response.data;

      // Store tokens and user info in auth context
      setAuth({
        user: user.username,
        email: user.email,
        firstname: user.firstname,
        lastname: user.lastname,
        accessToken: access_token,
        refreshToken: refresh_token,
        tokenType: 'Bearer',
        isLoggedIn: true
      });

      // Store tokens in localStorage for persistence
      localStorage.setItem('accessToken', access_token);
      localStorage.setItem('refreshToken', refresh_token);
      localStorage.setItem('user', JSON.stringify(user));

      setIdentifier('');
      setPassword('');
      navigate(from, { replace: true });
    } catch (err: any) {
      if (!err?.response) {
        setErrMsg('No Server Response');
      } else if (err.response?.status === 400) {
        setErrMsg('Invalid username/email or password');
      } else if (err.response?.status === 401) {
        setErrMsg('Invalid credentials');
      } else if (err.response?.status === 403) {
        setErrMsg('Access Denied. You are not authorized to access this page.');
      } else {
        setErrMsg(
          err.response?.data?.detail || 
          'An error occurred while attempting to login. Please try again.'
        );
      }
      errRef.current?.focus();
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="auth-section">
      <p
        ref={errRef}
        className={errMsg ? 'errmsg' : 'offscreen'}
        aria-live="assertive"
      >
        {errMsg}
      </p>
      <h1>Sign In</h1>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="identifier">Username or Email:</label>
          <input
            type="text"
            id="identifier"
            ref={userRef}
            autoComplete="off"
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setIdentifier(e.target.value)
            }
            value={identifier}
            placeholder="Enter your username or email"
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="password">Password:</label>
          <input
            type="password"
            id="password"
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setPassword(e.target.value)
            }
            value={password}
            placeholder="Enter your password"
            required
            disabled={loading}
          />
        </div>

        <button type="submit" disabled={loading}>
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>

      <div className="auth-links">
        <p>
          Don't have an account?{' '}
          <Link to="/register">Create one</Link>
        </p>
      </div>
    </section>
  );
};

export default Login;
