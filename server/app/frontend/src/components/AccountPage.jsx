import { useContext, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AuthContext from '../context/AuthProvider';
import axiosInstance from '../api/axiosConfig';
import '../styles.css';

const AccountPage = () => {
  const { auth } = useContext(AuthContext);
  const navigate = useNavigate();
  const [accountData, setAccountData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editing, setEditing] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    username: '',
    first_name: '',
    last_name: '',
    display_name: ''
  });

  useEffect(() => {
    fetchAccountData();
  }, []);

  const fetchAccountData = async () => {
    try {
      setLoading(true);
      const { data } = await axiosInstance.get('/auth/me');
      setAccountData(data);
      const userData = data.user || {};
      setFormData({
        email: userData.email || '',
        username: userData.username || '',
        first_name: userData.first_name || '',
        last_name: userData.last_name || '',
        display_name: userData.display_name || ''
      });
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to load account data');
      console.error('Error fetching account data:', err);
      if (err.response?.status === 401) {
        navigate('/login');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      const { data: updatedData } = await axiosInstance.put('/api/users/profile', formData);
      setAccountData(updatedData);
      setEditing(false);
      setError(null);
    } catch (err) {
      setError(err.message || 'Failed to update account');
      console.error('Error updating account:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !accountData) {
    return (
      <section className="account-page">
        <div className="loading">Loading account information...</div>
      </section>
    );
  }

  if (!accountData) {
    return (
      <section className="account-page">
        <div className="error-message">Failed to load account data</div>
      </section>
    );
  }

  const userData = accountData.user || {};
  const accountInfo = accountData.account || {};
  const stats = accountData.stats || {};

  return (
    <section className="account-page" style={{ padding: '2rem' }}>
      <div className="account-container" style={{ maxWidth: '1200px', margin: '0 auto' }}>
        
        {/* Header */}
        <div className="account-header" style={{ marginBottom: '2rem', borderBottom: '2px solid #1e40af', paddingBottom: '1rem' }}>
          <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Account Dashboard</h1>
          <p style={{ color: '#666' }}>Manage your account information and settings</p>
        </div>

        {error && (
          <div className="error-message" style={{
            backgroundColor: '#fee',
            color: '#c33',
            padding: '1rem',
            borderRadius: '4px',
            marginBottom: '2rem',
            border: '1px solid #fcc'
          }}>
            {error}
          </div>
        )}

        {/* Profile Summary Cards */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
          gap: '1.5rem',
          marginBottom: '2rem'
        }}>
          {/* User Info Card */}
          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '1.5rem',
            borderRadius: '8px',
            border: '1px solid #e0e0e0'
          }}>
            <h3 style={{ marginTop: 0, color: '#1e40af' }}>User Profile</h3>
            <div style={{ fontSize: '0.95rem' }}>
              <p><strong>Username:</strong> {userData.username}</p>
              <p><strong>Display Name:</strong> {userData.display_name || 'Not set'}</p>
              <p><strong>Role:</strong> <span style={{
                backgroundColor: userData.is_admin ? '#f87171' : '#3b82f6',
                color: '#fff',
                padding: '0.25rem 0.75rem',
                borderRadius: '4px',
                fontSize: '0.9rem'
              }}>{userData.role}</span></p>
              <p><strong>Status:</strong> <span style={{
                color: userData.is_active ? '#10b981' : '#ef4444'
              }}>
                {userData.is_active ? '✓ Active' : '✗ Inactive'}
              </span></p>
            </div>
          </div>

          {/* Account Balance Card */}
          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '1.5rem',
            borderRadius: '8px',
            border: '1px solid #e0e0e0'
          }}>
            <h3 style={{ marginTop: 0, color: '#1e40af' }}>Account Balance</h3>
            <div style={{ fontSize: '0.95rem' }}>
              <p><strong>Account ID:</strong> {accountInfo.account_id}</p>
              <p><strong>Cash Balance:</strong> ${accountInfo.cash_balance?.toLocaleString()}</p>
              <p><strong>Starting Balance:</strong> ${accountInfo.starting_balance?.toLocaleString()}</p>
              <p><strong>Total Value:</strong> ${accountInfo.account_value?.toLocaleString()}</p>
            </div>
          </div>

          {/* Account Stats Card */}
          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '1.5rem',
            borderRadius: '8px',
            border: '1px solid #e0e0e0'
          }}>
            <h3 style={{ marginTop: 0, color: '#1e40af' }}>Account Information</h3>
            <div style={{ fontSize: '0.95rem' }}>
              <p><strong>Created:</strong> {stats.created_at ? new Date(stats.created_at).toLocaleDateString() : 'N/A'}</p>
              <p><strong>Last Login:</strong> {stats.last_login ? new Date(stats.last_login).toLocaleDateString() : 'Never'}</p>
              <p><strong>Permissions:</strong> {userData.permissions?.length || 0} granted</p>
            </div>
          </div>
        </div>

        {/* Contact Information Section */}
        <div style={{
          backgroundColor: '#fff',
          padding: '1.5rem',
          borderRadius: '8px',
          border: '1px solid #e0e0e0',
          marginBottom: '2rem'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ margin: 0 }}>Contact Information</h2>
            {!editing && (
              <button
                onClick={() => setEditing(true)}
                style={{
                  padding: '0.5rem 1rem',
                  backgroundColor: '#3b82f6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '0.95rem'
                }}
              >
                Edit
              </button>
            )}
          </div>

          {editing ? (
            <form style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
              gap: '1rem'
            }}>
              <div>
                <label><strong>Email</strong></label>
                <input 
                  type="email" 
                  name="email" 
                  value={formData.email}
                  onChange={handleInputChange}
                  disabled
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    borderRadius: '4px',
                    border: '1px solid #ccc',
                    opacity: 0.6,
                    backgroundColor: '#f0f0f0'
                  }}
                />
              </div>

              <div>
                <label><strong>Username</strong></label>
                <input 
                  type="text" 
                  name="username" 
                  value={formData.username}
                  onChange={handleInputChange}
                  disabled
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    borderRadius: '4px',
                    border: '1px solid #ccc',
                    opacity: 0.6,
                    backgroundColor: '#f0f0f0'
                  }}
                />
              </div>

              <div>
                <label><strong>First Name</strong></label>
                <input 
                  type="text" 
                  name="first_name" 
                  value={formData.first_name}
                  onChange={handleInputChange}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    borderRadius: '4px',
                    border: '1px solid #ccc'
                  }}
                />
              </div>

              <div>
                <label><strong>Last Name</strong></label>
                <input 
                  type="text" 
                  name="last_name" 
                  value={formData.last_name}
                  onChange={handleInputChange}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    borderRadius: '4px',
                    border: '1px solid #ccc'
                  }}
                />
              </div>

              <div style={{ gridColumn: 'span 2' }}>
                <label><strong>Display Name</strong></label>
                <input 
                  type="text" 
                  name="display_name" 
                  value={formData.display_name}
                  onChange={handleInputChange}
                  style={{
                    width: '100%',
                    padding: '0.5rem',
                    borderRadius: '4px',
                    border: '1px solid #ccc'
                  }}
                />
              </div>

              <div style={{ gridColumn: 'span 2', display: 'flex', gap: '1rem' }}>
                <button
                  onClick={handleSave}
                  disabled={loading}
                  style={{
                    padding: '0.75rem 1.5rem',
                    backgroundColor: '#10b981',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    opacity: loading ? 0.6 : 1
                  }}
                >
                  {loading ? 'Saving...' : 'Save Changes'}
                </button>
                <button
                  onClick={() => setEditing(false)}
                  style={{
                    padding: '0.75rem 1.5rem',
                    backgroundColor: '#6b7280',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
              gap: '1rem'
            }}>
              <div>
                <p style={{ margin: '0 0 0.5rem 0', color: '#666' }}>Email</p>
                <p style={{ margin: 0, fontSize: '1.05rem', fontWeight: 500 }}>{userData.email}</p>
              </div>
              <div>
                <p style={{ margin: '0 0 0.5rem 0', color: '#666' }}>First Name</p>
                <p style={{ margin: 0, fontSize: '1.05rem', fontWeight: 500 }}>{formData.first_name || 'Not set'}</p>
              </div>
              <div>
                <p style={{ margin: '0 0 0.5rem 0', color: '#666' }}>Last Name</p>
                <p style={{ margin: 0, fontSize: '1.05rem', fontWeight: 500 }}>{formData.last_name || 'Not set'}</p>
              </div>
              <div style={{ gridColumn: 'span 2' }}>
                <p style={{ margin: '0 0 0.5rem 0', color: '#666' }}>Display Name</p>
                <p style={{ margin: 0, fontSize: '1.05rem', fontWeight: 500 }}>{userData.display_name || formData.display_name || 'Not set'}</p>
              </div>
            </div>
          )}
        </div>

        {/* Permissions Section */}
        {userData.permissions && userData.permissions.length > 0 && (
          <div style={{
            backgroundColor: '#f8f9fa',
            padding: '1.5rem',
            borderRadius: '8px',
            border: '1px solid #e0e0e0'
          }}>
            <h3 style={{ marginTop: 0, color: '#1e40af' }}>Account Permissions</h3>
            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '0.75rem'
            }}>
              {userData.permissions.map((perm, idx) => (
                <span
                  key={idx}
                  style={{
                    backgroundColor: '#dbeafe',
                    color: '#1e40af',
                    padding: '0.5rem 1rem',
                    borderRadius: '20px',
                    fontSize: '0.9rem',
                    border: '1px solid #93c5fd'
                  }}
                >
                  {perm}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

export default AccountPage;
