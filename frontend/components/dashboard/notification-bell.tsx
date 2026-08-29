'use client';

import { useRef, useState, useEffect } from 'react';
import { Bell, X, CheckCheck, Trash2, AlertTriangle, Info, ShieldAlert } from 'lucide-react';
import { useAlerts, type Alert, type AlertSeverity } from '@/context/alerts-context';

function timeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return date.toLocaleDateString();
}

const severityConfig: Record<AlertSeverity, { icon: React.ReactNode; border: string; bg: string; badge: string; text: string }> = {
  critical: {
    icon: <ShieldAlert className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />,
    border: 'border-l-red-500',
    bg: 'bg-red-50 dark:bg-red-950/30',
    badge: 'bg-red-500',
    text: 'text-red-700 dark:text-red-300',
  },
  warning: {
    icon: <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />,
    border: 'border-l-amber-500',
    bg: 'bg-amber-50 dark:bg-amber-950/30',
    badge: 'bg-amber-500',
    text: 'text-amber-700 dark:text-amber-300',
  },
  info: {
    icon: <Info className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />,
    border: 'border-l-blue-500',
    bg: 'bg-blue-50 dark:bg-blue-950/30',
    badge: 'bg-blue-500',
    text: 'text-blue-700 dark:text-blue-300',
  },
};

function AlertItem({ alert, onRead }: { alert: Alert; onRead: (id: string) => void }) {
  const cfg = severityConfig[alert.severity];
  return (
    <div
      onClick={() => onRead(alert.id)}
      className={`flex gap-3 p-3 border-l-2 rounded-r-lg cursor-pointer transition-all duration-200 hover:brightness-95 ${cfg.border} ${cfg.bg} ${alert.read ? 'opacity-60' : ''}`}
    >
      {cfg.icon}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p className={`text-xs font-semibold leading-tight ${cfg.text}`}>{alert.title}</p>
          {!alert.read && (
            <span className={`shrink-0 w-1.5 h-1.5 rounded-full mt-1 ${cfg.badge}`} />
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{alert.message}</p>
        <p className="text-[10px] text-muted-foreground/60 mt-1">{timeAgo(alert.timestamp)}</p>
      </div>
    </div>
  );
}

export default function NotificationBell() {
  const { alerts, unreadCount, markRead, markAllRead, clearAll } = useAlerts();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const handleOpen = () => {
    setOpen((prev) => !prev);
    if (!open && unreadCount > 0) {
      // Small delay so user sees badge before it clears
      setTimeout(markAllRead, 800);
    }
  };

  return (
    <div ref={ref} className="relative">
      {/* Bell button */}
      <button
        id="notification-bell-btn"
        onClick={handleOpen}
        className="relative p-2 rounded-full hover:bg-muted transition-colors focus:outline-none focus:ring-2 focus:ring-primary/40"
        aria-label="Notifications"
      >
        <Bell className={`h-5 w-5 ${unreadCount > 0 ? 'text-foreground' : 'text-muted-foreground'}`} />
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white animate-pulse">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-xl border border-border bg-card shadow-2xl z-[999] overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/40">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-primary" />
              <span className="text-sm font-semibold text-foreground">Alerts</span>
              {unreadCount > 0 && (
                <span className="text-xs bg-red-500 text-white rounded-full px-1.5 py-0.5 font-medium">
                  {unreadCount} new
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              {alerts.length > 0 && (
                <>
                  <button
                    onClick={markAllRead}
                    className="p-1.5 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                    title="Mark all read"
                  >
                    <CheckCheck className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={clearAll}
                    className="p-1.5 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-destructive"
                    title="Clear all"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </>
              )}
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-md hover:bg-muted transition-colors text-muted-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Alert list */}
          <div className="max-h-[420px] overflow-y-auto">
            {alerts.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 gap-3 text-muted-foreground">
                <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center">
                  <Bell className="h-6 w-6 opacity-40" />
                </div>
                <p className="text-sm font-medium">All clear</p>
                <p className="text-xs text-center px-6 opacity-70">No alerts right now. Thresholds are being monitored.</p>
              </div>
            ) : (
              <div className="p-2 space-y-1.5">
                {alerts.map((alert) => (
                  <AlertItem key={alert.id} alert={alert} onRead={markRead} />
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          {alerts.length > 0 && (
            <div className="px-4 py-2 border-t border-border bg-muted/20 text-center">
              <p className="text-[10px] text-muted-foreground">
                Alerts auto-deduped · last 10 min window
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
