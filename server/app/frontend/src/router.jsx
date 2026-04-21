import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthProvider';

// Pages
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import PortfolioPage from './pages/PortfolioPage';
import TradingPage from './pages/TradingPage';
import TradesPage from './pages/TradesPage';
import SignalsPage from './pages/SignalsPage';
import PerformancePage from './pages/PerformancePage';
import RiskPage from './pages/RiskPage';
import AgentsPage from './pages/AgentsPage';
import AdminPage from './pages/AdminPage';
import SettingsPage from './pages/SettingsPage';
import NotFoundPage from './pages/NotFoundPage';

// Protected Route Component
const ProtectedRoute = ({ component: Component, adminOnly = false }) => {
  const token = localStorage.getItem('tradeadviser-token');
  const userRole = localStorage.getItem('tradeadviser-user-role');

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (adminOnly && !['ADMIN', 'SUPER_ADMIN'].includes(userRole)) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Component />;
};

export function AppRouter() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected Routes */}
          <Route path="/dashboard" element={<ProtectedRoute component={DashboardPage} />} />
          <Route path="/portfolio" element={<ProtectedRoute component={PortfolioPage} />} />
          <Route path="/trading" element={<ProtectedRoute component={TradingPage} />} />
          <Route path="/trades" element={<ProtectedRoute component={TradesPage} />} />
          <Route path="/signals" element={<ProtectedRoute component={SignalsPage} />} />
          <Route path="/performance" element={<ProtectedRoute component={PerformancePage} />} />
          <Route path="/risk" element={<ProtectedRoute component={RiskPage} />} />
          <Route path="/agents" element={<ProtectedRoute component={AgentsPage} />} />
          
          {/* Admin Routes */}
          <Route path="/admin" element={<ProtectedRoute component={AdminPage} adminOnly />} />
          
          {/* Settings */}
          <Route path="/settings" element={<ProtectedRoute component={SettingsPage} />} />

          {/* Default & 404 */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default AppRouter;
