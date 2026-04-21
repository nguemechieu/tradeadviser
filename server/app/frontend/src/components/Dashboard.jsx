import { useNavigate, Link } from "react-router-dom";
import { useContext, useState } from "react";
import AuthContext from "../context/AuthProvider";
import axiosInstance from "../api/axiosConfig";

const Dashboard = () => {
    const context = useContext(AuthContext);
    
    // Defensive check for context
    if (!context) {
        return <div style={{ color: '#fff', padding: '2rem' }}>Error: Auth context not available</div>;
    }

    const { auth, setAuth } = context;
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);

    const logout = async () => {
        try {
            setLoading(true);
            await axiosInstance.post('/auth/logout');
        } catch (error) {
            console.error('Logout failed:', error);
        } finally {
            // Always clear local state and storage regardless of backend response
            localStorage.removeItem('tradeadviser-token');
            localStorage.removeItem('tradeadviser-user');
            localStorage.removeItem('remember-identifier');
            setAuth({});
            navigate('/login', { replace: true });
            setLoading(false);
        }
    }

    return (
        <section className="dashboard-page">
            <h1>Dashboard</h1>
            <p>You are logged in as {auth?.user?.email || 'User'}!</p>
            <br />
            
            <div className="dashboard-links">
                <Link to="/trading-editor" className="btn btn-primary">Go to the Editor page</Link>
                <br />
                <Link to="/admin-panel" className="btn btn-primary">Go to the Admin page</Link>
                <br />
                <Link to="/community" className="btn btn-primary">Go to the Community</Link>
                <br />
                <Link to="/account" className="btn btn-primary">Go to Account Settings</Link>
                <br />
                <Link to="/trading" className="btn btn-primary">Go to Trading</Link>
            </div>
            
            <div className="flexGrow">
                <button onClick={logout} disabled={loading} className="btn btn-secondary">
                    {loading ? 'Signing out...' : 'Sign Out'}
                </button>
            </div>
        </section>
    )
}

export default Dashboard
