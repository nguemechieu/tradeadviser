import React, { useContext, useEffect, useState } from "react";
import { Outlet, Navigate } from "react-router-dom";
import AuthContext from "../context/AuthProvider";
import useRefreshToken from "../hooks/useRefreshToken";
import LoadingSpinner from "./LoadingSpinner";

const PersistLogin = () => {
  const { auth } = useContext(AuthContext);
  const refresh = useRefreshToken();
  const [loading, setLoading] = useState(true);
  const [refreshFailed, setRefreshFailed] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const verifyToken = async () => {
      if (!auth?.accessToken) {
        try {
          await refresh();
          if (isMounted) setLoading(false);
        } catch (err) {
          console.error("Token refresh failed:", err);
          if (isMounted) {
            setRefreshFailed(true);
            setLoading(false);
          }
        }
      } else {
        setLoading(false);
      }
    };

    verifyToken().then(r =>{} );

    return () => {
      isMounted = false;
    };
  }, [auth?.accessToken, refresh]);

  if (loading) return <LoadingSpinner />;

  return refreshFailed || !auth?.accessToken ? (
      <Navigate to="/login" replace />
  ) : (
      <Outlet />
  );
};

export default PersistLogin;
