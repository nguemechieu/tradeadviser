import React, { useEffect, useState } from "react";
import {axiosPrivate} from "../api/axiosPrivate";

const Security = () => {
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [is2FAEnabled, setIs2FAEnabled] = useState(false);
  const [activityLogs, setActivityLogs] = useState([
    { date: "2024-12-21", action: "Login from New York" },
    { date: "2024-12-19", action: "Password change request" },
  ]);

  const handleChangePassword = async (e) => {
    e.preventDefault();

    await axiosPrivate.post("/api/reset-password", {
      current_password: password,
      new_password: newPassword,
    });

    setPassword("");
    setNewPassword("");
  };

  const toggle2FA = () => {
    // Here, you would add logic to enable or disable 2FA
    setIs2FAEnabled(!is2FAEnabled);
  };

  useEffect(() => {
    setActivityLogs(
      activityLogs.concat({
        date: new Date().toISOString().split("T")[0],
        action: is2FAEnabled ? "2FA enabled" : "2FA disabled",
      }),
    );
  }, [activityLogs,is2FAEnabled,setIs2FAEnabled,setActivityLogs]);

  return (
    <div className="security-container">
      <h2>Security Settings</h2>

      {/* Change Password Section */}
      <div className="section">
        <h3>Change Password</h3>
        <form onSubmit={handleChangePassword}>
          <div className="form-group">
            <label>Current Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your current password"
              required
            />
          </div>
          <div className="form-group">
            <label>New Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Enter your new password"
              required
            />
          </div>
          <button type="submit">Change Password</button>
        </form>
      </div>

      {/* Two-Factor Authentication Section */}
      <div className="section">
        <h3>Two-Factor Authentication (2FA)</h3>
        <button onClick={toggle2FA}>
          {is2FAEnabled ? "Disable 2FA" : "Enable 2FA"}
        </button>
        <p>{is2FAEnabled ? "2FA is enabled" : "2FA is disabled"}</p>
      </div>

      {/* Security Activity Section */}
      <div className="section">
        <h3>Recent Security Activity</h3>
        <ul>
          {activityLogs.map((log, index) => (
            <li key={index}>
              <strong>{log.date}</strong>: {log.action}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default Security;
