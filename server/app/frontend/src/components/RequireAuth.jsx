import { useLocation, Navigate, Outlet } from "react-router-dom";
import { useContext, useEffect, useState } from "react";
import AuthContext from "../context/AuthProvider";

const RequireAuth = ({ allowedRoles }) => {
    const context = useContext(AuthContext);
    const { auth } = context || {};
    const location = useLocation();
    const [isInitialized, setIsInitialized] = useState(false);

    useEffect(() => {
        // Give the context time to initialize from localStorage if needed
        setIsInitialized(true);
    }, []);

    if (!isInitialized) {
        return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0a0e27', color: '#fff' }}>Loading...</div>;
    }

    // Check if user has a role
    const userRole = auth?.role;
    const hasAccess = userRole && (allowedRoles === undefined || allowedRoles.includes(userRole));

    // Also check token as fallback
    const hasToken = auth?.token || localStorage.getItem('tradeadviser-token');

    return (
        hasAccess || (hasToken && userRole)
            ? <Outlet />
            : auth?.user
                ? <Navigate to="/access-denied" state={{ from: location }} replace />
                : <Navigate to="/login" state={{ from: location }} replace />
    );
}

export default RequireAuth;