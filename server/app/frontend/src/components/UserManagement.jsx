import { useState, useEffect, useContext } from 'react';
import AuthContext from '../context/AuthProvider';
import axiosInstance from '../api/axiosConfig';
import '../app.css';

const ROLES = [
    { value: 'trader', label: 'Trader', color: '#53b4ff', description: 'Can view dashboards and place trades' },
    { value: 'editor', label: 'Editor', color: '#ffd93d', description: 'Can edit trading strategies' },
    { value: 'admin', label: 'Admin', color: '#ff6b6b', description: 'Full system access' }
];

const UserManagement = () => {
    const { auth } = useContext(AuthContext);
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [updatingRole, setUpdatingRole] = useState({});
    const [selectedUsers, setSelectedUsers] = useState(new Set());
    const [bulkRole, setBulkRole] = useState('trader');
    const [bulkUpdating, setBulkUpdating] = useState(false);
    const [auditLogs, setAuditLogs] = useState([]);
    const [showAuditLogs, setShowAuditLogs] = useState(false);
    const [auditLoading, setAuditLoading] = useState(false);

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
            const response = await axiosInstance.get('/admin/users');
            setUsers(response.data || []);
            setError('');
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to fetch users');
            console.error('Error fetching users:', err);
        } finally {
            setLoading(false);
        }
    };

    const fetchAuditLogs = async () => {
        try {
            setAuditLoading(true);
            const response = await axiosInstance.get('/admin/audit-logs?limit=50');
            setAuditLogs(response.data.logs || []);
        } catch (err) {
            setError('Failed to fetch audit logs');
            console.error('Error fetching audit logs:', err);
        } finally {
            setAuditLoading(false);
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
            const response = await axiosInstance.post('/admin/users', formData);
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
            const response = await axiosInstance.put(`/admin/users/${userId}/role`, { role: newRole });
            
            // Update local users list
            setUsers(users.map(user => 
                user.id === userId ? { ...user, role: newRole } : user
            ));
            
            setError('');
            // Refresh audit logs
            if (showAuditLogs) {
                fetchAuditLogs();
            }
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to update user role');
            console.error('Error updating role:', err);
        } finally {
            setUpdatingRole(prev => ({ ...prev, [userId]: false }));
        }
    };

    const handleToggleUserSelection = (userId) => {
        const newSelected = new Set(selectedUsers);
        if (newSelected.has(userId)) {
            newSelected.delete(userId);
        } else {
            newSelected.add(userId);
        }
        setSelectedUsers(newSelected);
    };

    const handleSelectAll = () => {
        if (selectedUsers.size === users.length) {
            setSelectedUsers(new Set());
        } else {
            setSelectedUsers(new Set(users.map(u => u.id)));
        }
    };

    const handleBulkRoleUpdate = async () => {
        if (selectedUsers.size === 0) {
            setError('Please select at least one user');
            return;
        }

        try {
            setBulkUpdating(true);
            const updates = Array.from(selectedUsers).map(userId => ({
                user_id: userId,
                role: bulkRole
            }));

            const response = await axiosInstance.put('/admin/users/roles/bulk', { updates });
            
            // Update local users list
            setUsers(users.map(user => 
                selectedUsers.has(user.id) ? { ...user, role: bulkRole } : user
            ));
            
            setSelectedUsers(new Set());
            setError('');
            fetchAuditLogs();
        } catch (err) {
            setError(err.response?.data?.detail || 'Failed to bulk update roles');
            console.error('Error bulk updating roles:', err);
        } finally {
            setBulkUpdating(false);
        }
    };

    const getRoleByValue = (value) => {
        return ROLES.find(r => r.value === value) || ROLES[0];
    };

    const formatDate = (isoDate) => {
        try {
            return new Date(isoDate).toLocaleString();
        } catch {
            return isoDate;
        }
    };

    return (
        <section style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
            <div style={{ marginBottom: '2rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
                    <h1>User Management</h1>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button
                            onClick={() => {
                                setShowAuditLogs(!showAuditLogs);
                                if (!showAuditLogs) fetchAuditLogs();
                            }}
                            className="btn btn-secondary"
                            style={{ padding: '0.5rem 1rem' }}
                        >
                            📋 {showAuditLogs ? 'Hide' : 'Show'} Audit Logs
                        </button>
                        <button
                            onClick={() => setShowCreateForm(!showCreateForm)}
                            className="btn btn-primary"
                            style={{ padding: '0.5rem 1rem' }}
                        >
                            {showCreateForm ? '✕ Cancel' : '+ New User'}
                        </button>
                    </div>
                </div>
            </div>

            {/* Error Message */}
            {error && (
                <div style={{
                    backgroundColor: '#fee',
                    color: '#c33',
                    padding: '1rem',
                    borderRadius: '4px',
                    marginBottom: '1rem',
                    border: '1px solid #fcc'
                }}>
                    ⚠️ {error}
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
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
                                {ROLES.map(role => (
                                    <label key={role.value} style={{
                                        padding: '0.75rem',
                                        border: `2px solid ${formData.role === role.value ? role.color : 'rgba(136, 168, 203, 0.2)'}`,
                                        borderRadius: '4px',
                                        cursor: 'pointer',
                                        backgroundColor: formData.role === role.value ? `${role.color}15` : 'transparent',
                                        transition: 'all 0.2s'
                                    }}>
                                        <input
                                            type="radio"
                                            name="role"
                                            value={role.value}
                                            checked={formData.role === role.value}
                                            onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                                            style={{ marginRight: '0.5rem', cursor: 'pointer' }}
                                        />
                                        <span style={{ color: role.color, fontWeight: '600', fontSize: '0.9rem' }}>
                                            {role.label}
                                        </span>
                                        <div style={{ fontSize: '0.75rem', color: '#8ea3bc', marginTop: '0.25rem' }}>
                                            {role.description}
                                        </div>
                                    </label>
                                ))}
                            </div>
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

            {/* Bulk Role Update */}
            {selectedUsers.size > 0 && (
                <div className="card" style={{
                    padding: '1rem',
                    marginBottom: '2rem',
                    backgroundColor: 'rgba(83, 180, 255, 0.05)',
                    border: '1px solid rgba(83, 180, 255, 0.2)'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                        <span style={{ color: '#53b4ff', fontWeight: '600' }}>
                            {selectedUsers.size} user{selectedUsers.size !== 1 ? 's' : ''} selected
                        </span>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                            <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                Assign role:
                                <select
                                    value={bulkRole}
                                    onChange={(e) => setBulkRole(e.target.value)}
                                    style={{
                                        padding: '0.5rem',
                                        borderRadius: '4px',
                                        border: '1px solid rgba(136, 168, 203, 0.3)',
                                        backgroundColor: '#1a1f2e',
                                        color: '#8ea3bc',
                                        cursor: 'pointer'
                                    }}
                                >
                                    {ROLES.map(role => (
                                        <option key={role.value} value={role.value}>{role.label}</option>
                                    ))}
                                </select>
                            </label>
                            <button
                                onClick={handleBulkRoleUpdate}
                                disabled={bulkUpdating}
                                className="btn btn-primary"
                                style={{ padding: '0.5rem 1rem' }}
                            >
                                {bulkUpdating ? '⏳ Updating...' : '✓ Apply to Selected'}
                            </button>
                            <button
                                onClick={() => setSelectedUsers(new Set())}
                                className="btn btn-secondary"
                                style={{ padding: '0.5rem 1rem' }}
                            >
                                ✕ Cancel
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Users List */}
            <div className="card" style={{ padding: '2rem', marginBottom: '2rem' }}>
                <h2 style={{ marginBottom: '1rem' }}>All Users ({users.length})</h2>
                
                {loading ? (
                    <p>⏳ Loading users...</p>
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
                                    <th style={{ padding: '1rem', textAlign: 'left', width: '40px' }}>
                                        <input
                                            type="checkbox"
                                            checked={selectedUsers.size === users.length && users.length > 0}
                                            onChange={handleSelectAll}
                                            style={{ cursor: 'pointer', width: '18px', height: '18px' }}
                                        />
                                    </th>
                                    <th style={{ padding: '1rem', textAlign: 'left' }}>Email</th>
                                    <th style={{ padding: '1rem', textAlign: 'left' }}>Username</th>
                                    <th style={{ padding: '1rem', textAlign: 'left' }}>Name</th>
                                    <th style={{ padding: '1rem', textAlign: 'center' }}>Role</th>
                                    <th style={{ padding: '1rem', textAlign: 'center' }}>Change Role</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((user) => {
                                    const role = getRoleByValue(user.role || 'trader');
                                    return (
                                        <tr key={user.id} style={{
                                            borderBottom: '1px solid rgba(136, 168, 203, 0.1)',
                                            backgroundColor: selectedUsers.has(user.id) ? 'rgba(83, 180, 255, 0.05)' : 'transparent'
                                        }}>
                                            <td style={{ padding: '1rem', textAlign: 'center' }}>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedUsers.has(user.id)}
                                                    onChange={() => handleToggleUserSelection(user.id)}
                                                    style={{ cursor: 'pointer', width: '18px', height: '18px' }}
                                                />
                                            </td>
                                            <td style={{ padding: '1rem' }}>{user.email}</td>
                                            <td style={{ padding: '1rem' }}>{user.username}</td>
                                            <td style={{ padding: '1rem' }}>{user.display_name}</td>
                                            <td style={{ padding: '1rem', textAlign: 'center' }}>
                                                <span style={{
                                                    display: 'inline-block',
                                                    padding: '0.4rem 0.8rem',
                                                    borderRadius: '20px',
                                                    backgroundColor: role.color,
                                                    color: '#fff',
                                                    fontSize: '0.85rem',
                                                    fontWeight: '600'
                                                }}>
                                                    {role.label}
                                                </span>
                                            </td>
                                            <td style={{ padding: '1rem', textAlign: 'center' }}>
                                                <select
                                                    value={user.role || 'trader'}
                                                    onChange={(e) => handleRoleChange(user.id, e.target.value)}
                                                    disabled={updatingRole[user.id]}
                                                    title="Click to change user role"
                                                    style={{
                                                        padding: '0.5rem 0.75rem',
                                                        borderRadius: '4px',
                                                        border: `1px solid ${getRoleByValue(user.role || 'trader').color}`,
                                                        backgroundColor: '#1a1f2e',
                                                        color: getRoleByValue(user.role || 'trader').color,
                                                        cursor: updatingRole[user.id] ? 'not-allowed' : 'pointer',
                                                        fontWeight: '600',
                                                        fontSize: '0.9rem'
                                                    }}
                                                >
                                                    {ROLES.map(r => (
                                                        <option key={r.value} value={r.value}>{r.label}</option>
                                                    ))}
                                                </select>
                                                {updatingRole[user.id] && <span style={{ marginLeft: '0.5rem' }}>⏳</span>}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {/* Audit Logs */}
            {showAuditLogs && (
                <div className="card" style={{ padding: '2rem' }}>
                    <h2 style={{ marginBottom: '1rem' }}>Recent Audit Logs</h2>
                    
                    {auditLoading ? (
                        <p>⏳ Loading audit logs...</p>
                    ) : auditLogs.length === 0 ? (
                        <p style={{ color: '#8ea3bc' }}>No audit logs found</p>
                    ) : (
                        <div style={{ overflowX: 'auto' }}>
                            <table style={{
                                width: '100%',
                                borderCollapse: 'collapse',
                                fontSize: '0.9rem'
                            }}>
                                <thead>
                                    <tr style={{ borderBottom: '2px solid rgba(136, 168, 203, 0.2)' }}>
                                        <th style={{ padding: '0.75rem', textAlign: 'left' }}>Action</th>
                                        <th style={{ padding: '0.75rem', textAlign: 'left' }}>Admin</th>
                                        <th style={{ padding: '0.75rem', textAlign: 'left' }}>Target User</th>
                                        <th style={{ padding: '0.75rem', textAlign: 'center' }}>Change</th>
                                        <th style={{ padding: '0.75rem', textAlign: 'left' }}>Timestamp</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {auditLogs.map((log, idx) => {
                                        const oldRole = getRoleByValue(log.old_value || 'trader');
                                        const newRole = getRoleByValue(log.new_value || 'trader');
                                        return (
                                            <tr key={idx} style={{ borderBottom: '1px solid rgba(136, 168, 203, 0.1)' }}>
                                                <td style={{ padding: '0.75rem' }}>
                                                    <span style={{
                                                        backgroundColor: 'rgba(255, 182, 61, 0.1)',
                                                        color: '#ffb63d',
                                                        padding: '0.25rem 0.5rem',
                                                        borderRadius: '3px',
                                                        fontWeight: '600',
                                                        fontSize: '0.8rem'
                                                    }}>
                                                        {log.action.toUpperCase()}
                                                    </span>
                                                </td>
                                                <td style={{ padding: '0.75rem', color: '#8ea3bc' }}>
                                                    {log.admin?.email || 'System'}
                                                </td>
                                                <td style={{ padding: '0.75rem', color: '#8ea3bc' }}>
                                                    {log.target?.email || 'N/A'}
                                                </td>
                                                <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                                                    {log.old_value && (
                                                        <>
                                                            <span style={{
                                                                display: 'inline-block',
                                                                padding: '0.2rem 0.5rem',
                                                                borderRadius: '3px',
                                                                backgroundColor: `${oldRole.color}20`,
                                                                color: oldRole.color,
                                                                fontSize: '0.8rem',
                                                                fontWeight: '600'
                                                            }}>
                                                                {oldRole.label}
                                                            </span>
                                                            <span style={{ margin: '0 0.25rem', color: '#8ea3bc' }}>→</span>
                                                            <span style={{
                                                                display: 'inline-block',
                                                                padding: '0.2rem 0.5rem',
                                                                borderRadius: '3px',
                                                                backgroundColor: `${newRole.color}20`,
                                                                color: newRole.color,
                                                                fontSize: '0.8rem',
                                                                fontWeight: '600'
                                                            }}>
                                                                {newRole.label}
                                                            </span>
                                                        </>
                                                    )}
                                                </td>
                                                <td style={{ padding: '0.75rem', color: '#8ea3bc', fontSize: '0.85rem' }}>
                                                    {formatDate(log.timestamp)}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </section>
    );
};

export default UserManagement;
