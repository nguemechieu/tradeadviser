import React from "react";
import { useNavigate } from "react-router-dom";
import Logo from "./Logo";
import "./TradeAdviser.css";

const TradeAdviser = () => {
  const navigate = useNavigate();

  const features = [
    {
      icon: "📊",
      title: "Real-Time Analytics",
      description: "Live market data, portfolio tracking, and performance metrics at your fingertips"
    },
    {
      icon: "🤖",
      title: "AI-Powered Signals",
      description: "Advanced algorithms detect trading opportunities across multiple markets 24/7"
    },
    {
      icon: "🛡️",
      title: "Risk Management",
      description: "Built-in safeguards and position sizing tools to protect your capital"
    },
    {
      icon: "⚡",
      title: "Lightning Fast",
      description: "Sub-millisecond latency for instant order execution and strategy deployment"
    },
    {
      icon: "🌍",
      title: "Multi-Asset",
      description: "Trade crypto, forex, stocks, and commodities from a unified platform"
    },
    {
      icon: "👥",
      title: "Community Insights",
      description: "Connect with traders, share strategies, and learn from market experts"
    }
  ];

  const stats = [
    { number: "50K+", label: "Active Traders" },
    { number: "$2.5B", label: "Volume (24h)" },
    { number: "99.9%", label: "Uptime" },
    { number: "150+", label: "Supported Assets" }
  ];

  return (
    <div className="welcome-container">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-content">
          <div className="hero-text">
            <h1 className="hero-title">
              Welcome to <span className="brand-accent">TradeAdviser</span>
            </h1>
            <p className="hero-subtitle">
              Professional trading terminal for the modern markets. 
              Intelligent insights. Powerful execution. Complete control.
            </p>
            <div className="hero-cta">
              <button 
                className="btn btn-primary"
                onClick={() => navigate("/login")}
              >
                Get Started
              </button>
              <button 
                className="btn btn-secondary"
                onClick={() => navigate("/docs/guide")}
              >
                Learn More
              </button>
            </div>
          </div>
          <div className="hero-visual">
            <div className="floating-card card-1">
              <div className="card-value">+24.5%</div>
              <div className="card-label">Monthly Return</div>
            </div>
            <div className="floating-card card-2">
              <div className="card-value">$2.5B</div>
              <div className="card-label">24h Volume</div>
            </div>
            <div className="floating-card card-3">
              <div className="card-value">50K</div>
              <div className="card-label">Active Traders</div>
            </div>
            <svg className="hero-illustration" viewBox="0 0 400 300">
              <defs>
                <linearGradient id="gradientBlue" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style={{ stopColor: "#00d4ff", stopOpacity: 0.8 }} />
                  <stop offset="100%" style={{ stopColor: "#0099ff", stopOpacity: 0.4 }} />
                </linearGradient>
              </defs>
              <path d="M 50 250 Q 100 200 150 220 T 250 150 T 350 100" stroke="url(#gradientBlue)" strokeWidth="3" fill="none" />
              <circle cx="150" cy="220" r="6" fill="#00d4ff" />
              <circle cx="250" cy="150" r="6" fill="#00d4ff" />
              <circle cx="350" cy="100" r="6" fill="#00d4ff" />
            </svg>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="stats-section">
        <div className="stats-grid">
          {stats.map((stat, idx) => (
            <div key={idx} className="stat-card">
              <div className="stat-number">{stat.number}</div>
              <div className="stat-label">{stat.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features Section */}
      <section className="features-section">
        <div className="features-header">
          <h2>Powerful Trading Features</h2>
          <p>Everything you need to trade smarter and faster</p>
        </div>
        <div className="features-grid">
          {features.map((feature, idx) => (
            <div key={idx} className="feature-card">
              <div className="feature-icon">{feature.icon}</div>
              <h3 className="feature-title">{feature.title}</h3>
              <p className="feature-description">{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How It Works Section */}
      <section className="how-it-works">
        <h2>How It Works</h2>
        <div className="steps-container">
          <div className="step">
            <div className="step-number">01</div>
            <h3>Create Account</h3>
            <p>Sign up in minutes and connect your broker account securely</p>
          </div>
          <div className="step-divider"></div>
          <div className="step">
            <div className="step-number">02</div>
            <h3>Analyze Markets</h3>
            <p>Access real-time data, charts, and AI-powered market signals</p>
          </div>
          <div className="step-divider"></div>
          <div className="step">
            <div className="step-number">03</div>
            <h3>Execute Trades</h3>
            <p>Place orders instantly with advanced risk management tools</p>
          </div>
          <div className="step-divider"></div>
          <div className="step">
            <div className="step-number">04</div>
            <h3>Track & Optimize</h3>
            <p>Monitor performance and optimize your strategies in real-time</p>
          </div>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="testimonials-section">
        <h2>Trusted by Professional Traders</h2>
        <div className="testimonials-grid">
          <div className="testimonial-card">
            <div className="stars">⭐⭐⭐⭐⭐</div>
            <p className="testimonial-text">
              "TradeAdviser has transformed my trading workflow. The execution speed and analytics are unmatched."
            </p>
            <div className="testimonial-author">
              <div className="author-avatar">JR</div>
              <div>
                <div className="author-name">James Richardson</div>
                <div className="author-title">Forex Trader</div>
              </div>
            </div>
          </div>
          <div className="testimonial-card">
            <div className="stars">⭐⭐⭐⭐⭐</div>
            <p className="testimonial-text">
              "The AI signals have helped me identify opportunities I would have missed. Highly recommended."
            </p>
            <div className="testimonial-author">
              <div className="author-avatar">SC</div>
              <div>
                <div className="author-name">Sarah Chen</div>
                <div className="author-title">Crypto Investor</div>
              </div>
            </div>
          </div>
          <div className="testimonial-card">
            <div className="stars">⭐⭐⭐⭐⭐</div>
            <p className="testimonial-text">
              "The risk management features give me peace of mind. I can focus on strategy instead of worrying."
            </p>
            <div className="testimonial-author">
              <div className="author-avatar">MK</div>
              <div>
                <div className="author-name">Michael Kumar</div>
                <div className="author-title">Portfolio Manager</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="final-cta">
        <div className="cta-content">
          <h2>Ready to Trade Smarter?</h2>
          <p>Join thousands of traders using TradeAdviser to achieve their goals</p>
          <button 
            className="btn btn-large"
            onClick={() => navigate("/register")}
          >
            Start Your Free Trial
          </button>
        </div>
      </section>
    </div>
  );
};

export default TradeAdviser;
