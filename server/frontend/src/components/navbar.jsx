/**
 * Main Navigation Bar for Sopotek Quant System
 * 
 * Provides access to all major routes and features including:
 * - User authentication flows
 * - Portfolio & trading views
 * - Admin dashboard
 * - Settings and workspace configuration
 */

import { useState } from "react";
import logo from "../assets/logo.png";

export function Navbar({ currentView, onNavigate, isAuthenticated, userRole, onLogout }) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const navigationGroups = [
    {
      title: "Trading",
      items: [
        { id: "portfolio", label: "Portfolio", icon: "📊", description: "Dashboard, positions, orders" },
        { id: "trades", label: "Trades", icon: "💱", description: "Trade history and analytics" },
        { id: "signals", label: "Signals", icon: "📡", description: "Trading signals" },
        { id: "performance", label: "Performance", icon: "📈", description: "Strategy performance" },
        { id: "trade", label: "Execute Trade", icon: "🎯", description: "Place new orders" },
      ]
    },
    {
      title: "Administration",
      items: [
        { id: "admin", label: "Admin Dashboard", icon: "⚙️", description: "System administration", requiresAdmin: true },
        { id: "operations", label: "Operations", icon: "🔧", description: "System health & monitoring", requiresAdmin: true },
        { id: "agents", label: "AI Agents", icon: "🤖", description: "Manage trading agents", requiresAdmin: true },
        { id: "risk", label: "Risk Management", icon: "⚠️", description: "Portfolio risk limits", requiresAdmin: true },
        { id: "performance_audit", label: "Performance Audit", icon: "📋", description: "Detailed performance metrics", requiresAdmin: true },
        { id: "users_licenses", label: "Users & Licenses", icon: "🎫", description: "User accounts & licenses", requiresAdmin: true },
      ]
    },
    {
      title: "Account",
      items: [
        { id: "workspace", label: "Workspace Settings", icon: "⚡", description: "Personal settings & preferences" },
        { id: "auth", label: "Authentication", icon: "🔐", description: "Login, register, or reset password" },
      ]
    }
  ];

  const handleNavClick = (viewId) => {
    onNavigate(viewId);
    setIsMenuOpen(false);
  };

  const handleLogout = () => {
    onLogout();
    handleNavClick("auth");
  };

  const filteredGroups = navigationGroups.map(group => ({
    ...group,
    items: group.items.filter(item => !item.requiresAdmin || userRole === "admin")
  })).filter(group => group.items.length > 0);

  return (
    <nav className="navbar">
      <div className="navbar__container">
        {/* Logo & Brand */}
        <div className="navbar__brand">
          <img src={logo} alt="Sopotek" className="navbar__logo" />
          <span className="navbar__title">TradeAdviser</span>
        </div>

        {/* Mobile Menu Toggle */}
        <button 
          className="navbar__toggle"
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          aria-label="Toggle navigation menu"
        >
          <span className="navbar__toggle-icon">☰</span>
        </button>

        {/* Navigation Menu */}
        <div className={`navbar__menu ${isMenuOpen ? "navbar__menu--open" : ""}`}>
          {filteredGroups.map((group) => (
            <div key={group.title} className="navbar__group">
              <div className="navbar__group-title">{group.title}</div>
              <div className="navbar__items">
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    className={`navbar__item ${currentView === item.id ? "navbar__item--active" : ""}`}
                    onClick={() => handleNavClick(item.id)}
                    title={item.description}
                  >
                    <span className="navbar__item-icon">{item.icon}</span>
                    <span className="navbar__item-label">{item.label}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}

          {/* User Section */}
          <div className="navbar__footer">
            {isAuthenticated && (
              <>
                <div className="navbar__user-info">
                  <span className="navbar__user-badge">{userRole?.toUpperCase() || "USER"}</span>
                </div>
                <button 
                  className="navbar__logout"
                  onClick={handleLogout}
                >
                  <span>🚪</span> Logout
                </button>
              </>
            )}
            {!isAuthenticated && (
              <button 
                className="navbar__login"
                onClick={() => handleNavClick("auth")}
              >
                <span>🔓</span> Login
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Mobile Overlay */}
      {isMenuOpen && (
        <div 
          className="navbar__overlay"
          onClick={() => setIsMenuOpen(false)}
        />
      )}
    </nav>
  );
}

export function NavbarLink({ href, children, target = "_blank" }) {
  return (
    <a 
      href={href} 
      target={target} 
      rel={target === "_blank" ? "noopener noreferrer" : undefined}
      className="navbar-link"
    >
      {children}
    </a>
  );
}
