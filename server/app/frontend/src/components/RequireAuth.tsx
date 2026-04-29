import { Navigate, Outlet, useLocation } from "react-router-dom";
import useAuth from "../hooks/useAuth";

const RequireAuth = ({ allowedRoles = [] }) => {
  const { auth } = useAuth();
  const location = useLocation();

  const userRoles = auth?.user?.roles || [];

  const hasAccess = Array.isArray(userRoles)
      ? userRoles.some((role) => allowedRoles.includes(role))
      : allowedRoles.includes(userRoles);

  return hasAccess ? (
      <Outlet />
  ) : (
      <Navigate to="/unauthorized" state={{ from: location }} replace />
  );
};

export default RequireAuth;
