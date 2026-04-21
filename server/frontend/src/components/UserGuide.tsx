import './UserGuide.css';

const UserGuide = () => {
  return (
    <div className="user-guide">
      <div className="guide-header">
        <h1>TradeAdviser User Guide</h1>
        <p>Complete guide to using the TradeAdviser platform</p>
      </div>

      <div className="guide-container">
        {/* Getting Started */}
        <section className="guide-section">
          <h2 className="section-title">🚀 Getting Started</h2>
          
          <div className="subsection">
            <h3>Creating Your Account</h3>
            <ol className="guide-list">
              <li>Navigate to the Registration page</li>
              <li>Enter your email address and create a secure password</li>
              <li>Optionally add your username and display name</li>
              <li>Click "Register" to create your account</li>
              <li>You can now log in with your credentials</li>
            </ol>
          </div>

          <div className="subsection">
            <h3>Logging In</h3>
            <ol className="guide-list">
              <li>Go to the Login page</li>
              <li>Enter your email or username</li>
              <li>Enter your password</li>
              <li>Check "Remember Me" to stay logged in (optional)</li>
              <li>Click "Sign In"</li>
            </ol>
          </div>
        </section>

        {/* Dashboard Overview */}
        <section className="guide-section">
          <h2 className="section-title">📊 Dashboard Overview</h2>
          
          <div className="subsection">
            <h3>Your Personal Dashboard</h3>
            <p>
              The dashboard is your home page that shows all the modules and features you have access to
              based on your user role. Key elements include:
            </p>
            <ul className="guide-list">
              <li><strong>Quick Stats:</strong> Shows your accessible modules, role, and status</li>
              <li><strong>Module Cards:</strong> Access different features and tools</li>
              <li><strong>Quick Links:</strong> Shortcuts to documentation and community</li>
              <li><strong>Features Overview:</strong> Summary of platform capabilities</li>
            </ul>
          </div>

          <div className="subsection">
            <h3>Navigation Menu</h3>
            <p>The top navigation bar provides quick access to:</p>
            <ul className="guide-list">
              <li><strong>Dashboard:</strong> Main home page</li>
              <li><strong>Trading Tools:</strong> Trading Editor, Community</li>
              <li><strong>Admin Panel:</strong> Administrative functions (if authorized)</li>
              <li><strong>Documentation:</strong> API and user guides</li>
            </ul>
          </div>
        </section>

        {/* User Roles */}
        <section className="guide-section">
          <h2 className="section-title">👥 User Roles & Permissions</h2>
          
          <div className="role-card">
            <h3>📈 Trader</h3>
            <p>Standard trading user with access to:</p>
            <ul className="guide-list">
              <li>Portfolio management and monitoring</li>
              <li>Trading strategy editor</li>
              <li>Community forums and discussions</li>
              <li>Personal trading signals</li>
            </ul>
          </div>

          <div className="role-card">
            <h3>⚠️ Risk Manager</h3>
            <p>Risk management specialist with access to:</p>
            <ul className="guide-list">
              <li>Portfolio risk monitoring and analysis</li>
              <li>Risk limit configuration and enforcement</li>
              <li>Breach detection and alerts</li>
              <li>Risk reporting and auditing</li>
            </ul>
          </div>

          <div className="role-card">
            <h3>🔧 Operations</h3>
            <p>System operations team with access to:</p>
            <ul className="guide-list">
              <li>System health monitoring</li>
              <li>Broker connectivity status</li>
              <li>Active connections management</li>
              <li>Deployment status tracking</li>
            </ul>
          </div>

          <div className="role-card">
            <h3>🛡️ Admin</h3>
            <p>Administrator with full access to:</p>
            <ul className="guide-list">
              <li>All operations features</li>
              <li>Risk management tools</li>
              <li>User and license management</li>
              <li>AI Agent deployment</li>
              <li>Performance auditing</li>
            </ul>
          </div>

          <div className="role-card">
            <h3>👑 Super Admin</h3>
            <p>Complete system access with highest privileges:</p>
            <ul className="guide-list">
              <li>All admin features</li>
              <li>System configuration</li>
              <li>Complete audit trail access</li>
              <li>User role management</li>
            </ul>
          </div>
        </section>

        {/* Feature Guides */}
        <section className="guide-section">
          <h2 className="section-title">✨ Feature Guides</h2>
          
          <div className="subsection">
            <h3>Trading Editor</h3>
            <p>Create and manage your trading strategies:</p>
            <ol className="guide-list">
              <li>Go to Trading Editor from the main menu</li>
              <li>Click "New Strategy" to create a strategy</li>
              <li>Define your strategy parameters and rules</li>
              <li>Test your strategy with historical data</li>
              <li>Deploy your strategy when ready</li>
            </ol>
          </div>

          <div className="subsection">
            <h3>Community</h3>
            <p>Connect with other traders and share insights:</p>
            <ul className="guide-list">
              <li>View discussions and posts from other traders</li>
              <li>Create new discussion threads</li>
              <li>Share your trading strategies and results</li>
              <li>Ask questions and get community support</li>
              <li>Follow traders and strategies you're interested in</li>
            </ul>
          </div>

          <div className="subsection">
            <h3>Admin Operations</h3>
            <p>Monitor system health and broker status:</p>
            <ul className="guide-list">
              <li>View real-time system health metrics</li>
              <li>Check broker connectivity status</li>
              <li>Monitor active user connections</li>
              <li>Track deployment versions and status</li>
            </ul>
          </div>
        </section>

        {/* Troubleshooting */}
        <section className="guide-section">
          <h2 className="section-title">🔧 Troubleshooting</h2>
          
          <div className="subsection">
            <h3>Common Issues</h3>
            
            <div className="faq-item">
              <h4>Can't log in</h4>
              <p>
                Check that you've entered the correct email/username and password. If you've forgotten your
                password, use the "Forgot Password" link on the login page to reset it.
              </p>
            </div>

            <div className="faq-item">
              <h4>Session expired</h4>
              <p>
                Your session expires after 30 minutes of inactivity. If you had "Remember Me" checked,
                you'll be automatically logged back in with a new session. Otherwise, log in again.
              </p>
            </div>

            <div className="faq-item">
              <h4>Access denied to a feature</h4>
              <p>
                Some features require specific user roles. Contact your administrator to request access
                to additional features. Your current role is shown in the user menu.
              </p>
            </div>

            <div className="faq-item">
              <h4>Trading strategy won't deploy</h4>
              <p>
                Ensure your strategy has valid parameters and passes the validation checks. Check the error
                messages in the editor for specific issues. Contact support if you need assistance.
              </p>
            </div>
          </div>
        </section>

        {/* Support & Resources */}
        <section className="guide-section">
          <h2 className="section-title">📚 Support & Resources</h2>
          
          <div className="resources-grid">
            <div className="resource-card">
              <h3>📖 API Documentation</h3>
              <p>Complete reference of all API endpoints available for developers.</p>
              <a href="/docs/routes" className="resource-link">View API Routes →</a>
            </div>

            <div className="resource-card">
              <h3>💬 Community</h3>
              <p>Connect with other traders, share strategies, and get support.</p>
              <a href="/community" className="resource-link">Visit Community →</a>
            </div>

            <div className="resource-card">
              <h3>📧 Support</h3>
              <p>Need help? Contact our support team for assistance.</p>
              <a href="mailto:support@tradeadviser.com" className="resource-link">Email Support →</a>
            </div>

            <div className="resource-card">
              <h3>💻 GitHub</h3>
              <p>View our source code and contribute to the project.</p>
              <a href="https://github.com/tradeadviser" target="_blank" rel="noopener noreferrer" className="resource-link">View Repository →</a>
            </div>
          </div>
        </section>

        {/* Tips & Best Practices */}
        <section className="guide-section">
          <h2 className="section-title">💡 Tips & Best Practices</h2>
          
          <div className="tips-grid">
            <div className="tip-card">
              <span className="tip-icon">🔒</span>
              <h4>Keep Your Password Secure</h4>
              <p>Use a strong, unique password and never share it with anyone.</p>
            </div>

            <div className="tip-card">
              <span className="tip-icon">✅</span>
              <h4>Test Before Deploy</h4>
              <p>Always backtest your trading strategies before deploying them to production.</p>
            </div>

            <div className="tip-card">
              <span className="tip-icon">📊</span>
              <h4>Monitor Risk</h4>
              <p>Regularly review your risk limits and adjust them as needed.</p>
            </div>

            <div className="tip-card">
              <span className="tip-icon">🤝</span>
              <h4>Engage Community</h4>
              <p>Share your experiences and learn from other traders in the community.</p>
            </div>

            <div className="tip-card">
              <span className="tip-icon">📈</span>
              <h4>Track Performance</h4>
              <p>Regularly review your trading performance and adjust your strategies accordingly.</p>
            </div>

            <div className="tip-card">
              <span className="tip-icon">🔄</span>
              <h4>Stay Updated</h4>
              <p>Keep track of platform updates and new features in the community.</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default UserGuide;
