import React from "react";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

const LogOut = () => {
  const navigate = useNavigate();

  useEffect(() => {
    // Perform logout logic here
    localStorage.removeItem("accessToken");
    localStorage.removeItem("session");
    localStorage.removeItem("persist");

    // Redirect to the login page after a short delay
    const timer = setTimeout(() => {
      navigate("/login");
    }, 2000);

    // Clean up the timer on a component unmount
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div style={{ textAlign: "center", marginTop: "20%" }}>
      <h1>Logging Out...</h1>
      <p>Please wait while we log you out.</p>
      <p>Redirecting to the login page...</p>
    </div>
  );
};

export default LogOut;
