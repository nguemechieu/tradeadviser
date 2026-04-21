import { axiosPrivate } from '../api/axios';
import useAuth from './useAuth';

const useRefreshToken = () => {
    const { auth, setAuth } = useAuth();

    return async () => {
        try {
            const response = await axiosPrivate.post('/api/auth/refresh', {
                refresh_token: auth?.refreshToken || localStorage.getItem('refreshToken'),
                remember_me: true
            });
            
            const { access_token, refresh_token, expires_in } = response.data;
            
            // Update auth context with new tokens
            setAuth(prev => ({
                ...prev,
                accessToken: access_token,
                refreshToken: refresh_token,
                expiresIn: expires_in
            }));
            
            // Persist tokens
            localStorage.setItem('accessToken', access_token);
            if (refresh_token) {
                localStorage.setItem('refreshToken', refresh_token);
            }
            
            return access_token;
        } catch (error) {
            console.error('Token refresh failed:', error);
            // Clear auth on refresh failure
            setAuth({});
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            throw error;
        }
    };
};

export default useRefreshToken;
