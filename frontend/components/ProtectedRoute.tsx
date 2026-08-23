'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
    const { user, loading } = useAuth();
    const router = useRouter();

    useEffect(() => {
        console.log('🛡️ ProtectedRoute check:', { loading, hasUser: !!user, email: user?.email });

        if (!loading && !user) {
            console.log('❌ No user, redirecting to login');
            router.push('/login');
        } else if (!loading && user) {
            console.log('✅ User authenticated, showing dashboard');
        }
    }, [user, loading, router]);

    if (loading) {
        console.log('⏳ Loading auth state...');
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="text-center">
                    <div className="h-8 w-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                    <p className="text-muted-foreground">Loading...</p>
                </div>
            </div>
        );
    }

    if (!user) {
        console.log('🚫 No user after loading, returning null');
        return null;
    }

    console.log('✅ Rendering protected content for:', user.email);
    return <>{children}</>;
}
