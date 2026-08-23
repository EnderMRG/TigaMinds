'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Leaf, Menu, X, Send } from 'lucide-react';
import CultivationIntelligence from '@/components/dashboard/cultivation-intelligence';
import LeafQualityScanner from '@/components/dashboard/leaf-quality-scanner';
import FarmerActionSimulator from '@/components/dashboard/farmer-action-simulator';
import MarketIntelligence from '@/components/dashboard/market-intelligence';
import ChatbotBubble from '@/components/dashboard/chatbot-bubble';
import ProfileDropdown from '@/components/dashboard/profile-dropdown';
import AccountSettings from '@/components/dashboard/account-settings';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { LanguageToggle } from '@/components/language-toggle';
import { useLanguage } from '@/context/LanguageContext';
import { apiClient } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState('cultivation');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sendingAlert, setSendingAlert] = useState(false);
  const { t } = useLanguage();
  const { toast } = useToast();

  const handleSendAlert = async () => {
    setSendingAlert(true);
    try {
      const response = await apiClient.post('/api/send-sms', {
        phone: '+917002168639',
        message: 'আজকে কাজ আছে',
      });

      if (response.success) {
        toast({
          title: 'Success',
          description: 'Worker alert sent successfully!',
        });
      } else {
        toast({
          title: 'Error',
          description: response.error || 'Failed to send alert',
          variant: 'destructive',
        });
      }
    } catch (error) {
      console.error('Error sending alert:', error);
      toast({
        title: 'Error',
        description: 'Failed to send worker alert',
        variant: 'destructive',
      });
    } finally {
      setSendingAlert(false);
    }
  };

  const tabs = [
    {
      id: 'cultivation',
      label: t('cultivationIntelligence'),
      description: t('realtimeIotMonitoring'),
    },
    {
      id: 'leaf-quality',
      label: t('leafQualityScanner'),
      description: t('aiPoweredGrading'),
    },
    {
      id: 'action',
      label: t('actionSimulator'),
      description: t('simulateActionBeforeOutcome'),
    },
    {
      id: 'market',
      label: t('marketIntelligence'),
      description: t('priceForecastingTrends'),
    },
    {
      id: 'settings',
      label: t('accountSettings'),
      description: t('manageYourProfile'),
    },
  ];

  return (
    <ProtectedRoute>
      <div className="flex h-screen bg-background overflow-hidden">
        {/* Sidebar */}
        <div
          className={`fixed inset-y-0 left-0 z-50 w-64 border-r border-border bg-card transition-transform duration-300 ease-in-out ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'
            } lg:relative lg:translate-x-0`}
        >
          <div className="flex flex-col h-full">
            <div className="flex items-center justify-between p-6 border-b border-border">
              <Link href="/" className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
                  <Leaf className="h-5 w-5 text-primary-foreground" />
                </div>
                <span className="font-bold text-foreground">CHAI-NET</span>
              </Link>
              <button
                onClick={() => setSidebarOpen(false)}
                className="lg:hidden text-muted-foreground hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <nav className="flex-1 space-y-2 p-4">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id);
                    setSidebarOpen(false);
                  }}
                  className={`w-full text-left px-4 py-3 rounded-lg transition-colors ${activeTab === tab.id
                    ? 'bg-primary text-primary-foreground'
                    : 'text-foreground hover:bg-muted'
                    }`}
                >
                  <div className="font-medium">{tab.label}</div>
                  <div className="text-xs opacity-75 mt-1">{tab.description}</div>
                </button>
              ))}
              <button
                onClick={handleSendAlert}
                disabled={sendingAlert}
                className="w-full mt-4 flex items-center gap-2 px-4 py-3 rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
              >
                <Send className="h-4 w-4" />
                <span className="font-medium">
                  {sendingAlert ? 'Sending...' : 'Send Worker Alert'}
                </span>
              </button>
            </nav>

            <div className="p-4 border-t border-border">
              <Link href="/">
                <Button variant="outline" size="sm" className="w-full bg-transparent">
                  {t('backToHome')}
                </Button>
              </Link>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Top Bar */}
          <div className="border-b border-border bg-card h-16 flex items-center justify-between px-6">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden text-foreground hover:text-muted-foreground"
              >
                <Menu className="h-6 w-6" />
              </button>
              <h1 className="text-xl font-bold text-foreground">{t('dashboard')}</h1>
            </div>
            <div className="flex items-center gap-4">
              <div className="text-sm text-muted-foreground">
                {new Date().toLocaleDateString('en-US', {
                  weekday: 'long',
                  month: 'long',
                  day: 'numeric',
                })}
              </div>
              <LanguageToggle />
              <ProfileDropdown onSettingsClick={() => setActiveTab('settings')} />
            </div>
          </div>

          {/* Content Area */}
          <div className="flex-1 overflow-auto">
            <div className="p-6">
              {activeTab === 'cultivation' && <CultivationIntelligence />}
              {activeTab === 'leaf-quality' && <LeafQualityScanner />}
              {activeTab === 'action' && <FarmerActionSimulator />}
              {activeTab === 'market' && <MarketIntelligence />}
              {activeTab === 'settings' && <AccountSettings />}
            </div>
          </div>
        </div>
        <ChatbotBubble />
      </div>
    </ProtectedRoute>
  );
}
