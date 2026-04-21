import { Link } from "react-router-dom";
import { UsersLicensesDashboard } from './users_licenses';

const AdminPanel = () => {
    return (
        <section style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
            <h1>Admin Panel</h1>
            <p style={{ color: '#8ea3bc', marginBottom: '2rem' }}>Manage users, licenses, and system configuration</p>
            
            {/* Quick Links */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                gap: '1rem',
                marginBottom: '2rem'
            }}>
                <Link to="/admin/users" className="card" style={{
                    padding: '1.5rem',
                    textDecoration: 'none',
                    color: 'inherit',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    border: '1px solid rgba(83, 180, 255, 0.2)'
                }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(83, 180, 255, 0.05)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                    <h3 style={{ marginTop: 0, color: '#53b4ff' }}>👥 User Management</h3>
                    <p style={{ color: '#8ea3bc', marginBottom: 0 }}>Create users, assign roles, and manage permissions</p>
                </Link>

                <Link to="/system-status" className="card" style={{
                    padding: '1.5rem',
                    textDecoration: 'none',
                    color: 'inherit',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    border: '1px solid rgba(83, 180, 255, 0.2)'
                }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(83, 180, 255, 0.05)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                    <h3 style={{ marginTop: 0, color: '#53b4ff' }}>📊 System Status</h3>
                    <p style={{ color: '#8ea3bc', marginBottom: 0 }}>Monitor system health and performance</p>
                </Link>
            </div>

            <div style={{ marginTop: '2rem', paddingTop: '2rem', borderTop: '1px solid rgba(136, 168, 203, 0.2)' }}>
                <h2>User & License Management</h2>
                <UsersLicensesDashboard token={localStorage.getItem('token')} onError={() => {}} />
            </div>

            <div style={{ flexGrow: 1, marginTop: '2rem', paddingTop: '2rem', borderTop: '1px solid rgba(136, 168, 203, 0.2)' }}>
                <Link to="/" className="btn btn-secondary">← Back to Home</Link>
            </div>
        </section>
    )
}

export default AdminPanel
