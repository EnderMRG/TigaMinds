'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import {
    User,
    signInWithPopup,
    signOut as firebaseSignOut,
    onAuthStateChanged,
    setPersistence,
    browserLocalPersistence,
} from 'firebase/auth';
import { auth, googleProvider } from '@/lib/firebase';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api';

interface AuthContextType {
    user: User | null;
    loading: boolean;
    signInWithGoogle: () => Promise<void>;
    logout: () => Promise<void>;
    getIdToken: () => Promise<string | null>;
    isDemoMode: boolean;
    toggleDemoMode: () => void;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    loading: true,
    signInWithGoogle: async () => { },
    logout: async () => { },
    getIdToken: async () => null,
    isDemoMode: false,
    toggleDemoMode: () => { },
});

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [loading, setLoading] = useState(true);
    const [isDemoMode, setIsDemoMode] = useState(false);
    const router = useRouter();

    // Get ID token from current auth user (not from state)
    const getIdToken = async (): Promise<string | null> => {
        if (isDemoMode || localStorage.getItem('chai_demo_mode') === 'true') {
            return "demo_token";
        }
        const currentUser = auth.currentUser;
        if (!currentUser) {
            return null;
        }
        try {
            const token = await currentUser.getIdToken();
            return token;
        } catch (error) {
            console.error('❌ Error getting ID token:', error);
            return null;
        }
    };

    const toggleDemoMode = () => {
        const newMode = !isDemoMode;
        setIsDemoMode(newMode);
        // Persist to local storage
        localStorage.setItem('chai_demo_mode', String(newMode));
        // Reload to refresh all data
        window.location.reload();
    };

    useEffect(() => {
        // Load demo mode preference
        const savedDemo = localStorage.getItem('chai_demo_mode') === 'true';
        setIsDemoMode(savedDemo);

        // Configure API client with header injector
        apiClient.setHeaderInjector(() => {
            if (savedDemo) {
                return { 'X-Force-Demo': 'true' };
            }
            return {};
        });

        // Enable persistence to keep user logged in
        setPersistence(auth, browserLocalPersistence)
            .catch((error) => {
                console.error('❌ Failed to enable persistence:', error);
            });

        // Configure API client with token getter
        apiClient.setTokenGetter(getIdToken);
        console.log('🔧 API client configured with token getter');

        const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
            if (savedDemo) {
                console.log('🎭 Demo mode active. Mocking user.');
                setUser({ email: 'demo@chaitea.com', uid: 'demo123', displayName: 'Demo User' } as any);
                setLoading(false);
            } else {
                console.log('🔐 Auth state changed:', firebaseUser ? firebaseUser.email : 'No user');
                setUser(firebaseUser);
                setLoading(false);
            }
        });

        return () => unsubscribe();
    }, [router]);

    const signInWithGoogle = async () => {
        try {
            console.log('🔑 Starting Google sign-in with popup...');
            const result = await signInWithPopup(auth, googleProvider);
            console.log('✅ Sign-in successful:', result.user.email);
            router.push('/dashboard');
        } catch (error: any) {
            console.error('❌ Error signing in with Google:', error);
            if (error.code === 'auth/popup-blocked') {
                alert('Popup was blocked! Please allow popups for this site and try again.');
            }
            throw error;
        }
    };

    const logout = async () => {
        try {
            await firebaseSignOut(auth);
            router.push('/login');
        } catch (error) {
            console.error('Error signing out:', error);
            throw error;
        }
    };

    const value = {
        user,
        loading,
        signInWithGoogle,
        logout,
        getIdToken,
        isDemoMode,
        toggleDemoMode,
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
