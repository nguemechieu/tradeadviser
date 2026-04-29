import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import useAuth from "../hooks/useAuth";
import {axiosPrivate} from "../api/axiosPrivate";

const GitHubRedirect = () => {
  const { setAuth } = useAuth(); // Custom hook to manage authentication
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true); // Loading state
  const navigate = useNavigate();

  useEffect(() => {
    const handleOAuthCallback = async (event) => {
      // Verify event origin for security
      if (event.origin !== window.location.origin) {
        console.warn("Ignored message from unknown origin:", event.origin);
        return;
      }

      try {
        const params = new URLSearchParams(event.data );


        console.log("params received "+event.data.code)
        const code = params.get("code");

        if (!code) {
          setError("Authorization code missing. Redirecting to login...");
          setTimeout(() => navigate("/login"), 3000);
          return;
        }

        // Send the authorization code to your backend
        const response = await axiosPrivate.post("/api/v3/auth/github/callback", { params });

        if (response.status === 200 && response.data) {
          const data = response.data;
          console.log("User authenticated successfully:", data);

          // Set authentication context and redirect
          setAuth(data);
          navigate("/", { replace: true });
        } else {
           new Error("Invalid response from server.");
        }
      } catch (err) {
        console.error("GitHub authentication error:", err);
        setError("Failed to authenticate with GitHub. Please try again.");
        setTimeout(() => navigate("/login"), 2000);
      } finally {
        setLoading(false);
      }
    };

    // Add the message event listener for the OAuth callback
    window.addEventListener("message", handleOAuthCallback);

    // Cleanup the event listener when component unmounts
    return () => {
      window.removeEventListener("message", handleOAuthCallback);
    };
  }, [setAuth, navigate]);

  return (
      <div>
        <h1>Redirecting to GitHub...</h1>
        {loading && <p>Please wait while we authenticate you with GitHub.</p>}
        {error && <p style={{ color: "red" }}>{error}</p>}
      </div>
  );
};

export default GitHubRedirect;
