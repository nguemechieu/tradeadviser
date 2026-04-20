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
    firstName: '',
    lastName: ''
  });

  useEffect(() => {
    fetchAccountData();
  }, []);

  const fetchAccountData = async () => {
    try {
      setLoading(true);
      const { data } = await axiosInstance.get('/auth/me');
      setAccountData(data);
      setFormData({
        email: data.email || '',
        firstName: data.first_name || '',
        lastName: data.last_name || ''
      });
      setError(null);
    } catch (err) {
      setError(err.message);
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
      const { data: updatedData } = await axiosInstance.put('/users/profile', formData);
      setAccountData(updatedData);
      setEditing(false);
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error('Error updating account:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading && !accountData) {
    return <section className="account-page"><div className="loading">Loading...</div></section>;
  }

  return (
    <section className="account-page">
      <div className="account-container">
        <div className="account-header">
          <h1>Account Settings</h1>
          <p>Manage your account information and preferences</p>
        </div>

        {error && <div className="error-message">{error}</div>}

        <div className="account-section">
          <h2>Profile Information</h2>
          
          {editing ? (
            <form className="form-group">
              <div className="form-field">
                <label>Email</label>
                <input 
                  type="email" 
                  name="email" 
                  value={formData.email}
                  onChange={handleInputChange}
                  disabled
                  className="input-field"
                />
              </div>

              <div className="form-field">
                <label>First Name</label>
                <input 
                  type="text" 
                  name="firstName" 
                  value={formData.firstName}
                  onChange={handleInputChange}
                  className="input-field"
                />
              </div>

              <div className="form-field">
                <label>Last Name</label>
                <input 
                  type="text" 
                  name="lastName" 
                  value={formData.lastName}
                  onChange={handleInputChange}
                  className="input-field"
                />
              </div>

              <div className="form-actions">
                <button 
                  type="button"
                  onClick={handleSave}
                  disabled={loading}
                  className="btn btn-primary"
                >
                  {loading ? 'Saving...' : 'Save Changes'}
                </button>
                <button 
                  type="button"
                  onClick={() => setEditing(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : (
            <div className="profile-info">
              <div className="info-field">
                <label>Email</label>
                <p>{accountData?.email}</p>
              </div>

              <div className="info-field">
                <label>First Name</label>
                <p>{accountData?.first_name || 'Not set'}</p>
              </div>

              <div className="info-field">
                <label>Last Name</label>
                <p>{accountData?.last_name || 'Not set'}</p>
              </div>

              <button 
                onClick={() => setEditing(true)}
                className="btn btn-primary"
              >
                Edit Profile
              </button>
            </div>
          )}
        </div>

        <div className="account-section">
          <h2>Account Status</h2>
          <div className="status-info">
            <div className="status-field">
              <label>Account Created</label>
              <p>{new Date(accountData?.created_at).toLocaleDateString()}</p>
            </div>
            <div className="status-field">
              <label>Last Updated</label>
              <p>{new Date(accountData?.updated_at).toLocaleDateString()}</p>
            </div>
          </div>
        </div>

        <div className="account-section">
          <h2>Preferences</h2>
          <div className="preferences">
            <div className="preference-item">
              <input type="checkbox" id="notifications" defaultChecked />
              <label htmlFor="notifications">Enable Email Notifications</label>
            </div>
            <div className="preference-item">
              <input type="checkbox" id="two-factor" />
              <label htmlFor="two-factor">Enable Two-Factor Authentication</label>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default AccountPage;
