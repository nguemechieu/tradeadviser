import { Routes, Route } from 'react-router-dom';
import Register from './components/Register';
import Login from './components/Login';
import Landing from './components/Landing';
import Dashboard from './components/Dashboard';
import HomePage from './components/HomePage';
import AccountPage from './components/AccountPage';
import TradingPage from './components/TradingPage';
import Layout from './components/Layout';
import TradingEditor from './components/TradingEditor';
import AdminPanel from './components/AdminPanel';
import NotFound from './components/NotFound';
import AccessDenied from './components/AccessDenied';
import Community from './components/Community';
import VerifyLink from './components/VerifyLink';
import RequireAuth from './components/RequireAuth';
import TradeAdviser from './components/TradeAdviser';
import PersistLogin from './components/PersistLogin';
import SystemStatus from './components/SystemStatus';

const ROLES = {
  'User': 2001,
  'Editor': 1984,
  'Admin': 5150
};

function App() {
  return (
    <Routes>
      {/* Layout wrapper for all routes */}
      <Route element={<Layout />}>
        {/* Public landing page */}
        <Route path="/" element={<Landing />} />
        
        {/* Public routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/tradeadviser" element={<TradeAdviser />} />
        <Route path="/verify-link" element={<VerifyLink />} />
        <Route path="/access-denied" element={<AccessDenied />} />

        {/* Protected routes */}
        <Route element={<PersistLogin />}>
          <Route element={<RequireAuth allowedRoles={[ROLES.User, ROLES.Editor, ROLES.Admin]} />}>
            <Route path="/home" element={<HomePage />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/trading" element={<TradingPage />} />
            <Route path="/not-found" element={<NotFound />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={[ROLES.Editor, ROLES.Admin]} />}>
            <Route path="/trading-editor" element={<TradingEditor />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={[ROLES.Editor, ROLES.Admin]} />}>
            <Route path="/community" element={<Community />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={[ROLES.Admin]} />}>
            <Route path="/admin-panel" element={<AdminPanel />} />
            <Route path="/system-status" element={<SystemStatus />} />
          </Route>
        </Route>
      </Route>

      {/* Catch-all for undefined routes */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

export default App;
