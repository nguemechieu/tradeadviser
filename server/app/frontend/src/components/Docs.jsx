import { useContext } from 'react';
import { Link } from 'react-router-dom';
import AuthContext from '../context/AuthProvider';

const Docs = () => {
    const { auth } = useContext(AuthContext);

    return (
        <section className="docs-page" style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
            <div style={{ marginBottom: '3rem' }}>
                <h1 style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>Documentation</h1>
                <p style={{ fontSize: '1.1rem', color: '#8ea3bc' }}>
                    Welcome to TradeAdviser documentation. Here you'll find guides and resources to help you get started.
                </p>
            </div>

            {/* Documentation Sections */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem', marginBottom: '3rem' }}>
                
                {/* Getting Started */}
                <div className="card" style={{ padding: '2rem' }}>
                    <h2 style={{ marginTop: 0 }}>Getting Started</h2>
                    <p>Learn the basics of TradeAdviser and how to set up your account.</p>
                    <ul style={{ textAlign: 'left', marginLeft: '1rem' }}>
                        <li>Account setup and registration</li>
                        <li>Profile configuration</li>
                        <li>Initial settings</li>
                    </ul>
                    <a href="#getting-started" style={{ color: '#53b4ff', fontWeight: '600' }}>Read more →</a>
                </div>

                {/* Trading Guide */}
                <div className="card" style={{ padding: '2rem' }}>
                    <h2 style={{ marginTop: 0 }}>Trading Guide</h2>
                    <p>Master the trading features and execute trades effectively.</p>
                    <ul style={{ textAlign: 'left', marginLeft: '1rem' }}>
                        <li>Placing trades</li>
                        <li>Portfolio management</li>
                        <li>Risk management</li>
                    </ul>
                    <a href="#trading-guide" style={{ color: '#53b4ff', fontWeight: '600' }}>Read more →</a>
                </div>

                {/* API Reference */}
                <div className="card" style={{ padding: '2rem' }}>
                    <h2 style={{ marginTop: 0 }}>API Reference</h2>
                    <p>Complete API documentation for developers and integrations.</p>
                    <ul style={{ textAlign: 'left', marginLeft: '1rem' }}>
                        <li>Authentication endpoints</li>
                        <li>Trading operations</li>
                        <li>Data queries</li>
                    </ul>
                    <a href="#api-reference" style={{ color: '#53b4ff', fontWeight: '600' }}>Read more →</a>
                </div>

                {/* Analytics */}
                <div className="card" style={{ padding: '2rem' }}>
                    <h2 style={{ marginTop: 0 }}>Analytics & Reporting</h2>
                    <p>Understand your trading performance with detailed analytics.</p>
                    <ul style={{ textAlign: 'left', marginLeft: '1rem' }}>
                        <li>Performance metrics</li>
                        <li>Profit/loss reports</li>
                        <li>Historical analysis</li>
                    </ul>
                    <a href="#analytics" style={{ color: '#53b4ff', fontWeight: '600' }}>Read more →</a>
                </div>

                {/* Community */}
                <div className="card" style={{ padding: '2rem' }}>
                    <h2 style={{ marginTop: 0 }}>Community & Support</h2>
                    <p>Connect with other traders and get support.</p>
                    <ul style={{ textAlign: 'left', marginLeft: '1rem' }}>
                        <li>Community forums</li>
                        <li>Help and support</li>
                        <li>FAQ</li>
                    </ul>
                    <a href="#community" style={{ color: '#53b4ff', fontWeight: '600' }}>Read more →</a>
                </div>

                {/* Advanced Features */}
                <div className="card" style={{ padding: '2rem' }}>
                    <h2 style={{ marginTop: 0 }}>Advanced Features</h2>
                    <p>Explore advanced trading strategies and tools.</p>
                    <ul style={{ textAlign: 'left', marginLeft: '1rem' }}>
                        <li>Strategy builder</li>
                        <li>Backtesting</li>
                        <li>Automation</li>
                    </ul>
                    <a href="#advanced" style={{ color: '#53b4ff', fontWeight: '600' }}>Read more →</a>
                </div>
            </div>

            {/* Quick Links */}
            <div style={{ 
                backgroundColor: 'rgba(83, 180, 255, 0.1)',
                padding: '2rem',
                borderRadius: '8px',
                marginBottom: '3rem'
            }}>
                <h3>Quick Start Links</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                    {auth?.user && (
                        <>
                            <Link to="/home" className="btn btn-primary" style={{ textDecoration: 'none', textAlign: 'center' }}>
                                Go to Home
                            </Link>
                            <Link to="/trading" className="btn btn-primary" style={{ textDecoration: 'none', textAlign: 'center' }}>
                                Start Trading
                            </Link>
                            <Link to="/dashboard" className="btn btn-primary" style={{ textDecoration: 'none', textAlign: 'center' }}>
                                View Dashboard
                            </Link>
                        </>
                    )}
                    {!auth?.user && (
                        <>
                            <Link to="/login" className="btn btn-primary" style={{ textDecoration: 'none', textAlign: 'center' }}>
                                Sign In
                            </Link>
                            <Link to="/register" className="btn btn-primary" style={{ textDecoration: 'none', textAlign: 'center' }}>
                                Create Account
                            </Link>
                        </>
                    )}
                </div>
            </div>

            {/* Detailed Sections */}
            <div style={{ marginTop: '3rem' }}>
                <h2 id="getting-started">Getting Started with TradeAdviser</h2>
                <p>
                    TradeAdviser is a comprehensive trading platform that provides real-time trading signals,
                    advanced portfolio analytics, and risk management tools. To get started:
                </p>
                <ol style={{ textAlign: 'left', paddingLeft: '2rem' }}>
                    <li>Create an account and verify your email</li>
                    <li>Complete your profile with personal information</li>
                    <li>Set up your trading preferences</li>
                    <li>Connect your broker account (if available)</li>
                    <li>Start trading with confidence</li>
                </ol>

                <h2 id="trading-guide" style={{ marginTop: '2rem' }}>Trading Guide</h2>
                <p>
                    The trading interface provides an intuitive way to manage your positions and strategies.
                    You can place trades, monitor your portfolio, and execute trades directly from the platform.
                </p>

                <h2 id="api-reference" style={{ marginTop: '2rem' }}>API Reference</h2>
                <p>
                    TradeAdviser provides a comprehensive REST API for developers and integrations.
                    All API endpoints are secured with token-based authentication.
                </p>

                <h2 id="community" style={{ marginTop: '2rem' }}>Community Support</h2>
                <p>
                    Join our community to connect with other traders, share strategies, and get support
                    from experienced members and our support team.
                </p>
            </div>

            {/* Footer Info */}
            <div style={{ 
                marginTop: '3rem',
                paddingTop: '2rem',
                borderTop: '1px solid rgba(136, 168, 203, 0.2)',
                textAlign: 'center',
                color: '#8ea3bc'
            }}>
                <p>Need more help? Check our <a href="#faq" style={{ color: '#53b4ff' }}>FAQ</a> or contact support.</p>
                <p style={{ fontSize: '0.9rem', marginTop: '1rem' }}>
                    © 2026 TradeAdviser. All rights reserved.
                </p>
            </div>
        </section>
    );
};

export default Docs;
