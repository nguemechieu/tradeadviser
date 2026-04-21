import { useEffect, useContext, useState } from 'react';
import { Outlet } from 'react-router-dom';
import AuthContext from '../context/AuthProvider';

const PersistLogin = () => {
    const { auth, setAuth } = useContext(AuthContext);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        // The AuthProvider now handles persistence, but we can verify the token is valid
        if (auth?.token) {
            // Token exists, component can proceed
            setIsLoading(false);
        } else {
            // No auth, proceed anyway - login page will handle redirect
            setIsLoading(false);
        }
    }, [auth]);

    if (isLoading) {
        return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: '#0a0e27', color: '#fff' }}>Loading...</div>;
    }

    return <Outlet />;
};

export default PersistLogin;