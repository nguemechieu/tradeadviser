import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import {Card} from "@mui/material";
import { axiosPrivate } from "../api/axios";

const ForgotPassword = () => {
  const [email, setEmail] = useState("");
  const [success, setSuccess] = useState(false);
  const [errMsg, setErrMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const location = useLocation();
  const from = location.state?.from?.pathname || "/";

  const isValidEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  useEffect(() => {
    if (isValidEmail) {
      setErrMsg("");
    } else if (email) {
      setErrMsg("Invalid email address");
    }
  }, [email, isValidEmail]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setLoading(true);
    setSuccess(false);
    setErrMsg("");

     await axiosPrivate.post("/api/v3/auth/forgot/password", JSON.stringify({ email:email }), {
        headers: { "Content-Type": "application/json" },
      })
      .then((response) => {
        setErrMsg(JSON.stringify(response));
        setSuccess(true);
        setLoading(false);
      })
      .catch((error) => {
        setErrMsg(JSON.stringify( error));
        setLoading(false);
      });
  };

  return (<>
    <Card className={'section'}>
      <h2>Forgot Password</h2>


      {errMsg && <p className="error-message">{errMsg}</p>}
      {success && (
        <p className="success-message">
          Check your email for further instructions.
        </p>
      )}

      {!success && (
        <form
          onSubmit={(e) => handleSubmit(e)}
          className="forgot-password-form"
        >
          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input
              type="email"
              id="email"
              name="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              aria-invalid={!isValidEmail}
              placeholder="Enter your email address"
              autoComplete="email"
              pattern="^[^\s@]+@[^\s@]+\.[^\s@]+$"
              title="Please enter a valid email address."
            />
          </div>

          <button
            type="submit"
            className="submit-button"
            disabled={loading || !isValidEmail}
          >
            {loading ? "Sending..." : "Send Password Reset"}
            {loading && <span className="spinner"></span>}
          </button>
        </form>
      )}

      <Link to={from} className="back-link">
        Go Back
      </Link>
    </Card>
    </>
  );
};

export default ForgotPassword;
