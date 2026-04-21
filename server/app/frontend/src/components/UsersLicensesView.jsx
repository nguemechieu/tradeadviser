/**
 * Users & Licenses View
 * User account management and license control
 */

export default function UsersLicensesView({ token, loading, onRefresh }) {
  const [licenses, setLicenses] = React.useState([]);
  const [error, setError] = React.useState("");
  const [showNewLicense, setShowNewLicense] = React.useState(false);
  const [formData, setFormData] = React.useState({
    user_id: "",
    license_type: "basic",
    expiry_date: "",
  });

  React.useEffect(() => {
    if (!token) return;
    loadLicenses();
  }, [token]);

  async function loadLicenses() {
    try {
      setError("");
      const { usersLicenses } = await import("../api/services");
      const data = await usersLicenses.getLicenses(token);
      setLicenses(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load licenses");
    }
  }

  async function handleIssueLicense(e) {
    e.preventDefault();
    try {
      setError("");
      const { usersLicenses } = await import("../api/services");
      await usersLicenses.issueLicense(formData, token);
      setShowNewLicense(false);
      setFormData({ user_id: "", license_type: "basic", expiry_date: "" });
      loadLicenses();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to issue license");
    }
  }

  async function handleRevokeLicense(licenseId) {
    if (!window.confirm("Revoke this license?")) return;
    try {
      setError("");
      const { usersLicenses } = await import("../api/services");
      await usersLicenses.revokeLicense(licenseId, token);
      loadLicenses();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to revoke license");
    }
  }

  return (
    <section className="panel">
      <div className="panel__header">
        <h2>Users & Licenses</h2>
        <button onClick={() => setShowNewLicense(!showNewLicense)}>
          {showNewLicense ? "Cancel" : "Issue License"}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {showNewLicense && (
        <form onSubmit={handleIssueLicense} className="form">
          <div className="form-group">
            <label>User ID</label>
            <input
              type="text"
              value={formData.user_id}
              onChange={(e) =>
                setFormData({ ...formData, user_id: e.target.value })
              }
              required
            />
          </div>
          <div className="form-group">
            <label>License Type</label>
            <select
              value={formData.license_type}
              onChange={(e) =>
                setFormData({ ...formData, license_type: e.target.value })
              }
            >
              <option value="basic">Basic</option>
              <option value="pro">Pro</option>
              <option value="enterprise">Enterprise</option>
            </select>
          </div>
          <div className="form-group">
            <label>Expiry Date</label>
            <input
              type="date"
              value={formData.expiry_date}
              onChange={(e) =>
                setFormData({ ...formData, expiry_date: e.target.value })
              }
              required
            />
          </div>
          <button type="submit">Issue License</button>
        </form>
      )}

      {licenses.length > 0 && (
        <div className="licenses-list">
          <table className="data-table">
            <thead>
              <tr>
                <th>User ID</th>
                <th>License Type</th>
                <th>Status</th>
                <th>Issued</th>
                <th>Expires</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {licenses.map((license) => (
                <tr key={license.id}>
                  <td>{license.user_id}</td>
                  <td>{license.license_type}</td>
                  <td>
                    <span
                      className={`status-pill status-pill--${
                        license.is_active ? "success" : "error"
                      }`}
                    >
                      {license.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td>{new Date(license.issued_at).toLocaleDateString()}</td>
                  <td>{new Date(license.expires_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      onClick={() => handleRevokeLicense(license.id)}
                      className="button-danger"
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
