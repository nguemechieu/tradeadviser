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
import UserManagement from './components/UserManagement';
import NotFound from './components/NotFound';
import AccessDenied from './components/AccessDenied';
import Community from './components/Community';
import VerifyLink from './components/VerifyLink';
import RequireAuth from './components/RequireAuth';
import TradeAdviser from './components/TradeAdviser';
import PersistLogin from './components/PersistLogin';
import SystemStatus from './components/SystemStatus';
import Docs from './components/Docs';
import Unauthorized from './components/AccessDenied';

const ROLES = {
  'trader': 'trader',
  'editor': 'editor',
  'admin': 'admin'
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
        <Route path="/docs" element={<Docs />} />

        {/* Protected routes */}
        <Route element={<PersistLogin />}>
          <Route element={<RequireAuth allowedRoles={[ROLES.trader, ROLES.editor, ROLES.admin]} />}>
            <Route path="/home" element={<HomePage />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/trading" element={<TradingPage />} />
            <R
            <Route path="/unautorized" element={<Unauthorized />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={[ROLES.editor, ROLES.admin]} />}>
            <Route path="/trading-editor" element={<TradingEditor />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={[ROLES.editor, ROLES.admin]} />}>
            <Route path="/community" element={<Community />} />
          </Route>

          <Route element={<RequireAuth allowedRoles={[ROLES.admin]} />}>
            <Route path="/admin-panel" element={<AdminPanel />} />
            <Route path="/admin/users" element={<UserManagement />} />
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
