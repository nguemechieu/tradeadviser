import { useRef, useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import axiosInstance from '../api/axiosConfig';
import logo from '../assets/logo.png';
import '../app.css';

const LOGIN_URL = '/auth/login';

const Login = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const from = location.state?.from?.pathname || "/home";

    const emailRef = useRef();

    const [email, setEmail] = useState('');
    const [pwd, setPwd] = useState('');
    const [errMsg, setErrMsg] = useState('');
    const [loading, setLoading] = useState(false);
    const [rememberMe, setRememberMe] = useState(false);

    useEffect(() => {
        emailRef.current?.focus();
    }, []);

    useEffect(() => {
        setErrMsg('');
    }, [email, pwd]);

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!email || !pwd) {
            setErrMsg('Please enter both email and password.');
            return;
        }

        try {
            setLoading(true);
            const response = await axiosInstance.post(LOGIN_URL, {
                identifier: email,
                password: pwd,
                remember_me: rememberMe
            });

            const { access_token, token_type } = response.data;
            
            // Store token
            localStorage.setItem('tradeadviser-token', access_token);
            
            if (rememberMe) {
                localStorage.setItem('remember-email', email);
            } else {
                localStorage.removeItem('remember-email');
            }

            setEmail('');
            setPwd('');
            navigate(from, { replace: true });
        } catch (err) {
            if (!err?.response) {
                setErrMsg('No server response. Please try again.');
            } else if (err.response?.status === 401) {
                setErrMsg('Invalid email or password.');
            } else if (err.response?.status === 400) {
                setErrMsg('Invalid login credentials.');
            } else {
                setErrMsg('Login failed. Please try again.');
            }
            emailRef.current?.focus();
        } finally {
            setLoading(false);
        }
    };

    return (
        <section className="auth-page" style={{ 
            display: 'flex', 
            justifyContent: 'center', 
            alignItems: 'center',
            minHeight: '100vh',
            padding: '2rem 1rem'
        }}>
            <div className="card" style={{ maxWidth: '450px', width: '100%' }}>
                {/* Header */}
                <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                    <img src={logo} alt="TradeAdviser" style={{ height: '60px', marginBottom: '1rem' }} />
                    <h1 style={{ fontSize: '1.8rem' }}>Sign In</h1>
                    <p style={{ color: '#8ea3bc' }}>Welcome back to TradeAdviser</p>
                </div>

                {/* Error Message */}
                {errMsg && (
                    <div className="error-message" style={{ marginBottom: '1rem' }}>
                        {errMsg}
                    </div>
                )}

                {/* Login Form */}
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                    {/* Email Field */}
                    <div className="form-field">
                        <label htmlFor="email">Email Address</label>
                        <input
                            type="email"
                            id="email"
                            ref={emailRef}
                            autoComplete="email"
                            onChange={(e) => setEmail(e.target.value)}
                            value={email}
                            placeholder="you@example.com"
                            required
                            className="input-field"
                        />
                    </div>

                    {/* Password Field */}
                    <div className="form-field">
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                            <label htmlFor="password">Password</label>
                            <Link to="/forgot-password" style={{ fontSize: '0.85rem' }}>
                                Forgot password?
                            </Link>
                        </div>
                        <input
                            type="password"
                            id="password"
                            onChange={(e) => setPwd(e.target.value)}
                            value={pwd}
                            placeholder="••••••••"
                            required
                            className="input-field"
                        />
                    </div>

                    {/* Remember Me */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <input
                            type="checkbox"
                            id="remember"
                            checked={rememberMe}
                            onChange={(e) => setRememberMe(e.target.checked)}
                            style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                        />
                        <label htmlFor="remember" style={{ color: '#8ea3bc', cursor: 'pointer', marginBottom: 0 }}>
                            Remember me
                        </label>
                    </div>

                    {/* Submit Button */}
                    <button 
                        type="submit" 
                        disabled={loading}
                        className="btn btn-primary"
                        style={{ width: '100%', padding: '0.875rem', fontSize: '1rem', fontWeight: '600' }}
                    >
                        {loading ? 'Signing in...' : 'Sign In'}
                    </button>
                </form>

                {/* Divider */}
                <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '1rem', 
                    margin: '2rem 0',
                    opacity: 0.5
                }}>
                    <div style={{ flex: 1, height: '1px', backgroundColor: 'rgba(136, 168, 203, 0.3)' }}></div>
                    <span style={{ color: '#8ea3bc', fontSize: '0.9rem' }}>OR</span>
                    <div style={{ flex: 1, height: '1px', backgroundColor: 'rgba(136, 168, 203, 0.3)' }}></div>
                </div>

                {/* Quick Links */}
                <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: '1fr 1fr', 
                    gap: '1rem',
                    marginBottom: '2rem'
                }}>
                    <Link to="/tradeadviser" className="btn btn-secondary" style={{ textAlign: 'center', textDecoration: 'none' }}>
                        View Prices
                    </Link>
                    <Link to="/demo" className="btn btn-secondary" style={{ textAlign: 'center', textDecoration: 'none' }}>
                        Try Demo
                    </Link>
                </div>

                {/* Sign Up Link */}
                <div style={{ 
                    textAlign: 'center', 
                    paddingTop: '2rem', 
                    borderTop: '1px solid rgba(136, 168, 203, 0.2)' 
                }}>
                    <p style={{ color: '#8ea3bc', marginBottom: '0.5rem' }}>
                        Don't have an account?
                    </p>
                    <Link to="/register" style={{ 
                        color: '#53b4ff', 
                        fontWeight: '600',
                        fontSize: '1.05rem'
                    }}>
                        Create one now
                    </Link>
                </div>

                {/* Footer */}
                <div style={{ 
                    textAlign: 'center', 
                    marginTop: '2rem', 
                    paddingTop: '1rem',
                    borderTop: '1px solid rgba(136, 168, 203, 0.1)',
                    fontSize: '0.85rem',
                    color: '#8ea3bc'
                }}>
                    <p>By signing in, you agree to our Terms of Service and Privacy Policy</p>
                    <p style={{ marginTop: '1rem', opacity: 0.7 }}>© 2026 TradeAdviser. All rights reserved.</p>
                </div>
            </div>
        </section>
    );
};

export default Login;
