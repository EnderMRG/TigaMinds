'use client';

import { useEffect, useState } from 'react';
import { Download, X, Smartphone } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useLanguage } from '@/context/LanguageContext';

export default function PwaInstaller() {
  const { language } = useLanguage();
  const [installPrompt, setInstallPrompt] = useState<any>(null);
  const [isStandalone, setIsStandalone] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Check if already installed / running in standalone mode
    if (typeof window !== 'undefined') {
      const isPWA = window.matchMedia('(display-mode: standalone)').matches ||
                    (window.navigator as any).standalone === true;
      setIsStandalone(isPWA);

      // Register service worker
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker
          .register('/sw.js')
          .then((reg) => {
            console.log('✅ CHAI-NET PWA ServiceWorker registered with scope:', reg.scope);
          })
          .catch((err) => {
            console.warn('⚠️ CHAI-NET PWA ServiceWorker registration failed:', err);
          });
      }

      // Listen for install prompt
      const handleBeforeInstall = (e: Event) => {
        e.preventDefault();
        setInstallPrompt(e);
      };

      window.addEventListener('beforeinstallprompt', handleBeforeInstall);

      return () => {
        window.removeEventListener('beforeinstallprompt', handleBeforeInstall);
      };
    }
  }, []);

  const handleInstallClick = async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    const { outcome } = await installPrompt.userChoice;
    if (outcome === 'accepted') {
      setInstallPrompt(null);
    }
  };

  // Don't render banner if already installed, dismissed, or no prompt available
  if (isStandalone || dismissed || !installPrompt) {
    return null;
  }

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-6 md:w-96 z-50 animate-in fade-in slide-in-from-bottom-5 duration-300">
      <div className="bg-background/95 backdrop-blur-md border border-primary/30 rounded-2xl p-4 shadow-2xl shadow-primary/10 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary flex-shrink-0">
            <Smartphone className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-bold text-foreground">
              {language === 'as' ? 'CHAI-NET এপ ইনষ্টল কৰক' : 'Install CHAI-NET App'}
            </p>
            <p className="text-xs text-muted-foreground">
              {language === 'as'
                ? 'দ্ৰুত প্ৰৱেশ আৰু অফলাইন কাৰ্যক্ষমতাৰ বাবে'
                : 'Fast offline access & live crop monitoring'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 flex-shrink-0">
          <Button
            size="sm"
            onClick={handleInstallClick}
            className="h-8 px-3 text-xs bg-primary hover:bg-primary/90 text-primary-foreground font-semibold rounded-lg"
          >
            <Download className="h-3.5 w-3.5 mr-1" />
            {language === 'as' ? 'ইনষ্টল' : 'Install'}
          </Button>
          <button
            onClick={() => setDismissed(true)}
            className="h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            aria-label="Dismiss"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
