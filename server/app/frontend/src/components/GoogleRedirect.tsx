import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import useAuth from "../hooks/useAuth";
import {axiosPrivate} from "../api/axiosPrivate";


const GoogleRedirect = () => {
  const { setAuth } = useAuth();
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const handleGoogleResponse = async () => {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");

      if (!code) {
        setError("Google authentication failed. Please try again.");
        navigate("/login");
        return;
      }

      try {
        const response = await axiosPrivate.post("/api/v3/auth/google/callback", { code });
        const data = response.data;

        if (response.status === 200 && data.user) {
          setAuth(data.user);
          navigate("/", { replace: true });
        } else {
          new Error("Authentication failed.");
        }
      } catch (err) {
        console.error("Error handling Google login:", err);
        setError("Failed to authenticate with Google. Please try again.");
        navigate("/login");
      }
    };

    handleGoogleResponse();
  }, [navigate, setAuth]);

  return (
      <div>
        <h1>Redirecting...</h1>
        <p>{error || "Please wait while we process your Google login."}</p>
      </div>
  );
};

export default GoogleRedirect;
