'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Leaf, Menu, X, Send, Activity, Scan, Zap, TrendingUp, MoreHorizontal, Satellite, ShieldCheck, Cpu, Settings } from 'lucide-react';
import CultivationIntelligence from '@/components/dashboard/cultivation-intelligence';
import LeafQualityScanner from '@/components/dashboard/leaf-quality-scanner';
import FarmerActionSimulator from '@/components/dashboard/farmer-action-simulator';
import MarketIntelligence from '@/components/dashboard/market-intelligence';
import SatelliteCropHealth from '@/components/dashboard/satellite-crop-health';
import DigitalTwin from '@/components/dashboard/digital-twin';
import ChatbotBubble from '@/components/dashboard/chatbot-bubble';
import ProfileDropdown from '@/components/dashboard/profile-dropdown';
import AccountSettings from '@/components/dashboard/account-settings';
import SubsidyInsuranceNavigator from '@/components/dashboard/subsidy-insurance-navigator';
import NotificationBell from '@/components/dashboard/notification-bell';
import { AlertsProvider } from '@/context/alerts-context';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { LanguageToggle } from '@/components/language-toggle';
import { useLanguage } from '@/context/LanguageContext';
import { apiClient } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState('cultivation');
  const [sidebarOpen, setSidebarOpen] = useState(false);
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

      if (response) {
        toast({
          title: 'Alert Sent',
          description: 'Worker alert notification sent successfully.',
        });
      }
    } catch (error) {
      console.error('Failed to send alert:', error);
      toast({
        title: 'Error',
        description: 'Failed to send worker alert. Please try again.',
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
      icon: Activity,
    },
    {
      id: 'leaf-quality',
      label: t('leafQualityScanner'),
      description: t('aiPoweredGrading'),
      icon: Scan,
    },
    {
      id: 'action',
      label: t('actionSimulator'),
      description: t('simulateActionBeforeOutcome'),
      icon: Zap,
    },
    {
      id: 'market',
      label: t('marketIntelligence'),
      description: t('priceForecastingTrends'),
      icon: TrendingUp,
    },
    {
      id: 'satellite',
      label: t('satelliteCropHealth'),
      description: t('satelliteCropHealthDesc'),
      icon: Satellite,
    },
    {
      id: 'subsidies',
      label: t('subsidyNavigator'),
      description: t('subsidyNavigatorDesc'),
      icon: ShieldCheck,
    },
    {
      id: 'digital-twin',
      label: t('digitalTwin'),
      description: t('digitalTwinDesc'),
      icon: Cpu,
    },
    {
      id: 'settings',
      label: t('accountSettings'),
      description: t('manageYourProfile'),
      icon: Settings,
    },
  ];

  const mobileNavItems = [
    { id: 'cultivation', label: t('cultivationIntelligence').split(' ')[0], icon: Activity },
    { id: 'leaf-quality', label: t('leafQualityScanner').split(' ')[0], icon: Scan },
    { id: 'action', label: t('actionSimulator').split(' ')[0], icon: Zap },
    { id: 'market', label: t('marketIntelligence').split(' ')[0], icon: TrendingUp },
  ];

  return (
    <ProtectedRoute>
      <AlertsProvider>
        <div className="flex h-screen bg-background overflow-hidden relative">
          
          {sidebarOpen && (
            <div
              onClick={() => setSidebarOpen(false)}
              className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden transition-opacity duration-300 animate-in fade-in"
              aria-label="Close sidebar overlay"
            />
          )}

          <div
            className={`fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] border-r border-border bg-card shadow-2xl lg:shadow-none transition-transform duration-300 ease-in-out ${
              sidebarOpen ? 'translate-x-0' : '-translate-x-full'
            } lg:relative lg:translate-x-0`}
          >
            <div className="flex flex-col h-full">
              <div className="flex items-center justify-between p-5 sm:p-6 border-b border-border">
                <Link href="/" className="flex items-center gap-2.5">
                  <div className="h-9 w-9 rounded-xl bg-primary flex items-center justify-center shadow-md shadow-primary/20">
                    <Leaf className="h-5 w-5 text-primary-foreground" />
                  </div>
                  <div>
                    <span className="font-bold text-foreground tracking-tight text-lg block leading-none">CHAI-NET</span>
                    <span className="text-[10px] text-muted-foreground font-medium uppercase tracking-wider">Tea Intelligence</span>
                  </div>
                </Link>
                <button
                  onClick={() => setSidebarOpen(false)}
                  className="lg:hidden p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  aria-label="Close menu"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <nav className="flex-1 space-y-1.5 p-3 sm:p-4 overflow-y-auto scrollbar-thin">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => {
                        setActiveTab(tab.id);
                        setSidebarOpen(false);
                      }}
                      className={`w-full text-left px-3.5 py-3 rounded-xl transition-all flex items-start gap-3 ${
                        isActive
                          ? 'bg-primary text-primary-foreground shadow-sm shadow-primary/30 font-semibold'
                          : 'text-foreground hover:bg-muted/70'
                      }`}
                    >
                      <Icon className={`h-5 w-5 mt-0.5 flex-shrink-0 ${isActive ? 'text-primary-foreground' : 'text-primary'}`} />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm truncate">{tab.label}</div>
                        <div className={`text-xs mt-0.5 truncate ${isActive ? 'text-primary-foreground/80' : 'text-muted-foreground'}`}>
                          {tab.description}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </nav>

              <div className="p-4 border-t border-border">
                <Link href="/">
                  <Button variant="outline" size="sm" className="w-full bg-transparent justify-center">
                    {t('backToHome')}
                  </Button>
                </Link>
              </div>
            </div>
          </div>

          <div className="flex-1 flex flex-col overflow-hidden min-w-0">
            <div className="border-b border-border bg-card/80 backdrop-blur-md h-16 flex items-center justify-between px-3 sm:px-6 shrink-0 z-10">
              <div className="flex items-center gap-2.5 sm:gap-4 min-w-0">
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="lg:hidden p-2 rounded-lg text-foreground hover:text-muted-foreground hover:bg-muted transition-colors flex-shrink-0"
                  aria-label="Open navigation menu"
                >
                  <Menu className="h-5 w-5" />
                </button>
                <div className="flex items-center gap-2 truncate">
                  <h1 className="text-base sm:text-xl font-bold text-foreground truncate">{t('dashboard')}</h1>
                </div>
              </div>

              <div className="flex items-center gap-1.5 sm:gap-3 flex-shrink-0">
                <div className="hidden md:block text-xs lg:text-sm text-muted-foreground">
                  {new Date().toLocaleDateString('en-US', {
                    weekday: 'short',
                    month: 'short',
                    day: 'numeric',
                  })}
                </div>
                <LanguageToggle />
                <NotificationBell />
                <ProfileDropdown onSettingsClick={() => setActiveTab('settings')} />
              </div>
            </div>

            <div className="flex-1 overflow-auto">
              <div className="p-3 sm:p-5 md:p-6 pb-28 lg:pb-6 max-w-7xl mx-auto w-full">
                {activeTab === 'cultivation' && <CultivationIntelligence />}
                {activeTab === 'leaf-quality' && <LeafQualityScanner />}
                {activeTab === 'action' && <FarmerActionSimulator />}
                {activeTab === 'market' && <MarketIntelligence />}
                {activeTab === 'satellite' && <SatelliteCropHealth />}
                {activeTab === 'subsidies' && <SubsidyInsuranceNavigator />}
                {activeTab === 'digital-twin' && <DigitalTwin />}
                {activeTab === 'settings' && <AccountSettings />}
              </div>
            </div>
          </div>

          <div className="lg:hidden fixed bottom-0 left-0 right-0 z-30 bg-background/95 backdrop-blur-lg border-t border-border px-2 py-1.5 shadow-lg">
            <div className="grid grid-cols-5 gap-1 items-center max-w-md mx-auto">
              {mobileNavItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setActiveTab(item.id);
                      setSidebarOpen(false);
                    }}
                    className={`flex flex-col items-center justify-center py-1.5 px-1 rounded-xl transition-all ${
                      isActive ? 'text-primary font-semibold' : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    <div className={`p-1 rounded-lg transition-all ${isActive ? 'bg-primary/10 scale-110' : ''}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className="text-[10px] mt-0.5 tracking-tight truncate max-w-full">{item.label}</span>
                  </button>
                );
              })}

              <button
                onClick={() => setSidebarOpen(true)}
                className={`flex flex-col items-center justify-center py-1.5 px-1 rounded-xl transition-all ${
                  sidebarOpen ? 'text-primary font-semibold' : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <div className={`p-1 rounded-lg transition-all ${sidebarOpen ? 'bg-primary/10 scale-110' : ''}`}>
                  <MoreHorizontal className="h-5 w-5" />
                </div>
                <span className="text-[10px] mt-0.5 tracking-tight">More</span>
              </button>
            </div>
          </div>

          <ChatbotBubble onNavigate={setActiveTab} />
        </div>
      </AlertsProvider>
    </ProtectedRoute>
  );
}
