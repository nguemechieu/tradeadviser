import { useRef, useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import axiosInstance from '../api/axiosConfig';
import logo from '../assets/logo.png';
import '../app.css';

const USER_REGEX = /^[A-z][A-z0-9-_]{3,23}$/;
const PWD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%]).{8,24}$/;
const REGISTER_URL = '/auth/register';

const Register = () => {
    const userRef = useRef();
    const navigate = useNavigate();

    const [email, setEmail] = useState('');
    const [validEmail, setValidEmail] = useState(false);

    const [username, setUsername] = useState('');
    const [validUsername, setValidUsername] = useState(false);

    const [firstName, setFirstName] = useState('');
    const [lastName, setLastName] = useState('');
    const [middleName, setMiddleName] = useState('');
    const [phoneNumber, setPhoneNumber] = useState('');

    const [pwd, setPwd] = useState('');
    const [validPwd, setValidPwd] = useState(false);
    const [pwdFocus, setPwdFocus] = useState(false);

    const [matchPwd, setMatchPwd] = useState('');
    const [validMatch, setValidMatch] = useState(false);
    const [matchFocus, setMatchFocus] = useState(false);

    const [errMsg, setErrMsg] = useState('');
    const [loading, setLoading] = useState(false);
    const [success, setSuccess] = useState(false);

    useEffect(() => {
        userRef.current?.focus();
    }, []);

    useEffect(() => {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        setValidEmail(emailRegex.test(email));
    }, [email]);

    useEffect(() => {
        setValidUsername(USER_REGEX.test(username));
    }, [username]);

    useEffect(() => {
        setValidPwd(PWD_REGEX.test(pwd));
        setValidMatch(pwd === matchPwd);
    }, [pwd, matchPwd]);

    useEffect(() => {
        setErrMsg('');
    }, [email, username, firstName, lastName, pwd, matchPwd]);

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!validEmail || !validUsername || !firstName || !lastName || !validPwd || !validMatch) {
            setErrMsg("Invalid entry. Please check all required fields.");
            return;
        }

        try {
            setLoading(true);
            await axiosInstance.post(REGISTER_URL, {
                email,
                username,
                first_name: firstName,
                last_name: lastName,
                middle_name: middleName || null,
                phone_number: phoneNumber || null,
                password: pwd
            });

            setSuccess(true);
            setEmail('');
            setUsername('');
            setFirstName('');
            setLastName('');
            setMiddleName('');
            setPhoneNumber('');
            setPwd('');
            setMatchPwd('');
            
            setTimeout(() => {
                navigate('/login');
            }, 2000);
        } catch (err) {
            if (!err?.response) {
                setErrMsg('No server response. Please try again.');
            } else if (err.response?.status === 409) {
                setErrMsg('Email or username already registered.');
            } else if (err.response?.status === 400) {
                setErrMsg(err.response?.data?.detail || 'Invalid registration data.');
            } else {
                setErrMsg('Registration failed. Please try again.');
            }
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
            {success ? (
                <div className="card" style={{ textAlign: 'center', maxWidth: '500px' }}>
                    <div style={{ marginBottom: '2rem' }}>
                        <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✓</div>
                        <h1>Welcome to TradeAdviser!</h1>
                        <p style={{ color: '#8ea3bc' }}>Your account has been created successfully.</p>
                        <p style={{ color: '#78e6c8', marginTop: '1rem' }}>Redirecting to login...</p>
                    </div>
                </div>
            ) : (
                <div className="card" style={{ maxWidth: '500px', width: '100%' }}>
                    {/* Header */}
                    <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
                        <img src={logo} alt="TradeAdviser" style={{ height: '60px', marginBottom: '1rem' }} />
                        <h1 style={{ fontSize: '1.8rem' }}>Create Account</h1>
                        <p style={{ color: '#8ea3bc' }}>Join TradeAdviser today</p>
                    </div>

                    {/* Error Message */}
                    {errMsg && (
                        <div className="error-message" style={{ marginBottom: '1rem' }}>
                            {errMsg}
                        </div>
                    )}

                    {/* Registration Form */}
                    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        {/* Email Field */}
                        <div className="form-field">
                            <label htmlFor="email" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span>Email Address *</span>
                                {email && <span style={{ fontSize: '0.9rem', color: validEmail ? '#67e2a3' : '#ff7d8d' }}>
                                    {validEmail ? '✓' : '✗'}
                                </span>}
                            </label>
                            <input
                                type="email"
                                id="email"
                                ref={userRef}
                                autoComplete="email"
                                onChange={(e) => setEmail(e.target.value)}
                                value={email}
                                placeholder="you@example.com"
                                required
                                className="input-field"
                            />
                            {email && !validEmail && (
                                <p style={{ fontSize: '0.85rem', color: '#ff7d8d', marginTop: '0.5rem' }}>
                                    Please enter a valid email address.
                                </p>
                            )}
                        </div>

                        {/* Username Field */}
                        <div className="form-field">
                            <label htmlFor="username" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span>Username *</span>
                                {username && <span style={{ fontSize: '0.9rem', color: validUsername ? '#67e2a3' : '#ff7d8d' }}>
                                    {validUsername ? '✓' : '✗'}
                                </span>}
                            </label>
                            <input
                                type="text"
                                id="username"
                                autoComplete="username"
                                onChange={(e) => setUsername(e.target.value)}
                                value={username}
                                placeholder="4-24 characters (letters, numbers, -, _)"
                                required
                                className="input-field"
                            />
                            {username && !validUsername && (
                                <p style={{ fontSize: '0.85rem', color: '#ff7d8d', marginTop: '0.5rem' }}>
                                    Username must be 4-24 characters and start with a letter.
                                </p>
                            )}
                        </div>

                        {/* Name Fields Row */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                            {/* First Name Field */}
                            <div className="form-field">
                                <label htmlFor="firstName">
                                    <span>First Name *</span>
                                </label>
                                <input
                                    type="text"
                                    id="firstName"
                                    autoComplete="given-name"
                                    onChange={(e) => setFirstName(e.target.value)}
                                    value={firstName}
                                    placeholder="John"
                                    required
                                    className="input-field"
                                />
                            </div>

                            {/* Last Name Field */}
                            <div className="form-field">
                                <label htmlFor="lastName">
                                    <span>Last Name *</span>
                                </label>
                                <input
                                    type="text"
                                    id="lastName"
                                    autoComplete="family-name"
                                    onChange={(e) => setLastName(e.target.value)}
                                    value={lastName}
                                    placeholder="Doe"
                                    required
                                    className="input-field"
                                />
                            </div>
                        </div>

                        {/* Middle Name & Phone Number Row */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                            {/* Middle Name Field (Optional) */}
                            <div className="form-field">
                                <label htmlFor="middleName">
                                    <span>Middle Name</span>
                                </label>
                                <input
                                    type="text"
                                    id="middleName"
                                    autoComplete="additional-name"
                                    onChange={(e) => setMiddleName(e.target.value)}
                                    value={middleName}
                                    placeholder="(Optional)"
                                    className="input-field"
                                />
                            </div>

                            {/* Phone Number Field (Optional) */}
                            <div className="form-field">
                                <label htmlFor="phoneNumber">
                                    <span>Phone Number</span>
                                </label>
                                <input
                                    type="tel"
                                    id="phoneNumber"
                                    autoComplete="tel"
                                    onChange={(e) => setPhoneNumber(e.target.value)}
                                    value={phoneNumber}
                                    placeholder="(Optional)"
                                    className="input-field"
                                />
                            </div>
                        </div>

                        {/* Password Field */}
                        <div className="form-field">
                            <label htmlFor="password" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span>Password *</span>
                                {pwd && <span style={{ fontSize: '0.9rem', color: validPwd ? '#67e2a3' : '#ff7d8d' }}>
                                    {validPwd ? '✓' : '✗'}
                                </span>}
                            </label>
                            <input
                                type="password"
                                id="password"
                                onChange={(e) => setPwd(e.target.value)}
                                value={pwd}
                                placeholder="••••••••"
                                required
                                className="input-field"
                                onFocus={() => setPwdFocus(true)}
                                onBlur={() => setPwdFocus(false)}
                            />
                            {pwdFocus && pwd && !validPwd && (
                                <div style={{ fontSize: '0.85rem', color: '#f7b666', marginTop: '0.5rem', padding: '0.75rem', backgroundColor: 'rgba(247, 182, 102, 0.1)', borderRadius: '4px' }}>
                                    <p>Password must contain:</p>
                                    <ul style={{ marginLeft: '1rem', marginTop: '0.5rem' }}>
                                        <li>✓ Uppercase letter</li>
                                        <li>✓ Lowercase letter</li>
                                        <li>✓ Number</li>
                                        <li>✓ Special character (!@#$%)</li>
                                        <li>✓ 8-24 characters total</li>
                                    </ul>
                                </div>
                            )}
                        </div>

                        {/* Confirm Password Field */}
                        <div className="form-field">
                            <label htmlFor="confirm_pwd" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span>Confirm Password *</span>
                                {matchPwd && <span style={{ fontSize: '0.9rem', color: validMatch ? '#67e2a3' : '#ff7d8d' }}>
                                    {validMatch ? '✓' : '✗'}
                                </span>}
                            </label>
                            <input
                                type="password"
                                id="confirm_pwd"
                                onChange={(e) => setMatchPwd(e.target.value)}
                                value={matchPwd}
                                placeholder="••••••••"
                                required
                                className="input-field"
                                onFocus={() => setMatchFocus(true)}
                                onBlur={() => setMatchFocus(false)}
                            />
                            {matchFocus && matchPwd && !validMatch && (
                                <p style={{ fontSize: '0.85rem', color: '#ff7d8d', marginTop: '0.5rem' }}>
                                    Passwords do not match.
                                </p>
                            )}
                        </div>

                        {/* Submit Button */}
                        <button 
                            type="submit" 
                            disabled={!validEmail || !validUsername || !firstName || !lastName || !validPwd || !validMatch || loading}
                            className="btn btn-primary"
                            style={{ width: '100%', padding: '0.875rem' }}
                        >
                            {loading ? 'Creating account...' : 'Create Account'}
                        </button>
                    </form>

                    {/* Login Link */}
                    <div style={{ textAlign: 'center', marginTop: '2rem', paddingTop: '2rem', borderTop: '1px solid rgba(136, 168, 203, 0.2)' }}>
                        <p style={{ color: '#8ea3bc' }}>
                            Already have an account?{' '}
                            <Link to="/login" style={{ color: '#53b4ff', fontWeight: '600' }}>
                                Sign In
                            </Link>
                        </p>
                        <p style={{ color: '#8ea3bc', marginTop: '1rem', fontSize: '0.85rem', opacity: 0.7 }}>
                            © 2026 TradeAdviser. All rights reserved.
                        </p>
                    </div>
                </div>
            )}
        </section>
    );
};

export default Register;
