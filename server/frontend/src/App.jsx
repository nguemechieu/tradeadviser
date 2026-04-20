import { Routes, Route } from 'react-router-dom';
import Register from './components/Register';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
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

const ROLES = {
  'User': 2001,
  'Editor': 1984,
  'Admin': 5150
};

function App() {
  return (
      <Routes>
        <Route path="/" element={<Layout />}>
          {/* Public routes */}
          <Route path="login" element={<Login />} />
          <Route path="register" element={<Register />} />
          <Route path="tradeadviser" element={<TradeAdviser />} />
          <Route path="verify-link" element={<VerifyLink />} />
          <Route path="access-denied" element={<AccessDenied />} />

          {/* Protected routes */}

            <Route element={<RequireAuth allowedRoles={[ROLES.User, ROLES.Editor, ROLES.Admin]} />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="not-found" element={<NotFound />} />
            </Route>

            <Route element={<RequireAuth allowedRoles={[ROLES.Editor]} />}>
              <Route path="trading-editor" element={<TradingEditor />} />
            </Route>

            <Route element={<RequireAuth allowedRoles={[ROLES.Admin]} />}>
              <Route path="admin-panel" element={<AdminPanel />} />
            </Route>

            <Route element={<RequireAuth allowedRoles={[ROLES.Editor, ROLES.Admin]} />}>
              <Route path="community" element={<Community />} />
            </Route>


          {/* Catch-all for unmatched routes */}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
  );
}

export default App;
