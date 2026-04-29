import { Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";

import { Button } from "@mui/material";
import React from "react";
import {axiosPrivate} from "../api/axiosPrivate";

const ResetPassword= () => {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errMsg, setErrMsg] = useState("");
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState("");

  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/";

  const tokenRef = useRef(null);

  useEffect(() => {
    tokenRef.current?.focus();
  }, []);

  const resetPassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    setSuccess(false);
    setErrMsg("");

    try {
      const response = await axiosPrivate.post(
        "/api/v3/reset-password",
        JSON.stringify({ resetToken: token, password }),
      );

      if (response.status === 200) {
        setSuccess(true);
        navigate(from);
      }
    } catch (response) {
      if (response?.status === 400) {
        setErrMsg(response?.data.message);
      } else if (response?.status === 401) {
        setErrMsg("Invalid or expired reset token.");
      } else if (response?.status === 403) {
        setErrMsg("Unauthorized access.");
      } else {
        setErrMsg("An error occurred while resetting your password.");
      }
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    if (name === "password") {
      setPassword(value);
    } else if (name === "confirmPassword") {
      setConfirmPassword(value);
    } else if (name === "token") {
      setToken(value);
    }
  };

  return (
    <div>
      <h1>Reset Password</h1>
      {errMsg && <div className="error">{errMsg}</div>}
      {success && <div className="success">Password reset successful!</div>}
      <form onSubmit={resetPassword}>
        <input
          type="password"
          name="password"
          placeholder="New Password"
          value={password}
          onChange={handleInputChange}
        />
        <input
          type="password"
          name="confirmPassword"
          placeholder="Confirm New Password"
          value={confirmPassword}
          onChange={handleInputChange}
        />
        <input
          type="text"
          name="token"
          placeholder="Token (from email)"
          value={token}
          ref={tokenRef}
          onChange={handleInputChange}
        />
        <Button type="submit" disabled={loading}>
          {loading ? "Resetting Password..." : "Reset Password"}
        </Button>

        <div className="link">
          <Link to={from} className="back-link">
            Go Back
          </Link>
        </div>
      </form>
    </div>
  );
};

export default ResetPassword;
