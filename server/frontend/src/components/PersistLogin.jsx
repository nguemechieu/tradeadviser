import { useEffect, useState } from 'react';
import useAuth from '../hooks/useAuth';
import { Outlet } from 'react-router-dom';

const PersistLogin = ({ children }) => {
    const { setAuth } = useAuth();
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const persistedAuth = localStorage.getItem('user');
        const accessToken = localStorage.getItem('accessToken');
        const refreshToken = localStorage.getItem('refreshToken');

        if (persistedAuth && accessToken) {
            try {
                const user = JSON.parse(persistedAuth);
                
                // Restore auth state from localStorage
                setAuth({
                    user: user.username,
                    email: user.email,
                    id: user.id,
                    display_name: user.display_name,
                    firstname: user.firstname,
                    lastname: user.lastname,
                    role: user.role,
                    accessToken: accessToken,
                    refreshToken: refreshToken,
                    tokenType: 'Bearer',
                    isLoggedIn: true
                });
            } catch (error) {
                console.error('Failed to restore auth state:', error);
                // Clear corrupted data
                localStorage.removeItem('user');
                localStorage.removeItem('accessToken');
                localStorage.removeItem('refreshToken');
            }
        }

        setIsLoading(false);
    }, [setAuth]);

    if (isLoading) {
        return (
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100vh',
                background: '#0a0e27',
                color: '#fff'
            }}>
                <div>Loading...</div>
            </div>
        );
    }

    return children || <Outlet />;
}

export default PersistLogin;