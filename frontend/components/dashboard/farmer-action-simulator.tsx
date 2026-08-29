'use client';

import { useLanguage } from '@/context/LanguageContext';
import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { AlertCircle, TrendingUp, TrendingDown, CheckCircle, AlertTriangle, BarChart3, Zap, Download, Copy, Truck } from 'lucide-react';
import { apiClient } from '@/lib/api';
import dynamic from 'next/dynamic';
import { Loader2 } from 'lucide-react';

const RouteMap = dynamic(() => import('./route-map'), {
  ssr: false,
  loading: () => (
    <div className="h-[400px] w-full bg-muted/20 rounded-xl flex items-center justify-center border border-dashed border-muted-foreground/20">
      <div className="text-muted-foreground text-sm flex items-center gap-2">
        <Loader2 className="h-4 w-4 animate-spin" />Loading map…
      </div>
    </div>
  ),
});

type SimulationData = {
  timestamp: string;
  leafQuality: string;
  cropStage: string;
  marketTrend: string;
  recommendedActions: string[];
  diseasePreventionApproaches: string[];
  projectedOutcomes: {
    yieldChange: string;
    profitChange: string;
    riskLevel: string;
    harvestTiming: string;
  };
  noActionOutcomes: {
    yieldChange: string;
    profitChange: string;
    riskLevel: string;
  };
  marketInsights: {
    demandForecast: string;
    priceIncrease: string;
    sellingWindow: string;
  };
  confidence: {
    modelAccuracy: number;
    marketReliability: number;
    historicalSimilarity: number;
  };
  riskFactors?: Array<{
    factor: string;
    description: string;
    severity: 'high' | 'medium' | 'low';
  }>;
};

type SellingSuggestion = {
  title: string;
  description: string;
  expectedRevenue: string;
  timing: string;
  priority: 'high' | 'medium' | 'low';
  price_per_kg?: number;
};

