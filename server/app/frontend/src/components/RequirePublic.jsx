import { Navigate, Outlet } from "react-router-dom";
import useAuth from "../hooks/useAuth";

/**
 * RequirePublic - Guards public-only routes (login, register)
 * Redirects authenticated users to dashboard to prevent them from seeing auth pages
 */
const RequirePublic = () => {
    const { auth } = useAuth();

    // Check if user is logged in
    const isLoggedIn = auth?.isLoggedIn || auth?.accessToken;

    if (isLoggedIn) {
        // User is already logged in - redirect to dashboard
        return <Navigate to="/dashboard" replace />;
    }

    // User is not logged in - allow access to public routes
    return <Outlet />;
}

export default RequirePublic;
