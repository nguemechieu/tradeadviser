import { useRef, useState, useEffect, FormEvent, ChangeEvent, FC } from "react";
import { faCheck, faTimes } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import axiosInstance from '../api/axios';
import { Link } from "react-router-dom";
import './Auth.css';

const USER_REGEX = /^[A-Za-z][A-Za-z0-9_-]{3,23}$/;
const PWD_REGEX = /^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%]).{8,24}$/;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_REGEX = /^[\d\s\-\+\(\)]+$/;
const REGISTER_URL = '/api/auth/register';

interface RegisterResponse {
  access_token: string;
  refresh_token: string;
  user: {
    email: string;
    username: string;
    role: number;
  };
}

const Register: FC = () => {
  const userRef = useRef<HTMLInputElement>(null);
  const errRef = useRef<HTMLDivElement>(null);

  const [email, setEmail] = useState<string>('');
  const [validEmail, setValidEmail] = useState<boolean>(false);

  const [user, setUser] = useState<string>('');
  const [validName, setValidName] = useState<boolean>(false);
  const [userFocus, setUserFocus] = useState<boolean>(false);

  const [firstname, setFirstname] = useState<string>('');
  const [middlename, setMiddlename] = useState<string>('');
  const [lastname, setLastname] = useState<string>('');
  const [phone, setPhone] = useState<string>('');
  const [validPhone, setValidPhone] = useState<boolean>(true);

  const [pwd, setPwd] = useState<string>('');
  const [validPwd, setValidPwd] = useState<boolean>(false);
  const [pwdFocus, setPwdFocus] = useState<boolean>(false);

  const [matchPwd, setMatchPwd] = useState<string>('');
  const [validMatch, setValidMatch] = useState<boolean>(false);
  const [matchFocus, setMatchFocus] = useState<boolean>(false);

  const [errMsg, setErrMsg] = useState<string>('');
  const [success, setSuccess] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    userRef.current?.focus();
  }, []);

  useEffect(() => {
    setValidEmail(EMAIL_REGEX.test(email));
  }, [email]);

  useEffect(() => {
    setValidName(USER_REGEX.test(user));
  }, [user]);

  useEffect(() => {
    setValidPhone(phone === '' || PHONE_REGEX.test(phone));
  }, [phone]);

  useEffect(() => {
    setValidPwd(PWD_REGEX.test(pwd));
    setValidMatch(pwd === matchPwd);
  }, [pwd, matchPwd]);

  useEffect(() => {
    setErrMsg('');
  }, [user, pwd, matchPwd, email]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    const v1 = USER_REGEX.test(user);
    const v2 = PWD_REGEX.test(pwd);
    const v3 = EMAIL_REGEX.test(email);
    const v4 = phone === '' || PHONE_REGEX.test(phone);
    
    if (!v1 || !v2 || !v3 || !v4) {
      setErrMsg("Please meet all form requirements");
      return;
    }
    setLoading(true);
    try {
      const response = await axiosInstance.post<RegisterResponse>(REGISTER_URL,
        JSON.stringify({ 
          email,
          username: user,
          firstname,
          middlename,
          lastname,
          phone,
          password: pwd,
        }),
        {
          headers: { 'Content-Type': 'application/json' },
          withCredentials: true
        }
      );
      console.log(JSON.stringify(response?.data));
      setSuccess(true);
      setEmail('');
      setUser('');
      setFirstname('');
      setMiddlename('');
      setLastname('');
      setPhone('');
      setPwd('');
      setMatchPwd('');
    } catch (err) {
      const error = err as any;
      if (!error?.response) {
        setErrMsg('No Server Response');
      } else if (error.response?.status === 409) {
        setErrMsg('Username or email already taken');
      } else {
        setErrMsg(error.response?.data?.detail || 'Registration failed. Please try again.');
      }
      errRef.current?.focus();
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {success ? (
        <div className="auth-container">
          <div className="auth-wrapper">
            <div className="auth-card">
              <div className="auth-header">
                <h1>Account Created!</h1>
                <p>Your TradeAdviser account is ready</p>
              </div>
              <div className="success-message">
                <p>Thank you for registering. You can now sign in with your credentials.</p>
              </div>
              <Link to="/" className="auth-button">Sign In Now</Link>
            </div>
            <div className="auth-side">
              <div className="auth-side-content">
                <h2>Welcome Aboard</h2>
                <p>Start your journey towards smarter trading with intelligent AI-powered insights.</p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="auth-container">
          <div className="auth-wrapper">
            <div className="auth-card">
              <div className="auth-header">
                <h1>Create Account</h1>
                <p>Join TradeAdviser today</p>
              </div>

              {errMsg && (
                <div 
                  ref={errRef} 
                  className="auth-error" 
                  role="alert"
                  aria-live="assertive"
                >
                  {errMsg}
                </div>
              )}

              <form onSubmit={handleSubmit} className="auth-form">
                <div className="form-group">
                  <div className="label-wrapper">
                    <label htmlFor="email">Email</label>
                    <span className={validEmail ? "status valid" : email ? "status invalid" : ""}>
                      {validEmail && <FontAwesomeIcon icon={faCheck} />}
                      {email && !validEmail && <FontAwesomeIcon icon={faTimes} />}
                    </span>
                  </div>
                  <input
                    type="email"
                    id="email"
                    ref={userRef}
                    autoComplete="off"
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
                    value={email}
                    placeholder="Enter your email"
                    required
                    disabled={loading}
                    aria-invalid={validEmail ? "false" : "true"}
                  />
                </div>

                <div className="form-group">
                  <div className="label-wrapper">
                    <label htmlFor="username">Username</label>
                    <span className={validName ? "status valid" : user ? "status invalid" : ""}>
                      {validName && <FontAwesomeIcon icon={faCheck} />}
                      {user && !validName && <FontAwesomeIcon icon={faTimes} />}
                    </span>
                  </div>
                  <input
                    type="text"
                    id="username"
                    autoComplete="off"
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setUser(e.target.value)}
                    value={user}
                    placeholder="Enter a username"
                    required
                    disabled={loading}
                    aria-invalid={validName ? "false" : "true"}
                    aria-describedby="uidnote"
                    onFocus={() => setUserFocus(true)}
                    onBlur={() => setUserFocus(false)}
                  />
                  {userFocus && user && !validName && (
                    <p id="uidnote" className="requirement-note">
                      Username must be 4-24 characters, start with a letter, and contain only letters, numbers, underscores, or hyphens.
                    </p>
                  )}
                </div>

                <div className="form-row">
                  <div className="form-group">
                    <label htmlFor="firstname">First Name</label>
                    <input
                      type="text"
                      id="firstname"
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setFirstname(e.target.value)}
                      value={firstname}
                      placeholder="First name"
                      disabled={loading}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="middlename">Middle Name</label>
                    <input
                      type="text"
                      id="middlename"
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setMiddlename(e.target.value)}
                      value={middlename}
                      placeholder="Middle name"
                      disabled={loading}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="lastname">Last Name</label>
                    <input
                      type="text"
                      id="lastname"
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setLastname(e.target.value)}
                      value={lastname}
                      placeholder="Last name"
                      disabled={loading}
                    />
                  </div>
                </div>

                <div className="form-group">
                  <div className="label-wrapper">
                    <label htmlFor="phone">Phone</label>
                    <span className={phone && !validPhone ? "status invalid" : ""}>
                      {phone && !validPhone && <FontAwesomeIcon icon={faTimes} />}
                    </span>
                  </div>
                  <input
                    type="tel"
                    id="phone"
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setPhone(e.target.value)}
                    value={phone}
                    placeholder="(123) 456-7890"
                    disabled={loading}
                    aria-invalid={validPhone ? "false" : "true"}
                  />
                </div>

                <div className="form-group">
                  <div className="label-wrapper">
                    <label htmlFor="password">Password</label>
                    <span className={validPwd ? "status valid" : pwd ? "status invalid" : ""}>
                      {validPwd && <FontAwesomeIcon icon={faCheck} />}
                      {pwd && !validPwd && <FontAwesomeIcon icon={faTimes} />}
                    </span>
                  </div>
                  <input
                    type="password"
                    id="password"
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setPwd(e.target.value)}
                    value={pwd}
                    placeholder="Enter a password"
                    required
                    disabled={loading}
                    aria-invalid={validPwd ? "false" : "true"}
                    aria-describedby="pwdnote"
                    onFocus={() => setPwdFocus(true)}
                    onBlur={() => setPwdFocus(false)}
                  />
                  {pwdFocus && pwd && (
                    <div id="pwdnote" className="requirement-checklist">
                      <div className={pwd.length >= 8 && pwd.length <= 24 ? "req met" : "req"}>
                        <span>✓</span> 8-24 characters
                      </div>
                      <div className={/[a-z]/.test(pwd) ? "req met" : "req"}>
                        <span>✓</span> Lowercase letter
                      </div>
                      <div className={/[A-Z]/.test(pwd) ? "req met" : "req"}>
                        <span>✓</span> Uppercase letter
                      </div>
                      <div className={/[0-9]/.test(pwd) ? "req met" : "req"}>
                        <span>✓</span> Number
                      </div>
                      <div className={/[!@#$%]/.test(pwd) ? "req met" : "req"}>
                        <span>✓</span> Special char (! @ # $ %)
                      </div>
                    </div>
                  )}
                </div>

                <div className="form-group">
                  <div className="label-wrapper">
                    <label htmlFor="confirm_pwd">Confirm Password</label>
                    <span className={validMatch && matchPwd ? "status valid" : matchPwd ? "status invalid" : ""}>
                      {validMatch && matchPwd && <FontAwesomeIcon icon={faCheck} />}
                      {matchPwd && !validMatch && <FontAwesomeIcon icon={faTimes} />}
                    </span>
                  </div>
                  <input
                    type="password"
                    id="confirm_pwd"
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setMatchPwd(e.target.value)}
                    value={matchPwd}
                    placeholder="Confirm password"
                    required
                    disabled={loading}
                    aria-invalid={validMatch ? "false" : "true"}
                    aria-describedby="confirmnote"
                    onFocus={() => setMatchFocus(true)}
                    onBlur={() => setMatchFocus(false)}
                  />
                  {matchFocus && !validMatch && matchPwd && (
                    <p id="confirmnote" className="requirement-note">
                      Passwords do not match
                    </p>
                  )}
                </div>

                <button 
                  type="submit" 
                  className="auth-button"
                  disabled={!validName || !validPwd || !validMatch || !validEmail || !validPhone || loading}
                >
                  {loading ? 'Creating Account...' : 'Create Account'}
                </button>
              </form>

              <div className="auth-footer">
                <p>Already have an account? <Link to="/">Sign In</Link></p>
              </div>
            </div>

            <div className="auth-side">
              <div className="auth-side-content">
                <h2>Trade with Confidence</h2>
                <p>Get AI-powered trading recommendations, real-time market analysis, and portfolio insights.</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default Register;
