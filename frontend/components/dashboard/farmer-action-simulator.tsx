'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { AlertCircle, TrendingUp, TrendingDown, CheckCircle, AlertTriangle, BarChart3, Zap, Download, Copy } from 'lucide-react';
import { apiClient } from '@/lib/api';

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
};

export default function FarmerActionSimulator() {
  const [decision, setDecision] = useState<'pending' | 'proceed' | 'modify' | 'skip'>('pending');
  const [simulationData, setSimulationData] = useState<SimulationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Yield input and selling suggestions
  const [yieldInput, setYieldInput] = useState<string>('');
  const [sellingSuggestions, setSellingSuggestions] = useState<SellingSuggestion[]>([]);
  const [selectedApproach, setSelectedApproach] = useState<number>(0);
  const [showYieldAnalysis, setShowYieldAnalysis] = useState(false);

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

      // Call the new backend API with real Guwahati market data
      const data = await apiClient.post("/api/calculate-yield-strategy", {
        yield_kg: yieldKg,
        selected_approach: selectedApproach
      });

      // Map backend strategies to frontend format
      const mappedSuggestions: SellingSuggestion[] = data.strategies.map((strategy: any) => ({
        title: strategy.title,
        description: strategy.description,
        expectedRevenue: strategy.revenue_display,
        timing: strategy.timing,
        priority: strategy.priority as 'high' | 'medium' | 'low'
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
      const data = await apiClient.post("/api/calculate-yield-strategy", {
        yield_kg: yieldKg,
        selected_approach: approachIndex
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
            riskFactors: simulationData.riskFactors || []
          },
          yield_input: yieldInput ? parseFloat(yieldInput) : null,
          selected_approach: selectedApproach,
          selling_suggestions: sellingSuggestions.length > 0 ? sellingSuggestions.map(s => ({
            title: s.title,
            description: s.description,
            expectedRevenue: s.expectedRevenue,
            timing: s.timing,
            priority: s.priority
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
        Running farmer action simulation…
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
        <h2 className="text-3xl font-bold text-foreground">Farmer Action Simulator</h2>
        <p className="text-muted-foreground mt-2">Simulate outcomes before taking action</p>
        <div className="mt-4 p-4 bg-muted rounded-lg">
          <p className="text-sm font-medium text-foreground mb-2">Based on:</p>
          <ul className="space-y-1 text-sm text-muted-foreground">
            <li>• Leaf Quality: {simulationData.leafQuality}</li>
            <li>• Crop Stage: Mid-growth</li>
            <li>• Market Trend: Rising demand</li>
          </ul>
        </div>
      </div>

      {/* Recommended Action Card */}
      <Card className="p-6 border-primary/30 bg-gradient-to-br from-primary/10 to-transparent">
        <div className="flex items-start gap-4">
          <Zap className="h-6 w-6 text-primary flex-shrink-0 mt-1" />
          <div>
            <h3 className="font-bold text-foreground text-lg mb-3">Recommended Action</h3>
            <ul className="space-y-2 text-foreground">
              {simulationData.recommendedActions.map((action, i) => (
                <li key={i} className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0" />
                  <span>{action}</span>
                </li>
              ))}
            </ul>
            <p className="text-sm text-muted-foreground mt-4 italic">Why? These actions will improve leaf quality and align with optimal market timing.</p>
          </div>
        </div>
      </Card>

      {/* Disease Prevention Approaches */}
      {simulationData.diseasePreventionApproaches && simulationData.diseasePreventionApproaches.length > 0 && (
        <Card className="p-6 border-orange-200 dark:border-orange-900/30 bg-gradient-to-br from-orange-50 dark:from-orange-900/10 to-transparent">
          <div className="flex items-start gap-4">
            <AlertTriangle className="h-6 w-6 text-orange-600 dark:text-orange-400 flex-shrink-0 mt-1" />
            <div className="flex-1">
              <h3 className="font-bold text-foreground text-lg mb-3">Disease Prevention Approaches (Last 7 Days Data)</h3>
              <p className="text-sm text-muted-foreground mb-4">Based on 7 days of sensor and leaf scan data, here are 3 approaches to prevent and cure diseases:</p>
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

      {/* Yield Input and Selling Suggestions */}
      <Card className="p-6 border-primary/30 bg-gradient-to-br from-primary/10 to-transparent">
        <div className="flex items-start gap-4">
          <BarChart3 className="h-6 w-6 text-primary flex-shrink-0 mt-1" />
          <div className="flex-1">
            <h3 className="font-bold text-foreground text-lg mb-3">Yield Analysis and Selling Strategy</h3>
            <p className="text-sm text-muted-foreground mb-4">Enter your total yield to get personalized selling recommendations based on real Guwahati market data</p>

            <div className="flex gap-3 mb-6">
              <input
                type="number"
                value={yieldInput}
                onChange={(e) => setYieldInput(e.target.value)}
                placeholder="Enter yield in kg (e.g., 1000)"
                className="flex-1 px-4 py-2 border border-border rounded-lg bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <Button
                onClick={generateYieldSuggestions}
                className="bg-primary hover:bg-primary/90 text-primary-foreground"
              >
                Analyze Yield
              </Button>
            </div>

            {showYieldAnalysis && sellingSuggestions.length > 0 && (
              <div className="space-y-4">
                <h4 className="font-semibold text-foreground mb-3">3 Selling & Improvement Approaches:</h4>
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
                        <p className="text-xs text-muted-foreground">Expected Revenue</p>
                        <p className="text-lg font-bold text-green-600 dark:text-green-400">{suggestion.expectedRevenue}</p>
                      </div>
                      <div className="p-2 bg-muted rounded">
                        <p className="text-xs text-muted-foreground">Timing</p>
                        <p className="text-sm font-semibold text-foreground">{suggestion.timing}</p>
                      </div>
                    </div>
                  </div>
                ))}

                <div className="mt-4 p-4 bg-primary/10 rounded-lg border border-primary/20">
                  <p className="text-sm font-semibold text-foreground mb-2">
                    ✓ Selected Approach: {sellingSuggestions[selectedApproach]?.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    All cards above update in real-time based on your selection. This will be included in your downloadable PDF report.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Conditionally show these sections only when yield is entered */}
      {showYieldAnalysis && yieldInput && (
        <>
          {/* Primary Simulation Outcome - Hero Section */}
          <Card className="p-8 border-2 border-primary/50 bg-gradient-to-br from-primary/5 via-background to-background">
            <div className="mb-2 flex items-center gap-2">
              <TrendingUp className="h-6 w-6 text-primary" />
              <h3 className="font-bold text-foreground text-2xl">If You Follow This Action</h3>
            </div>
            <p className="text-muted-foreground mb-6">Projected outcome based on AI analysis</p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                <p className="text-sm text-muted-foreground mb-1">Expected Yield Change</p>
                <p className="text-3xl font-bold text-green-600 dark:text-green-400">{simulationData.projectedOutcomes.yieldChange}</p>
                <p className="text-xs text-muted-foreground mt-2">~1,500 to 1,800 kg additional yield</p>
              </div>

              <div className="p-4 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg border border-emerald-200 dark:border-emerald-800">
                <p className="text-sm text-muted-foreground mb-1">Estimated Profit Change</p>
                <p className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">{simulationData.projectedOutcomes.profitChange}</p>
                <p className="text-xs text-muted-foreground mt-2">Based on current market rates</p>
              </div>

              <div className="p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800">
                <p className="text-sm text-muted-foreground mb-1">Risk Level</p>
                <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                  {simulationData.projectedOutcomes.riskLevel}
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  Probability based on current conditions
                </p>
              </div>

              <div className="p-4 bg-amber-50 dark:bg-amber-900/20 rounded-lg border border-amber-200 dark:border-amber-800">
                <p className="text-sm text-muted-foreground mb-1">Harvest Timing</p>
                <p className="text-3xl font-bold text-amber-600 dark:text-amber-400">{simulationData.projectedOutcomes.harvestTiming}</p>
                <p className="text-xs text-muted-foreground mt-2">Aligns with market peak</p>
              </div>
            </div>
          </Card>

          {/* Comparison: If No Action */}
          <Card className="p-6 border-red-200 dark:border-red-900/30 bg-red-50 dark:bg-red-900/10">
            <div className="flex items-start gap-4">
              <TrendingDown className="h-6 w-6 text-red-600 dark:text-red-400 flex-shrink-0 mt-1" />
              <div className="flex-1">
                <h3 className="font-bold text-foreground text-lg mb-4">If No Action Is Taken</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Yield Change</p>
                    <p className="text-2xl font-bold text-red-600 dark:text-red-400">{simulationData.noActionOutcomes.yieldChange}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Profit Change</p>
                    <p className="text-2xl font-bold text-red-600 dark:text-red-400">{simulationData.noActionOutcomes.profitChange}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground mb-2">Risk Level</p>
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
                <h3 className="font-bold text-foreground text-lg mb-4">Market Timing Insight</h3>
                <div className="space-y-3">
                  <p className="text-foreground">
                    <span className="font-semibold">Demand Forecast:</span> {simulationData.marketInsights.demandForecast} <span className="text-green-600 dark:text-green-400">↑</span>
                  </p>
                  <p className="text-foreground">
                    <span className="font-semibold">Price Change:</span> {simulationData.marketInsights.priceIncrease}
                  </p>
                  <p className="text-foreground">
                    <span className="font-semibold">Best Selling Window:</span> {simulationData.marketInsights.sellingWindow}
                  </p>
                </div>
              </div>
            </div>
          </Card>

          {/* Confidence & Reliability */}
          <Card className="p-6 bg-muted/50">
            <h3 className="font-bold text-foreground mb-4">Simulation Confidence</h3>
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-foreground">Model Accuracy</p>
                  <span className="text-sm font-bold text-primary">{simulationData.confidence.modelAccuracy}%</span>
                </div>
                <div className="w-full bg-border rounded-full h-2">
                  <div className="bg-primary h-2 rounded-full" style={{ width: `${simulationData.confidence.modelAccuracy}%` }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-foreground">Market Data Reliability</p>
                  <span className="text-sm font-bold text-primary">{simulationData.confidence.marketReliability}%</span>
                </div>
                <div className="w-full bg-border rounded-full h-2">
                  <div className="bg-primary h-2 rounded-full" style={{ width: `${simulationData.confidence.marketReliability}%` }} />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm font-medium text-foreground">Historical Trend Similarity</p>
                  <span className="text-sm font-bold text-primary">{simulationData.confidence.historicalSimilarity}%</span>
                </div>
                <div className="w-full bg-border rounded-full h-2">
                  <div className="bg-primary h-2 rounded-full" style={{ width: `${simulationData.confidence.historicalSimilarity}%` }} />
                </div>
              </div>

              <div className="mt-4 p-3 bg-primary/10 rounded-lg border border-primary/20">
                <p className="text-sm text-foreground">
                  <span className="font-semibold">Overall Confidence: </span>
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
                <h3 className="font-bold text-foreground text-lg mb-4">Risk Factors</h3>
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
                      <span className="font-semibold">General Market Risk:</span> Enter yield amount above to see specific risk factors for your situation
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
          <h3 className="font-bold text-foreground text-2xl mb-2">Download Your Action Plan</h3>
          <p className="text-muted-foreground text-sm">
            Save this comprehensive analysis as a PDF report for your records
          </p>
        </div>

        <div className="flex justify-center">
          <Button
            onClick={downloadPDF}
            disabled={loading || !simulationData}
            className="bg-primary hover:bg-primary/90 text-primary-foreground h-14 px-8 text-base font-semibold rounded-lg transition-all duration-200 hover:shadow-lg hover:shadow-primary/20 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download className="h-5 w-5 mr-2" />
            {loading ? 'Generating PDF...' : 'Download PDF Report'}
          </Button>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            <p className="text-sm text-red-600 dark:text-red-400 text-center">{error}</p>
          </div>
        )}

        <div className="mt-6 p-4 bg-muted/50 rounded-lg">
          <p className="text-xs text-center text-muted-foreground">
            The PDF includes all recommendations, market insights, yield analysis, disease prevention approaches, and risk factors
          </p>
        </div>
      </Card>
    </div>
  );
}
