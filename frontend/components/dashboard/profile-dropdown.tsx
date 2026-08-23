'use client';

import { useState, useRef, useEffect } from 'react';
import { LogOut, Settings, MonitorPlay } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

interface ProfileDropdownProps {
  onSettingsClick: () => void;
}

export default function ProfileDropdown({ onSettingsClick }: ProfileDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const { user, logout, isDemoMode, toggleDemoMode } = useAuth();

  // Extract user info from Firebase user
  const displayName = user?.displayName || user?.email?.split('@')[0] || 'User';
  const email = user?.email || '';

  // Create avatar initials from display name or email
  const getInitials = (name: string) => {
    const parts = name.split(' ');
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  };

  const avatar = getInitials(displayName);

  // Farm name based on user type and demo mode
  const isDemoUser = email.toLowerCase() === 'demo@chaitea.com';
  const farmName = isDemoMode || isDemoUser ? 'Demo Tea Estate (View Only)' : 'My Tea Farm';

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout error:', error);
      // Fallback: redirect to login anyway
      window.location.href = '/login';
    }
  };

  const handleSettings = () => {
    onSettingsClick();
    setIsOpen(false);
  };

  const handleToggleDemo = () => {
    toggleDemoMode();
  };

  // Don't render if no user
  if (!user) return null;

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Avatar Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center justify-center h-10 w-10 rounded-full transition-colors font-semibold text-sm cursor-pointer hover:shadow-lg ${isDemoMode
          ? 'bg-amber-500 hover:bg-amber-600 text-white ring-2 ring-amber-300 ring-offset-2'
          : 'bg-primary hover:bg-primary/90 text-primary-foreground'
          }`}
        title={displayName}
      >
        {avatar}
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-72 bg-card border border-border rounded-lg shadow-lg z-50 animate-in fade-in slide-in-from-top-2 duration-200">
          {/* User Info Section */}
          <div className="p-4 border-b border-border">
            <div className="flex items-start gap-3">
              <div className={`h-10 w-10 rounded-full flex items-center justify-center font-semibold text-sm flex-shrink-0 ${isDemoMode ? 'bg-amber-500 text-white' : 'bg-primary text-primary-foreground'
                }`}>
                {avatar}
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold text-foreground truncate">{displayName}</h3>
                <p className="text-xs text-muted-foreground truncate">{email}</p>
                <p className={`text-xs mt-1 font-medium ${isDemoMode ? 'text-amber-600 dark:text-amber-400' : 'text-muted-foreground'}`}>
                  {farmName}
                </p>
              </div>
            </div>
          </div>

          {/* Menu Items */}
          <div className="py-2">
            {/* Demo Mode Toggle */}
            <button
              onClick={handleToggleDemo}
              className="w-full px-4 py-2 text-left text-sm hover:bg-muted transition-colors flex items-center gap-3 mb-1"
            >
              <div className={`flex items-center justify-center h-4 w-4 rounded-full ${isDemoMode ? 'bg-amber-500 text-white shadow-sm' : 'text-muted-foreground border border-muted-foreground/30'}`}>
                {isDemoMode && <MonitorPlay className="h-2.5 w-2.5" />}
              </div>
              <span className={isDemoMode ? 'font-medium text-amber-600 dark:text-amber-400' : 'text-foreground'}>
                {isDemoMode ? 'Demo Mode Active' : 'View Demo Data'}
              </span>
            </button>

            {/* Settings */}
            <button
              onClick={handleSettings}
              className="w-full px-4 py-2 text-left text-sm text-foreground hover:bg-muted transition-colors flex items-center gap-3"
            >
              <Settings className="h-4 w-4 text-muted-foreground" />
              <span>Account Settings</span>
            </button>
          </div>

          {/* Divider */}
          <div className="border-t border-border" />

          {/* Logout */}
          <div className="p-2">
            <button
              onClick={handleLogout}
              className="w-full px-4 py-2 text-left text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors rounded flex items-center gap-3 font-medium"
            >
              <LogOut className="h-4 w-4" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