export default function FarmerActionSimulator() {
  const { t } = useLanguage();
  const [decision, setDecision] = useState<'pending' | 'proceed' | 'modify' | 'skip'>('pending');
  const [simulationData, setSimulationData] = useState<SimulationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Yield input and selling suggestions
  const [yieldInput, setYieldInput] = useState<string>('');
  const [sellingSuggestions, setSellingSuggestions] = useState<SellingSuggestion[]>([]);
  const [selectedApproach, setSelectedApproach] = useState<number>(0);
  const [showYieldAnalysis, setShowYieldAnalysis] = useState(false);

  // Auction Center state
  const [centers, setCenters] = useState<{ key: string; name: string; lat: number; lng: number }[]>([]);
  const [selectedDest, setSelectedDest] = useState<string>('guwahati');
  
  // Infrastructure Reality & Map state
  const [infraRealityOn, setInfraRealityOn] = useState(false);
  const [routeData, setRouteData] = useState<{
    route_risk: string;
    spoilage_pct: number;
    effective_price: number;
    recommended_harvest_shift: number;
    destination_name?: string;
    distance_km?: number;
    duration_min?: number;
    alternate_route?: any;
    origin?: any;
    destination?: any;
    segments?: any[];
    geometry?: any;
    base_price?: number;
  } | null>(null);
  const [infraLoading, setInfraLoading] = useState(false);
  
  useEffect(() => {
    apiClient.get('/api/route/auction-centers')
      .then((d: any) => setCenters(d.centers || []))
      .catch(() => {});
  }, []);

  const fetchRouteAnalysis = async (dest: string) => {
    try {
      setInfraLoading(true);
      const data = await apiClient.post('/api/route/analyze', {
        origin_lat: 26.5714,
        origin_lng: 93.8441,
        origin_name: 'Tea Garden (Jorhat)',
        destination: dest,
      });
      setRouteData({
        route_risk: data.route_risk,
        spoilage_pct: data.spoilage_pct,
        effective_price: data.effective_price,
        recommended_harvest_shift: data.recommended_harvest_shift,
        destination_name: data.destination?.name,
        distance_km: data.distance_km,
        duration_min: data.duration_min,
        alternate_route: data.alternate_route,
        origin: data.origin,
        destination: data.destination,
        segments: data.segments,
        geometry: data.geometry,
        base_price: data.base_price,
      });
      return data;
    } catch (e) {
      console.error(e);
      return null;
    } finally {
      setInfraLoading(false);
    }
  };

  const toggleInfraReality = async () => {
    const next = !infraRealityOn;
    setInfraRealityOn(next);
    if (next && !routeData) {
      await fetchRouteAnalysis(selectedDest);
    }
  };

  // Helper function to clean markdown formatting from AI-generated text
  const cleanMarkdown = (text: string): string => {
    if (!text) return '';
    return text
      // Remove bold: **text** or __text__
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/__(.+?)__/g, '$1')
      // Remove italic: *text* or _text_
      .replace(/\*(.+?)\*/g, '$1')
      .replace(/_(.+?)_/g, '$1')
      // Remove code blocks: `text`
      .replace(/`(.+?)`/g, '$1')
      // Remove headers: # text
      .replace(/^#+\s+/gm, '')
      // Remove bullet points: - text or * text
      .replace(/^[\-\*]\s+/gm, '')
      // Clean up any remaining asterisks
      .replace(/\*/g, '');
  };


  const runSimulation = async () => {
    try {
      setLoading(true);
      setError(null);

      // Call the new comprehensive action plan API
      const data = await apiClient.post("/api/action-plan/generate");

      // Extract data from comprehensive response
      const envData = data.environmental_data || {};
      const leafData = data.leaf_scan_summary || {};
      const marketData = data.market_analysis || {};
      const recommendations = data.recommended_actions || {};

      // Build leaf quality string
      const leafQualityStr = leafData.scans_analyzed > 0
        ? `${leafData.status} (${leafData.scans_analyzed} scans analyzed)`
        : "No recent scans";

      // Build crop stage from environmental status
      const cropStage = envData.status === "excellent" || envData.status === "good"
        ? "Optimal growth conditions"
        : envData.status === "fair"
          ? "Moderate growth conditions"
          : "Stressed conditions";

      // Build market trend string
      const marketTrend = marketData.signal === "opportunity"
        ? "Rising demand"
        : marketData.signal === "risk"
          ? "High volatility"
          : marketData.signal === "watch"
            ? "Low demand"
            : "Stable market";

      // Combine all recommendations into a single array
      const allActions: string[] = [];

      if (recommendations.immediate_actions && recommendations.immediate_actions.length > 0) {
        recommendations.immediate_actions.forEach((item: any) => {
          allActions.push(item.action);
        });
      }

      if (recommendations.short_term_strategy && recommendations.short_term_strategy.length > 0) {
        recommendations.short_term_strategy.forEach((item: any) => {
          allActions.push(item.action);
        });
      }

      if (recommendations.market_timing && recommendations.market_timing.length > 0) {
        recommendations.market_timing.forEach((item: any) => {
          allActions.push(item.action);
        });
      }

      // If no specific actions, provide general guidance
      if (allActions.length === 0) {
        allActions.push("Continue current cultivation practices");
        allActions.push("Monitor environmental conditions daily");
        allActions.push("Maintain regular leaf health inspections");
      }

      // Build market insights
      const currentPrice = marketData.current_data?.current_price || 0;
      const forecastPrice = marketData.current_data?.forecast_price || 0;
      const priceChange = forecastPrice > currentPrice
        ? `+${((forecastPrice - currentPrice) / currentPrice * 100).toFixed(1)}% per kg`
        : `${((forecastPrice - currentPrice) / currentPrice * 100).toFixed(1)}% per kg`;

      const demandForecast = marketData.signal === "opportunity"
        ? "Rising in 7–10 days"
        : marketData.signal === "risk"
          ? "Volatile, monitor closely"
          : "Stable, wait for improvement";

      // Calculate selling window based on current date
      const today = new Date();
      const windowStart = new Date(today);
      windowStart.setDate(today.getDate() + 7);
      const windowEnd = new Date(today);
      windowEnd.setDate(today.getDate() + 12);

      const sellingWindow = `${windowStart.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – ${windowEnd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;

      // 🔑 Map backend → frontend structure
      setSimulationData({
        timestamp: new Date(data.timestamp).toLocaleString(),
        leafQuality: leafQualityStr,
        cropStage: cropStage,
        marketTrend: marketTrend,

        recommendedActions: allActions.slice(0, 5), // Take top 5 actions

        diseasePreventionApproaches: data.disease_prevention_approaches || [],

        projectedOutcomes: {
          yieldChange: data.projected_outcomes.yieldChange,
          profitChange: data.projected_outcomes.profitChange,
          riskLevel: data.projected_outcomes.riskLevel,
          harvestTiming: data.projected_outcomes.harvestTiming
        },

        noActionOutcomes: {
          yieldChange: "-2%",
          profitChange: "-₹1,200",
          riskLevel: "Medium"
        },

        marketInsights: {
          demandForecast: demandForecast,
          priceIncrease: priceChange,
          sellingWindow: sellingWindow
        },

        confidence: {
          modelAccuracy: data.confidence.modelAccuracy,
          marketReliability: data.confidence.marketReliability,
          historicalSimilarity: data.confidence.historicalSimilarity
        }
      });

    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const generateYieldSuggestions = async () => {
    if (!yieldInput || !simulationData) return;

    const yieldKg = parseFloat(yieldInput);
    if (isNaN(yieldKg) || yieldKg <= 0) {
      setError("Please enter a valid yield amount");
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Auto-fetch route analysis to get spoilage for chosen destination BEFORE yield calculation
      const routeRes = await fetchRouteAnalysis(selectedDest);
      if (!infraRealityOn) setInfraRealityOn(true);
      const spoilagePct = routeRes ? routeRes.spoilage_pct : 0.0;

      // Call the new backend API with real Guwahati market data and route spoilage
      const data = await apiClient.post("/api/calculate-yield-strategy", {
        yield_kg: yieldKg,
        selected_approach: selectedApproach,
        spoilage_pct: spoilagePct
      });

      // Map backend strategies to frontend format
      const mappedSuggestions: SellingSuggestion[] = data.strategies.map((strategy: any) => ({
        title: strategy.title,
        description: strategy.description,
        expectedRevenue: strategy.revenue_display,
        timing: strategy.timing,
        priority: strategy.priority as 'high' | 'medium' | 'low',
        price_per_kg: strategy.price_per_kg
      }));

      setSellingSuggestions(mappedSuggestions);
      setShowYieldAnalysis(true);

      // Update simulation data with real-time calculations
      setSimulationData(prev => prev ? {
        ...prev,
        projectedOutcomes: {
          yieldChange: data.projected_outcomes.yieldChange,
          profitChange: data.projected_outcomes.profitChange,
          riskLevel: data.projected_outcomes.riskLevel,
          harvestTiming: data.projected_outcomes.harvestTiming
        },
        noActionOutcomes: {
          yieldChange: data.no_action_outcomes.yieldChange,
          profitChange: data.no_action_outcomes.profitChange,
          riskLevel: data.no_action_outcomes.riskLevel
        },
        marketInsights: {
          demandForecast: data.market_data.signal === "opportunity"
            ? `Rising (Demand Index: ${data.market_data.demand_index}/100)`
            : data.market_data.signal === "risk"
              ? "Volatile, monitor closely"
              : "Stable, wait for improvement",
          priceIncrease: `${data.market_data.forecast_increase_pct > 0 ? '+' : ''}${data.market_data.forecast_increase_pct}% per kg`,
          sellingWindow: data.market_data.selling_window
        },
        riskFactors: data.risk_factors
      } : prev);



    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Function to recalculate when approach changes
  const handleApproachChange = async (approachIndex: number) => {
    setSelectedApproach(approachIndex);

    if (!yieldInput || !showYieldAnalysis) return;

    const yieldKg = parseFloat(yieldInput);
    if (isNaN(yieldKg) || yieldKg <= 0) return;

    try {
      const spoilagePct = routeData ? routeData.spoilage_pct : 0.0;
      
      const data = await apiClient.post("/api/calculate-yield-strategy", {
        yield_kg: yieldKg,
        selected_approach: approachIndex,
        spoilage_pct: spoilagePct
      });

      // Update only the projected outcomes based on new selection
      setSimulationData(prev => prev ? {
        ...prev,
        projectedOutcomes: {
          yieldChange: data.projected_outcomes.yieldChange,
          profitChange: data.projected_outcomes.profitChange,
          riskLevel: data.projected_outcomes.riskLevel,
          harvestTiming: data.projected_outcomes.harvestTiming
        }
      } : prev);

    } catch (err) {
      console.error("Failed to update approach:", err);
    }
  };

  const downloadPDF = async () => {
    if (!simulationData) return;

    try {
      setLoading(true);

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/generate-pdf-report`, {
        method: "POST",
        headers: await (async () => {
          const headers: Record<string, string> = { "Content-Type": "application/json" };
          // Get token from apiClient if available
          if ((apiClient as any).getToken) {
            const token = await (apiClient as any).getToken();
            if (token) headers['Authorization'] = `Bearer ${token}`;
          }
          return headers;
        })(),
        body: JSON.stringify({
          simulation_data: {
            recommendedActions: simulationData.recommendedActions,
            projectedOutcomes: simulationData.projectedOutcomes,
            noActionOutcomes: simulationData.noActionOutcomes,
            diseasePreventionApproaches: simulationData.diseasePreventionApproaches,
            marketInsights: simulationData.marketInsights,
            confidence: simulationData.confidence,
            riskFactors: simulationData.riskFactors || [],
            routeData: infraRealityOn && routeData ? {
              destination_name: routeData.destination_name,
              route_risk: routeData.route_risk,
              spoilage_pct: routeData.spoilage_pct,
              effective_price: routeData.effective_price,
              base_price: routeData.base_price,
              distance_km: routeData.distance_km,
              duration_min: routeData.duration_min,
              alternate_route: routeData.alternate_route ? {
                spoilage_pct: routeData.alternate_route.spoilage_pct,
                effective_price: routeData.alternate_route.effective_price
              } : null
            } : null
          },
          yield_input: yieldInput ? parseFloat(yieldInput) : null,
          selected_approach: selectedApproach,
          selling_suggestions: sellingSuggestions.length > 0 ? sellingSuggestions.map(s => ({
            title: s.title,
            description: s.description,
            expectedRevenue: s.expectedRevenue,
            timing: s.timing,
            priority: s.priority,
            price_per_kg: s.price_per_kg
          })) : []
        })
      });

      if (!response.ok) {
        throw new Error("Failed to generate PDF");
      }

      // Download the PDF
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ChaiTea_Action_Plan_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

    } catch (err: any) {
      setError("Failed to download PDF: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runSimulation();
  }, []);

  if (loading) {
    return (
      <div className="p-10 text-muted-foreground text-center">
        {t('runningFarmerSimulation')}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-10 text-red-600 text-center">
        Error: {error}
      </div>
    );
  }

  if (!simulationData) {
    return null;
  }
  return (

    <div className="space-y-6">
      {/* Header with Context */}
      <div>
        <h2 className="text-3xl font-bold text-foreground">{t('farmerActionSimTitle')}</h2>
        <p className="text-muted-foreground mt-2">{t('simulateOutcomesDesc')}</p>
        <div className="mt-4 p-4 bg-muted rounded-lg">
          <p className="text-sm font-medium text-foreground mb-2">{t('basedOn')}</p>
          <ul className="space-y-1 text-sm text-muted-foreground">
            <li>• {t('leafQualityLabel')} {simulationData.leafQuality}</li>
            <li>• {t('cropStageLabel')} {t('midGrowth')}</li>
            <li>• {t('marketTrendLabel')} {t('risingDemand')}</li>
          </ul>
        </div>
      </div>



      {/* Yield Input and Selling Suggestions */}
      <Card className="p-6 border-primary/30 bg-gradient-to-br from-primary/10 to-transparent">
        <div className="flex items-start gap-4">
          <BarChart3 className="h-6 w-6 text-primary flex-shrink-0 mt-1" />
          <div className="flex-1">
            <h3 className="font-bold text-foreground text-lg mb-3">{t('yieldAnalysisStrategy')}</h3>
            <p className="text-sm text-muted-foreground mb-4">{t('enterYieldDesc')}</p>

            <div className="flex flex-col gap-4 mb-6">
              <div className="flex flex-col md:flex-row gap-3">
                <div className="flex-1">
                  <label className="text-xs font-semibold text-muted-foreground mb-1 block">{t('originLocation')}</label>
                  <input
                    type="text"
                    value="Tea Garden (Jorhat)"
                    disabled
                    className="w-full px-4 py-2 border border-border rounded-lg bg-muted text-muted-foreground focus:outline-none"
                  />
                </div>
                <div className="flex-1">
                  <label className="text-xs font-semibold text-muted-foreground mb-1 block">{t('destinationAuctionCenter')}</label>
                  <select
                    value={selectedDest}
                    onChange={(e) => setSelectedDest(e.target.value)}
                    className="w-full px-4 py-2 border border-border rounded-lg bg-background text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary truncate"
                  >
                    {centers.map((c) => (
                      <option key={c.key} value={c.key}>{c.name}</option>
                    ))}
                    {centers.length === 0 && (
                      <>
                        <option value="guwahati">{t('guwahatiAuctionCenter')}</option>
                        <option value="siliguri">{t('siliguriAuctionCenter')}</option>
                        <option value="kolkata">{t('kolkataAuctionCenter')}</option>
                        <option value="jorhat">{t('jorhatAuctionCenter')}</option>
                      </>
                    )}
                  </select>
                </div>
              </div>
              <div className="flex flex-col md:flex-row gap-3 items-end">
                <div className="flex-1">
                  <label className="text-xs font-semibold text-muted-foreground mb-1 block">{t('yieldKg')}</label>
                  <input
                    type="number"
                    value={yieldInput}
                    onChange={(e) => setYieldInput(e.target.value)}
                    placeholder={t('enterYieldPlaceholder')}
                    className="w-full px-4 py-2 border border-border rounded-lg bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <Button
                  onClick={generateYieldSuggestions}
                  className="bg-primary hover:bg-primary/90 text-primary-foreground py-2 h-[42px]"
                >
                  {t('analyzeYield')}
                </Button>
              </div>
            </div>

            {showYieldAnalysis && sellingSuggestions.length > 0 && (
              <div className="space-y-4">
                <h4 className="font-semibold text-foreground mb-3">{t('threeSellingApproaches')}</h4>
                {sellingSuggestions.map((suggestion, i) => (
                  <div
                    key={i}
                    onClick={() => handleApproachChange(i)}
                    className={`p-4 rounded-lg border-2 cursor-pointer transition-all ${selectedApproach === i
                      ? 'border-primary bg-primary/10'
                      : 'border-border bg-background hover:border-primary/50'
                      }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center ${selectedApproach === i ? 'bg-primary' : 'bg-muted'
                          }`}>
                          {selectedApproach === i ? (
                            <CheckCircle className="h-4 w-4 text-primary-foreground" />
                          ) : (
                            <span className="text-xs font-bold text-muted-foreground">{i + 1}</span>
                          )}
                        </div>
                        <h5 className="font-semibold text-foreground">{suggestion.title}</h5>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${suggestion.priority === 'high' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                        suggestion.priority === 'medium' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' :
                          'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400'
                        }`}>
                        {suggestion.priority.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-sm text-muted-foreground mb-3">{suggestion.description}</p>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-2 bg-muted rounded">
                        <p className="text-xs text-muted-foreground">{t('expectedRevenue')}</p>
                        <p className="text-lg font-bold text-green-600 dark:text-green-400">{suggestion.expectedRevenue}</p>
                      </div>
                      <div className="p-2 bg-muted rounded">
                        <p className="text-xs text-muted-foreground">{t('timing')}</p>
                        <p className="text-sm font-semibold text-foreground">{suggestion.timing}</p>
                      </div>
                    </div>
                  </div>
                ))}

                <div className="mt-4 p-4 bg-primary/10 rounded-lg border border-primary/20">
                  <p className="text-sm font-semibold text-foreground mb-2">
                    ✓ {t('selectedApproach')}: {sellingSuggestions[selectedApproach]?.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t('realtimeCardsUpdate')}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Infra Reality live panel */}
      {infraRealityOn && infraLoading && (
        <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-center text-xs text-blue-400 animate-pulse">
          Fetching route risk from OSRM…
        </div>
      )}
      {infraRealityOn && routeData && !infraLoading && (
        <Card className="p-0 overflow-hidden border-blue-200 dark:border-blue-900 shadow-lg shadow-blue-500/10">
          {/* Map Header */}
          <div className="bg-blue-50 dark:bg-blue-900/30 p-4 border-b border-blue-100 dark:border-blue-800/50 flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-lg bg-blue-500 text-white flex items-center justify-center">
                <AlertCircle className="h-4 w-4" />
              </div>
              <div>
                <p className="font-bold text-foreground">{t('logisticsRouteAnalysis')}</p>
                <p className="text-xs text-muted-foreground">To {routeData.destination_name} ({routeData.distance_km} km)</p>
              </div>
            </div>
            <div className={`px-3 py-1 rounded-full text-xs font-bold border ${
              routeData.route_risk === 'HIGH' ? 'bg-red-500/10 text-red-500 border-red-200' : 
              routeData.route_risk === 'MEDIUM' ? 'bg-amber-500/10 text-amber-500 border-amber-200' : 
              'bg-emerald-500/10 text-emerald-500 border-emerald-200'
            }`}>
              {routeData.route_risk} {t('riskSuffix')}
            </div>
          </div>

          {/* Map View */}
          <div className="h-[300px] w-full bg-slate-100 relative">
            {routeData.origin && routeData.destination && routeData.segments && (
              <RouteMap
                origin={routeData.origin}
                destination={routeData.destination}
                segments={routeData.segments}
                alternateGeometry={routeData.alternate_route?.geometry}
              />
            )}
          </div>

          {/* Detailed Route & Financials Breakdown */}
          <div className="p-4 bg-background border-t border-blue-100 dark:border-blue-900/50">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Route Details */}
              <div className="space-y-4">
                <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">{t('routeDiagnostics')}</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-muted/50 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">{t('distance')}</p>
                    <p className="text-lg font-bold text-foreground">{routeData.distance_km} km</p>
                  </div>
                  <div className="p-3 bg-muted/50 rounded-lg">
                    <p className="text-xs text-muted-foreground mb-1">{t('estimatedDuration')}</p>
                    <p className="text-lg font-bold text-foreground">
                      {routeData.duration_min ? `${Math.floor(routeData.duration_min / 60)}h ${Math.round(routeData.duration_min % 60)}m` : 'N/A'}
                    </p>
                  </div>
                </div>
                <div className={`p-3 rounded-lg border ${
                  routeData.route_risk === 'HIGH' ? 'bg-red-50 dark:bg-red-900/10 border-red-200 text-red-800 dark:text-red-300' :
                  routeData.route_risk === 'MEDIUM' ? 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 text-amber-800 dark:text-amber-300' :
                  'bg-emerald-50 dark:bg-emerald-900/10 border-emerald-200 text-emerald-800 dark:text-emerald-300'
                }`}>
                  <p className="text-xs font-bold uppercase mb-1 flex items-center gap-2">
                    <AlertTriangle className="h-3 w-3" /> {t('routeAdvisory')}
                  </p>
                  <p className="text-sm">
                    {routeData.route_risk === 'HIGH' ? 'Severe weather or infrastructure issues detected on this route. Expect high transit spoilage.' :
                     routeData.route_risk === 'MEDIUM' ? 'Moderate delays expected. Ensure proper tarpaulin coverage.' :
                     'Clear route. Optimal conditions for transit.'}
                  </p>
                </div>
              </div>

              {/* Financials Breakdown */}
              <div className="space-y-4">
                <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">{t('effectivePriceCalculation')}</h4>
                {(() => {
                  const selectedPrice = sellingSuggestions[selectedApproach]?.price_per_kg || routeData.base_price || 0;
                  const spoilage = routeData.spoilage_pct;
                  const effectivePrice = selectedPrice * (1 - spoilage / 100);
                  
                  return (
                    <div className="bg-muted/30 border rounded-lg p-4 space-y-3">
                      <div className="flex justify-between items-center text-sm">
                        <span className="text-muted-foreground">{t('selectedBasePrice')}</span>
                        <span className="font-medium text-foreground">₹{selectedPrice.toFixed(2)}/kg</span>
                      </div>
                      <div className="flex justify-between items-center text-sm">
                        <span className="text-red-500 dark:text-red-400">{t('transitSpoilageDeduction')} ({spoilage}%)</span>
                        <span className="font-medium text-red-500 dark:text-red-400">-₹{(selectedPrice * (spoilage / 100)).toFixed(2)}/kg</span>
                      </div>
                      <div className="h-px bg-border w-full my-2"></div>
                      <div className="flex justify-between items-center">
                        <span className="font-bold text-foreground">{t('realizedEffectivePrice')}</span>
                        <span className="text-xl font-bold text-emerald-500 dark:text-emerald-400">₹{effectivePrice.toFixed(2)}<span className="text-sm text-emerald-500/70">/kg</span></span>
                      </div>
                    </div>
                  );
                })()}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Conditionally show these sections only when yield is entered */}
      {showYieldAnalysis && yieldInput && (
        <>
          {/* Unified Action Plan */}
          <Card className="p-6 border-primary/30 bg-gradient-to-br from-primary/10 to-transparent mb-6">
            <div className="flex items-start gap-4">
              <Zap className="h-6 w-6 text-primary flex-shrink-0 mt-1" />
              <div className="w-full">
                <h3 className="font-bold text-foreground text-lg mb-3">{t('unifiedActionPlan')}</h3>
                <p className="text-sm text-muted-foreground mb-4">{t('correlatedStrategy')}</p>
                
                <div className="space-y-6">
                  {/* Logistics & Yield Strategy */}
                  <div>
                    <h4 className="text-sm font-bold text-foreground uppercase tracking-wider mb-3">{t('logisticsYieldStrategy')}</h4>
                    <ul className="space-y-3 text-foreground">
                      <li className="flex items-start gap-3">
                        <BarChart3 className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                        <div>
                          <span className="font-medium">Selected Approach: {sellingSuggestions[selectedApproach]?.title || 'Select an approach'}</span>
                          <p className="text-sm text-muted-foreground mt-1">{t('executeMarketApproach')}</p>
                        </div>
                      </li>
                      {routeData && (
                        <li className="flex items-start gap-3">
                          <Truck className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                          <div>
                            <span className="font-medium">
                              Logistics Action: {
                                routeData.route_risk === 'HIGH' 
                                  ? 'Delay dispatch or select alternate route to avoid high spoilage.'
                                  : routeData.route_risk === 'MEDIUM'
                                    ? 'Proceed with caution. Monitor weather along the route.'
                                    : 'Optimal dispatch conditions. Proceed with current route.'
                              }
                            </span>
                            <p className="text-sm text-muted-foreground mt-1">Mitigate the expected {routeData.spoilage_pct}% spoilage risk.</p>
                          </div>
                        </li>
                      )}
                    </ul>
                  </div>

                  {/* Environmental & Crop Strategy */}
                  <div>
                    <h4 className="text-sm font-bold text-foreground uppercase tracking-wider mb-3">{t('environmentalCropStrategy')}</h4>
                    <ul className="space-y-3 text-foreground">
                      {simulationData.recommendedActions.map((action, i) => (
                        <li key={i} className="flex items-start gap-3">
                          <CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                          <span className="font-medium text-foreground">{action}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Disease Prevention Approaches */}
          {simulationData.diseasePreventionApproaches && simulationData.diseasePreventionApproaches.length > 0 && (
            <Card className="p-6 border-orange-200 dark:border-orange-900/30 bg-gradient-to-br from-orange-50 dark:from-orange-900/10 to-transparent mb-6">
              <div className="flex items-start gap-4">
                <AlertTriangle className="h-6 w-6 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-1" />
                <div className="flex-1">
                  <h3 className="font-bold text-foreground text-lg mb-3">{t('diseasePreventionApproachesTitle')}</h3>
                  <p className="text-sm text-muted-foreground mb-4">{t('diseasePreventionDesc')}</p>
                  <div className="space-y-4">
                    {simulationData.diseasePreventionApproaches.map((approach, i) => (
                      <div key={i} className="p-4 bg-white dark:bg-background rounded-lg border border-orange-200 dark:border-orange-900/50">
                        <div className="flex items-start gap-3">
                          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center">
                            <span className="text-sm font-bold text-orange-600 dark:text-orange-400">{i + 1}</span>
                          </div>
                          <p className="text-foreground flex-1">{cleanMarkdown(approach)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Primary Simulation Outcome - Hero Section */}
          <Card className="p-4 sm:p-6 lg:p-8 border-2 border-primary/50 bg-gradient-to-br from-primary/5 via-background to-background">
            <div className="mb-2 flex items-center gap-2">
              <TrendingUp className="h-5 w-5 sm:h-6 sm:w-6 text-primary" />
              <h3 className="font-bold text-foreground text-lg sm:text-2xl">{t('ifYouFollowThisAction')}</h3>
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground mb-4 sm:mb-6">{t('projectedOutcomeAi')}</p>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
              <div className="p-3 sm:p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                <p className="text-xs sm:text-sm text-muted-foreground mb-1 truncate">{t('expectedYieldChange')}</p>
                <p className="text-xl sm:text-3xl font-bold text-green-600 dark:text-green-400">{simulationData.projectedOutcomes.yieldChange}</p>
                <p className="text-[10px] sm:text-xs text-muted-foreground mt-1 sm:mt-2 truncate">{t('additionalYieldEst')}</p>
              </div>

              <div className="p-3 sm:p-4 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg border border-emerald-200 dark:border-emerald-800">
                <p className="text-xs sm:text-sm text-muted-foreground mb-1 truncate">{t('estimatedProfitChange')}</p>
                <p className="text-xl sm:text-3xl font-bold text-emerald-600 dark:text-emerald-400">{simulationData.projectedOutcomes.profitChange}</p>
                <p className="text-[10px] sm:text-xs text-muted-foreground mt-1 sm:mt-2 truncate">{t('basedOnCurrentRates')}</p>
              </div>

              <div className="p-3 sm:p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                <p className="text-xs sm:text-sm text-muted-foreground mb-1 truncate">{t('riskLevelLabel')}</p>
                <p className="text-xl sm:text-3xl font-bold text-blue-600 dark:text-blue-400">
                  {simulationData.projectedOutcomes.riskLevel}
                </p>
                <p className="text-[10px] sm:text-xs text-muted-foreground mt-1 sm:mt-2 truncate">
                  {t('probBasedOnConditions')}
                </p>
              </div>

              <div className="p-3 sm:p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                <p className="text-xs sm:text-sm text-muted-foreground mb-1 truncate">{t('harvestTiming')}</p>
                <p className="text-xl sm:text-3xl font-bold text-amber-600 dark:text-amber-400">{simulationData.projectedOutcomes.harvestTiming}</p>
                <p className="text-[10px] sm:text-xs text-muted-foreground mt-1 sm:mt-2 truncate">{t('alignsWithMarketPeak')}</p>
              </div>
            </div>
          </Card>

          {/* Comparison: If No Action */}
          <Card className="p-6 border-red-200 dark:border-red-900/30 bg-red-50 dark:bg-red-900/10">
            <div className="flex items-start gap-4">
              <TrendingDown className="h-6 w-6 text-red-600 dark:text-red-400 flex-shrink-0 mt-1" />
              <div className="flex-1">
                <h3 className="font-bold text-foreground text-lg mb-4">{t('ifNoActionTaken')}</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">{t('yieldChange')}</p>
                    <p className="text-2xl font-bold text-red-600 dark:text-red-400">{simulationData.noActionOutcomes.yieldChange}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">{t('profitChange')}</p>
                    <p className="text-2xl font-bold text-red-600 dark:text-red-400">{simulationData.noActionOutcomes.profitChange}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">{t('riskLevelLabel')}</p>
                    <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{simulationData.noActionOutcomes.riskLevel}</p>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          {/* Market Timing Insight */}
          <Card className="p-6">
            <div className="flex items-start gap-4">
              <BarChart3 className="h-6 w-6 text-primary flex-shrink-0 mt-1" />
              <div className="flex-1">
                <h3 className="font-bold text-foreground text-lg mb-4">{t('marketTimingInsight')}</h3>
                <div className="space-y-3">
                  <p className="text-foreground">
                    <span className="font-semibold">{t('demandForecastLabel')}</span> {simulationData.marketInsights.demandForecast} <span className="text-green-600 dark:text-green-400">↑</span>
                  </p>
                  <p className="text-foreground">
                    <span className="font-semibold">{t('priceChangeLabel')}</span> {simulationData.marketInsights.priceIncrease}
                  </p>
                  <p className="text-foreground">
                    <span className="font-semibold">{t('bestSellingWindowLabel')}</span> {simulationData.marketInsights.sellingWindow}
                  </p>
                </div>
              </div>
            </div>
          </Card>

          {/* Confidence & Reliability */}
          <Card className="p-6 bg-muted/50">
            <h3 className="font-bold text-foreground mb-4">{t('simulationConfidence')}</h3>
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-foreground">{t('modelAccuracy')}</p>
                  <span className="text-sm font-bold text-primary">{simulationData.confidence.modelAccuracy}%</span>
                </div>
                <div className="w-full bg-border rounded-full h-2">
                  <div className="bg-primary h-2 rounded-full" style={{ width: `${simulationData.confidence.modelAccuracy}%` }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-foreground">{t('marketDataReliability')}</p>
                  <span className="text-sm font-bold text-primary">{simulationData.confidence.marketReliability}%</span>
                </div>
                <div className="w-full bg-border rounded-full h-2">
                  <div className="bg-primary h-2 rounded-full" style={{ width: `${simulationData.confidence.marketReliability}%` }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-foreground">{t('historicalTrendSimilarity')}</p>
                  <span className="text-sm font-bold text-primary">{simulationData.confidence.historicalSimilarity}%</span>
                </div>
                <div className="w-full bg-border rounded-full h-2">
                  <div className="bg-primary h-2 rounded-full" style={{ width: `${simulationData.confidence.historicalSimilarity}%` }} />
                </div>
              </div>

              <div className="mt-4 p-3 bg-primary/10 rounded-lg border border-primary/20">
                <p className="text-sm text-foreground">
                  <span className="font-semibold">{t('overallConfidence')} </span>
                  <span className="text-primary font-bold">
                    {Math.round((simulationData.confidence.modelAccuracy + simulationData.confidence.marketReliability + simulationData.confidence.historicalSimilarity) / 3) >= 85 ? 'High' :
                      Math.round((simulationData.confidence.modelAccuracy + simulationData.confidence.marketReliability + simulationData.confidence.historicalSimilarity) / 3) >= 70 ? 'Medium' : 'Low'}
                    ({Math.round((simulationData.confidence.modelAccuracy + simulationData.confidence.marketReliability + simulationData.confidence.historicalSimilarity) / 3)}%)
                  </span>
                </p>
              </div>
            </div>
          </Card>

          {/* Risk Explanation */}
          <Card className="p-6 border-yellow-200 dark:border-yellow-900/30 bg-yellow-50 dark:bg-yellow-900/10">
            <div className="flex items-start gap-4">
              <AlertTriangle className="h-6 w-6 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-1" />
              <div className="flex-1">
                <h3 className="font-bold text-foreground text-lg mb-4">{t('riskFactors')}</h3>
                {simulationData.riskFactors && simulationData.riskFactors.length > 0 ? (
                  <ul className="space-y-3">
                    {simulationData.riskFactors.map((risk, index) => (
                      <li key={index} className="flex items-start gap-3">
                        <div className={`flex-shrink-0 w-2 h-2 rounded-full mt-2 ${risk.severity === 'high' ? 'bg-red-500' :
                          risk.severity === 'medium' ? 'bg-yellow-500' :
                            'bg-green-500'
                          }`} />
                        <div className="flex-1">
                          <span className="font-semibold text-foreground">{risk.factor}: </span>
                          <span className="text-foreground">{risk.description}</span>
                          <span className={`ml-2 px-2 py-0.5 rounded text-xs font-semibold ${risk.severity === 'high' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                            risk.severity === 'medium' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' :
                              'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                            }`}>
                            {risk.severity.toUpperCase()}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <ul className="space-y-2">
                    <li className="text-foreground">
                      <span className="font-semibold">{t('generalMarketRisk')}</span> Enter yield amount above to see specific risk factors for your situation
                    </li>
                  </ul>
                )}
              </div>
            </div>
          </Card>
        </>
      )}

      {/* Download PDF */}
      <Card className="p-8 border-2 border-primary/50 bg-gradient-to-br from-primary/10 via-background to-background">
        <div className="text-center mb-6">
          <h3 className="font-bold text-foreground text-2xl mb-2">{t('downloadYourActionPlan')}</h3>
          <p className="text-muted-foreground text-sm">
            {t('savePdfDesc')}
          </p>
        </div>

        <div className="flex justify-center">
          <Button
            onClick={downloadPDF}
            disabled={loading || !simulationData}
            className="bg-primary hover:bg-primary/90 text-primary-foreground h-14 px-8 text-base font-semibold rounded-lg transition-all duration-200 hover:shadow-lg hover:shadow-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download className="h-5 w-5 mr-2" />
            {loading ? t('generatingPdf') : t('downloadPdfReport')}
          </Button>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-600 dark:text-red-400 text-center">{error}</p>
          </div>
        )}

        <div className="mt-6 p-4 bg-muted/50 rounded-lg">
          <p className="text-xs text-center text-muted-foreground">
            {t('pdfIncludesDesc')}
          </p>
        </div>
      </Card>
    </div>
  );
}
