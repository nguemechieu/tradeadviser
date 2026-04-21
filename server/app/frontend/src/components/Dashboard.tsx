import { useNavigate } from "react-router-dom";
import { useContext } from "react";
import AuthContext from "../context/AuthProvider";
import './Auth.css';

interface AuthState {
  user?: string;
  email?: string;
  firstname?: string;
  lastname?: string;
  accessToken?: string;
  isLoggedIn?: boolean;
}

const Dashboard = () => {
  const { auth, setAuth } = useContext(AuthContext) as {
    auth: AuthState;
    setAuth: (auth: AuthState) => void;
  };
  const navigate = useNavigate();

  const logout = async () => {
    // Clear auth state and localStorage
    setAuth({});
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
    navigate('/login');
  };

  const displayName = auth?.firstname && auth?.lastname
    ? `${auth.firstname} ${auth.lastname}`
    : auth?.user || 'User';

  return (
    <section className="dashboard">
      <div className="dashboard-header">
        <h1>Welcome to TradeAdviser</h1>
        <p className="subtitle">Intelligent Trading Advisory Platform</p>
      </div>

      <div className="user-info">
        <h2>Welcome, {displayName}!</h2>
        <p>Email: <span>{auth?.email}</span></p>
        {auth?.user && (
          <p>Username: <span>{auth.user}</span></p>
        )}
      </div>

      <div className="dashboard-content">
        <p>You are successfully logged in to TradeAdviser.</p>
        <p>Use the navigation menu to access different features:</p>
        <ul>
          <li>Dashboard - View your trading analytics</li>
          <li>Trading Editor - Create and manage trading strategies</li>
          <li>Community - Connect with other traders</li>
          <li>Admin Panel - Manage system settings (admin only)</li>
        </ul>
      </div>

      <div className="dashboard-actions">
        <button onClick={logout} className="logout-btn">
          Sign Out
        </button>
      </div>
    </section>
  );
};

export default Dashboard;
