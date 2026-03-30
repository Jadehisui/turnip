import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    // undefined = still loading, null = not logged in, object = logged in user
    const [user, setUser] = useState(undefined);

    useEffect(() => {
        fetch('/api/user/status')
            .then(res => {
                if (res.status === 401) { setUser(null); return null; }
                return res.json();
            })
            .then(data => {
                if (data) setUser(data.email ? data : null);
            })
            .catch(() => setUser(null));
    }, []);

    const logout = () => { window.location.href = '/logout'; };

    return (
        <AuthContext.Provider value={{ user, setUser, logout, loading: user === undefined }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
