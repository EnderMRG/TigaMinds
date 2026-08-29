"use client";

import React, { createContext, useContext, useState, useCallback, useRef } from "react";

export type AlertSeverity = 'info' | 'warning' | 'critical';

export interface Alert {
  id: string;
  title: string;
  message: string;
  severity: AlertSeverity;
  source: string;
  timestamp: Date;
  read: boolean;
}

interface AlertsContextValue {
  alerts: Alert[];
  unreadCount: number;
  addAlert: (alert: Omit<Alert, 'id' | 'timestamp' | 'read'>) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
  clearAll: () => void;
}

const AlertsContext = createContext<AlertsContextValue | null>(null);

export function AlertsProvider({ children }: { children: React.ReactNode }) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const lastFiredRef = useRef<Record<string, number>>({});

  const addAlert = useCallback((alert: Omit<Alert, 'id' | 'timestamp' | 'read'>) => {
    const now = Date.now();
    const DEDUP_WINDOW_MS = 10 * 60 * 1000;
    if (lastFiredRef.current[alert.source] && now - lastFiredRef.current[alert.source] < DEDUP_WINDOW_MS) {
      return;
    }
    lastFiredRef.current[alert.source] = now;
    const newAlert: Alert = {
      ...alert,
      id: alert.source + '-' + now,
      timestamp: new Date(now),
      read: false,
    };
    setAlerts((prev) => [newAlert, ...prev].slice(0, 50));
    if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator && 'PushManager' in window) {
      navigator.serviceWorker.ready.then(async (reg) => {
        const sub = await reg.pushManager.getSubscription();
        if (!sub) return;
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const subJson = sub.toJSON();
        try {
          await fetch(API_BASE + '/api/push/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              endpoint: sub.endpoint,
              keys: { p256dh: subJson.keys?.p256dh, auth: subJson.keys?.auth },
              title: newAlert.title,
              body: newAlert.message,
            }),
          });
        } catch {}
      });
    }
  }, []);

  const markRead = useCallback((id: string) => {
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, read: true } : a)));
  }, []);

  const markAllRead = useCallback(() => {
    setAlerts((prev) => prev.map((a) => ({ ...a, read: true })));
  }, []);

  const clearAll = useCallback(() => setAlerts([]), []);

  const unreadCount = alerts.filter((a) => !a.read).length;

  return (
    <AlertsContext.Provider value={{ alerts, unreadCount, addAlert, markRead, markAllRead, clearAll }}>
      {children}
    </AlertsContext.Provider>
  );
}

export function useAlerts() {
  const ctx = useContext(AlertsContext);
  if (!ctx) throw new Error('useAlerts must be used within AlertsProvider');
  return ctx;
}
