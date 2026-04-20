import { useState, useEffect, useContext } from 'react';
import AuthContext from '../context/AuthProvider';
import axiosInstance from '../api/axiosConfig';
import '../app.css';

const UserManagement = () => {
    const { auth } = useContext(AuthContext);
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [updatingRole, setUpdatingRole] = useState({});

    // Form state for creating new user
    const [formData, setFormData] = useState({
        email: '',
        username: '',
        password: '',
        first_name: '',
        last_name: '',
        middle_name: '',
        phone_number: '',
        role: 'trader'
    });

    const [createError, setCreateError] = useState('');
    const [createSuccess, setCreateSuccess] = useState('');
    const [creating, setCreating] = useState(false);

    // Fetch all users
    useEffect(() => {
        fetchUsers();
    }, []);

    const fetchUsers = async () => {
        try {
            setLoading(true);
            const response = await axiosInstance.get('/auth/admin/users');
            setUsers(response.data.users || []);
            setError('');
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to fetch users');
            console.error('Error fetching users:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateUser = async (e) => {
        e.preventDefault();
        setCreateError('');
        setCreateSuccess('');

        if (!formData.email || !formData.username || !formData.password || !formData.first_name || !formData.last_name) {
            setCreateError('Please fill in all required fields');
            return;
        }

        try {
            setCreating(true);
            const response = await axiosInstance.post('/auth/admin/create-user', formData);
            setCreateSuccess('User created successfully!');
            setFormData({
                email: '',
                username: '',
                password: '',
                first_name: '',
                last_name: '',
                middle_name: '',
                phone_number: '',
                role: 'trader'
            });
            setShowCreateForm(false);
            fetchUsers();
        } catch (err) {
            setCreateError(err.response?.data?.detail || 'Failed to create user');
            console.error('Error creating user:', err);
        } finally {
            setCreating(false);
        }
    };

    const handleRoleChange = async (userId, newRole) => {
        try {
            setUpdatingRole(prev => ({ ...prev, [userId]: true }));
            const response = await axiosInstance.put(`/auth/admin/users/${userId}/role`, { role: newRole });
            
            // Update local users list
            setUsers(users.map(user => 
                user.id === userId ? { ...user, role: newRole } : user
            ));
            
            setError('');
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to update user role');
            console.error('Error updating role:', err);
        } finally {
            setUpdatingRole(prev => ({ ...prev, [userId]: false }));
        }
    };

    const getRoleColor = (role) => {
        switch (role?.toLowerCase()) {
            case 'admin':
                return '#ff6b6b';
            case 'editor':
                return '#ffd93d';
            case 'trader':
                return '#53b4ff';
            default:
                return '#8ea3bc';
        }
    };

    if (!auth?.user || auth?.role !== 'admin') {
        return (
            <section style={{ padding: '2rem', textAlign: 'center' }}>
                <h2>Access Denied</h2>
                <p>Only administrators can access user management.</p>
            </section>
        );
    }

    return (
        <section style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
            <div style={{ marginBottom: '2rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <h1>User Management</h1>
                    <button
                        onClick={() => setShowCreateForm(!showCreateForm)}
                        className="btn btn-primary"
                        style={{ padding: '0.5rem 1rem' }}
                    >
                        {showCreateForm ? 'Cancel' : '+ Create New User'}
                    </button>
                </div>
            </div>

            {/* Error Message */}
            {error && (
                <div style={{
                    backgroundColor: '#fee',
                    color: '#c33',
                    padding: '1rem',
                    borderRadius: '4px',
                    marginBottom: '1rem'
                }}>
                    {error}
                </div>
            )}

            {/* Create User Form */}
            {showCreateForm && (
                <div className="card" style={{ padding: '2rem', marginBottom: '2rem' }}>
                    <h2>Create New User</h2>
                    <form onSubmit={handleCreateUser} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div>
                            <label>Email *</label>
                            <input
                                type="email"
                                value={formData.email}
                                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                className="input-field"
                                placeholder="user@example.com"
                                required
                            />
                        </div>

                        <div>
                            <label>Username *</label>
                            <input
                                type="text"
                                value={formData.username}
                                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                className="input-field"
                                placeholder="username"
                                required
                            />
                        </div>

                        <div>
                            <label>First Name *</label>
                            <input
                                type="text"
                                value={formData.first_name}
                                onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                                className="input-field"
                                placeholder="John"
                                required
                            />
                        </div>

                        <div>
                            <label>Last Name *</label>
                            <input
                                type="text"
                                value={formData.last_name}
                                onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                                className="input-field"
                                placeholder="Doe"
                                required
                            />
                        </div>

                        <div>
                            <label>Middle Name (Optional)</label>
                            <input
                                type="text"
                                value={formData.middle_name}
                                onChange={(e) => setFormData({ ...formData, middle_name: e.target.value })}
                                className="input-field"
                                placeholder="Middle"
                            />
                        </div>

                        <div>
                            <label>Phone Number (Optional)</label>
                            <input
                                type="tel"
                                value={formData.phone_number}
                                onChange={(e) => setFormData({ ...formData, phone_number: e.target.value })}
                                className="input-field"
                                placeholder="+1 (555) 000-0000"
                            />
                        </div>

                        <div>
                            <label>Password *</label>
                            <input
                                type="password"
                                value={formData.password}
                                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                className="input-field"
                                placeholder="••••••••"
                                required
                            />
                        </div>

                        <div>
                            <label>Role *</label>
                            <select
                                value={formData.role}
                                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                                className="input-field"
                                style={{ cursor: 'pointer' }}
                            >
                                <option value="trader">Trader</option>
                                <option value="editor">Editor</option>
                                <option value="admin">Admin</option>
                            </select>
                        </div>

                        <div style={{ gridColumn: '1 / -1' }}>
                            {createError && (
                                <div style={{
                                    backgroundColor: '#fee',
                                    color: '#c33',
                                    padding: '0.75rem',
                                    borderRadius: '4px',
                                    marginBottom: '1rem'
                                }}>
                                    {createError}
                                </div>
                            )}

                            {createSuccess && (
                                <div style={{
                                    backgroundColor: '#efe',
                                    color: '#3c3',
                                    padding: '0.75rem',
                                    borderRadius: '4px',
                                    marginBottom: '1rem'
                                }}>
                                    {createSuccess}
                                </div>
                            )}

                            <button
                                type="submit"
                                disabled={creating}
                                className="btn btn-primary"
                                style={{ width: '100%' }}
                            >
                                {creating ? 'Creating...' : 'Create User'}
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {/* Users List */}
            <div className="card" style={{ padding: '2rem' }}>
                <h2>All Users ({users.length})</h2>
                
                {loading ? (
                    <p>Loading users...</p>
                ) : users.length === 0 ? (
                    <p style={{ color: '#8ea3bc' }}>No users found</p>
                ) : (
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{
                            width: '100%',
                            borderCollapse: 'collapse',
                            marginTop: '1rem'
                        }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid rgba(136, 168, 203, 0.2)' }}>
                                    <th style={{ padding: '1rem', textAlign: 'left' }}>Email</th>
                                    <th style={{ padding: '1rem', textAlign: 'left' }}>Username</th>
                                    <th style={{ padding: '1rem', textAlign: 'left' }}>Name</th>
                                    <th style={{ padding: '1rem', textAlign: 'left' }}>Role</th>
                                    <th style={{ padding: '1rem', textAlign: 'center' }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((user) => (
                                    <tr key={user.id} style={{ borderBottom: '1px solid rgba(136, 168, 203, 0.1)' }}>
                                        <td style={{ padding: '1rem' }}>{user.email}</td>
                                        <td style={{ padding: '1rem' }}>{user.username}</td>
                                        <td style={{ padding: '1rem' }}>{user.display_name}</td>
                                        <td style={{ padding: '1rem' }}>
                                            <span style={{
                                                display: 'inline-block',
                                                padding: '0.25rem 0.75rem',
                                                borderRadius: '20px',
                                                backgroundColor: getRoleColor(user.role),
                                                color: '#fff',
                                                fontSize: '0.85rem',
                                                fontWeight: '600'
                                            }}>
                                                {user.role?.toUpperCase() || 'TRADER'}
                                            </span>
                                        </td>
                                        <td style={{ padding: '1rem', textAlign: 'center' }}>
                                            <select
                                                value={user.role || 'trader'}
                                                onChange={(e) => handleRoleChange(user.id, e.target.value)}
                                                disabled={updatingRole[user.id]}
                                                style={{
                                                    padding: '0.5rem',
                                                    borderRadius: '4px',
                                                    border: '1px solid rgba(136, 168, 203, 0.3)',
                                                    backgroundColor: '#1a1f2e',
                                                    color: '#8ea3bc',
                                                    cursor: 'pointer'
                                                }}
                                            >
                                                <option value="trader">Trader</option>
                                                <option value="editor">Editor</option>
                                                <option value="admin">Admin</option>
                                            </select>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </section>
    );
};

export default UserManagement;
