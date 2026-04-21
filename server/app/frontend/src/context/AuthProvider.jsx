import { createContext, useState, useEffect } from "react";

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [auth, setAuth] = useState(() => {
        // Initialize from localStorage if available
        try {
            const savedToken = localStorage.getItem('tradeadviser-token');
            const savedUser = localStorage.getItem('tradeadviser-user');
            
            if (savedToken && savedUser) {
                const user = JSON.parse(savedUser);
                return {
                    token: savedToken,
                    user: user,
                    role: user.role || 'trader'
                };
            }
        } catch (error) {
            console.error('Failed to restore auth from storage:', error);
        }
        return {};
    });

    // Persist auth to localStorage whenever it changes
    useEffect(() => {
        if (auth?.token && auth?.user) {
            localStorage.setItem('tradeadviser-token', auth.token);
            localStorage.setItem('tradeadviser-user', JSON.stringify(auth.user));
        } else {
            localStorage.removeItem('tradeadviser-token');
            localStorage.removeItem('tradeadviser-user');
        }
    }, [auth]);

    const contextValue = {
        auth: auth || {},
        setAuth
    };

    return (
        <AuthContext.Provider value={contextValue}>
            {children}
        </AuthContext.Provider>
    )
}

export default AuthContext;