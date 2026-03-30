import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(undefined); // undefined = loading, null = logged out, obj = logged in

    useEffect(() => {
        fetch('/api/user/status')
            .then(res => {
                if (res.status === 401) { setUser(null); return null; }
                return res.json();
            })
            .then(data => {
                if (data && data.email) setUser(data);
                else if (data !== null) setUser(null);
            })
            .catch(() => setUser(null));
    }, []);

    const logout = () => {
        window.location.href = '/logout';
    };

    return (
        <AuthContext.Provider value={{ user, setUser, logout, loading: user === undefined }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    return useContext(AuthContext);
}
