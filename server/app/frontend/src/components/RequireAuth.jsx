import { useLocation, Navigate, Outlet } from "react-router-dom";
import useAuth from "../hooks/useAuth";

const RequireAuth = ({ allowedRoles }) => {
    const { auth } = useAuth();
    const location = useLocation();

    // Check if user is logged in
    const isLoggedIn = auth?.isLoggedIn || auth?.accessToken;
    
    // Check if user has one of the allowed roles
    const userRole = auth?.user?.role || auth?.role;
    const hasRequiredRole = !allowedRoles || allowedRoles.length === 0 || allowedRoles.includes(userRole);

    if (!isLoggedIn) {
        // User not logged in - redirect to login
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    if (!hasRequiredRole) {
        // User logged in but doesn't have required role - redirect to access denied
        return <Navigate to="/access-denied" state={{ from: location }} replace />;
    }

    // User is logged in and has required role
    return <Outlet />;
}

export default RequireAuth;