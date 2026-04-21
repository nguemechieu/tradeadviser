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
    let userRole = auth?.role;
    
    // Fallback: extract role from localStorage if needed
    if (!userRole) {
        try {
            const savedUser = localStorage.getItem('tradeadviser-user');
            if (savedUser) {
                const parsed = JSON.parse(savedUser);
                userRole = parsed?.role || 'trader';
            }
        } catch (e) {
            console.error('Failed to parse user from localStorage:', e);
        }
    }
    
    // Default role to 'trader' if still not found
    userRole = userRole || 'trader';
    
    const hasAccess = userRole && (allowedRoles === undefined || allowedRoles.includes(userRole));

    // Also check token as fallback
    const hasToken = auth?.token || localStorage.getItem('tradeadviser-token');
    
    console.debug('RequireAuth check:', { userRole, allowedRoles, hasAccess, hasToken });

    return (
        hasAccess || (hasToken && userRole)
            ? <Outlet />
            : auth?.user
                ? <Navigate to="/access-denied" state={{ from: location }} replace />
                : <Navigate to="/login" state={{ from: location }} replace />
    );
}

export default RequireAuth;