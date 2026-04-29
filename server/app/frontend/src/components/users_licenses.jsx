/**
 * Users & Licenses Pillar Dashboard
 * User management and subscription control
 */

import { useState, useEffect } from "react";
import { Card, MetricBox, DataTable, Alert, Badge, Button } from "./shared";

export function UsersLicensesDashboard({ token, onError }) {
  const [users, setUsers] = useState([]);
  const [licenses, setLicenses] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadUserData();
  }, [token]);

  async function loadUserData() {
    try {
      setLoading(true);
      setError("");

      const [usersRes, licensesRes] = await Promise.all([
        fetch("/api/v3/admin/users-licenses/users", {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch("/api/v3/admin/users-licenses/licenses", {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);

      if (!usersRes.ok) throw new Error("Failed to load users");
      if (!licensesRes.ok) throw new Error("Failed to load licenses");

      const usersData = await usersRes.json();
      const licensesData = await licensesRes.json();

      setUsers(usersData.users || []);
      setLicenses(licensesData.licenses || []);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error loading user data";
      setError(msg);
      onError?.(msg);
    } finally {
      setLoading(false);
    }
  }

  const activeLicenses = licenses.filter((l) => l.status === "active");
  const expiredLicenses = licenses.filter((l) => l.status === "expired");
  const activeUsers = users.filter((u) => u.is_active);

  return (
    <div className="pillar-dashboard users-licenses-dashboard">
      <h2>Users & Licenses</h2>

      {error && (
        <Alert
          type="error"
          title="Error"
          message={error}
          onDismiss={() => setError("")}
        />
      )}

      {/* Summary Stats */}
      <Card title="License Summary" subtitle="Subscription and entitlements overview">
        <div className="metrics-grid">
          <MetricBox
            label="Total Users"
            value={users.length}
            subtext={`${activeUsers.length} active`}
            tone="neutral"
          />
          <MetricBox
            label="Active Licenses"
            value={activeLicenses.length}
            tone="success"
          />
          <MetricBox
            label="Expired Licenses"
            value={expiredLicenses.length}
            tone={expiredLicenses.length > 0 ? "warning" : "success"}
          />
          <MetricBox
            label="License Types"
            value={new Set(licenses.map((l) => l.type)).size}
            tone="neutral"
          />
        </div>
      </Card>

      {/* Users Table */}
      <Card
        title="Users"
        subtitle="User management and license assignments"
        action={<Button variant="primary">+ Add User</Button>}
      >
        <DataTable
          columns={[
            { key: "email", label: "Email", width: "25%" },
            { key: "username", label: "Username", width: "20%" },
            {
              key: "role",
              label: "Role",
              width: "15%",
              render: (role) => <Badge type={role}>{role}</Badge>,
            },
            {
              key: "is_active",
              label: "Status",
              width: "15%",
              render: (active) => (
                <Badge type={active ? "success" : "error"}>
                  {active ? "Active" : "Inactive"}
                </Badge>
              ),
            },
            {
              key: "license",
              label: "License",
              width: "15%",
              render: (lic) => (
                <Badge type={lic?.status || "error"}>
                  {lic?.type || "None"}
                </Badge>
              ),
            },
            { key: "created_at", label: "Joined", width: "10%" },
          ]}
          rows={users}
          onRowClick={(user) => setSelectedUser(user)}
        />
      </Card>

      {/* User Details */}
      {selectedUser && (
        <Card
          title={`User: ${selectedUser.email}`}
          subtitle="Account details and license information"
          action={<Button variant="secondary">Edit</Button>}
        >
          <div className="user-details">
            <div className="user-section">
              <h4>Account Information</h4>
              <dl>
                <dt>Email:</dt>
                <dd>{selectedUser.email}</dd>
                <dt>Username:</dt>
                <dd>{selectedUser.username}</dd>
                <dt>Display Name:</dt>
                <dd>{selectedUser.display_name || "-"}</dd>
                <dt>Role:</dt>
                <dd>{selectedUser.role}</dd>
                <dt>Status:</dt>
                <dd>
                  <Badge type={selectedUser.is_active ? "success" : "error"}>
                    {selectedUser.is_active ? "Active" : "Inactive"}
                  </Badge>
                </dd>
                <dt>Created:</dt>
                <dd>{new Date(selectedUser.created_at).toLocaleDateString()}</dd>
              </dl>
            </div>
            <div className="user-section">
              <h4>License Information</h4>
              {selectedUser.license?.type ? (
                <dl>
                  <dt>Type:</dt>
                  <dd>{selectedUser.license.type}</dd>
                  <dt>Status:</dt>
                  <dd>
                    <Badge type={selectedUser.license.status}>
                      {selectedUser.license.status}
                    </Badge>
                  </dd>
                </dl>
              ) : (
                <p className="hint">No active license assigned</p>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Licenses Table */}
      <Card title="Licenses" subtitle="All licenses and subscriptions">
        <DataTable
          columns={[
            { key: "key", label: "License Key", width: "20%" },
            { key: "product", label: "Product", width: "15%" },
            {
              key: "type",
              label: "Type",
              width: "15%",
              render: (type) => <Badge type={type}>{type}</Badge>,
            },
            {
              key: "status",
              label: "Status",
              width: "15%",
              render: (status) => <Badge type={status}>{status}</Badge>,
            },
            { key: "valid_from", label: "Valid From", width: "12%" },
            { key: "valid_until", label: "Expires", width: "12%" },
            {
              key: "features",
              label: "Features",
              width: "11%",
              render: (features) => `${Object.values(features).filter(Boolean).length} enabled`,
            },
          ]}
          rows={licenses}
        />
      </Card>

      {/* License Types Info */}
      <Card title="License Tiers" subtitle="Available license types and features">
        <div className="license-tiers">
          <div className="tier">
            <h4>Trial</h4>
            <ul>
              <li>✓ Paper trading</li>
              <li>✓ 1 agent</li>
              <li>✓ 100 symbols</li>
              <li>✗ Live trading</li>
            </ul>
          </div>
          <div className="tier">
            <h4>Basic</h4>
            <ul>
              <li>✓ Paper trading</li>
              <li>✓ Live trading</li>
              <li>✓ 5 agents</li>
              <li>✓ 500 symbols</li>
            </ul>
          </div>
          <div className="tier">
            <h4>Professional</h4>
            <ul>
              <li>✓ Backtesting</li>
              <li>✓ Live trading</li>
              <li>✓ 20 agents</li>
              <li>✓ Unlimited symbols</li>
            </ul>
          </div>
          <div className="tier">
            <h4>Institutional</h4>
            <ul>
              <li>✓ Everything</li>
              <li>✓ Multi-broker</li>
              <li>✓ API access</li>
              <li>✓ SLA support</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
}
