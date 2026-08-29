"use client";

import { useLanguage } from "@/context/LanguageContext";
import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Activity, AlertTriangle, Droplets, ShieldAlert, Globe, IndianRupee, Leaf } from "lucide-react";
import { apiClient } from "@/lib/api";

type ForecastData = {
  date: string;
  bau: number;
  stress: number;
  optimistic: number;
};

type Financials = {
  bau_loss: number;
  optimistic_loss: number;
  savings: number;
};

export default function DigitalTwin() {
  const { t } = useLanguage();
  const [forecastData, setForecastData] = useState<ForecastData[]>([]);
  const [summary, setSummary] = useState<string>("");
  const [loading, setLoading] = useState(true);

  // Sliders state
  const [irrigationFreq, setIrrigationFreq] = useState([3]); // days
  const [interventionSpeed, setInterventionSpeed] = useState([2]); // days
  const [climateModel, setClimateModel] = useState<string>("normal");
  const [expectedYield, setExpectedYield] = useState<number>(1500); // kg
  const [financials, setFinancials] = useState<Financials | null>(null);

  useEffect(() => {
    const fetchForecast = async () => {
      setLoading(true);
      try {
        const response = await apiClient.post("/api/digital-twin/forecast/demo_field", {
          irrigation_freq_days: irrigationFreq[0],
          disease_intervention_days: interventionSpeed[0],
          climate_model: climateModel,
          expected_monthly_yield: expectedYield
        });
        setForecastData(response.forecast);
        setSummary(response.summary);
        if (response.financials) setFinancials(response.financials);
      } catch (err) {
        console.error("Failed to fetch digital twin forecast", err);
      } finally {
        setLoading(false);
      }
    };

    // Debounce the fetch slightly for slider smoothness
    const timer = setTimeout(() => {
      fetchForecast();
    }, 300);

    return () => clearTimeout(timer);
  }, [irrigationFreq, interventionSpeed, climateModel, expectedYield]);

  return (
    <div className="flex flex-col space-y-4 animate-in fade-in duration-500 min-h-0">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 sm:gap-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight">{t('digitalTwin')}</h2>
          <p className="text-xs sm:text-sm text-muted-foreground">
            {t('fiveYearSimDesc')}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 min-h-0">
        
        {/* Left Column: Controls */}
        <div className="lg:col-span-1 flex flex-col gap-4 lg:overflow-y-auto lg:pr-2 lg:max-h-[calc(100vh-200px)] scrollbar-thin">

          <Card className="p-4 space-y-5 shadow-sm">
            <div>
              <h3 className="font-bold text-base mb-1 flex items-center gap-2">
                <Activity className="h-4 w-4 text-blue-500" />
                {t('scenarioControls')}
              </h3>
              <p className="text-xs text-muted-foreground mb-4">
                {t('scenarioControlsDesc')}
              </p>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <label className="text-sm font-medium flex items-center gap-2">
                  <Globe className="h-4 w-4 text-purple-500" />
                  {t('macroClimate')}
                </label>
              </div>
              <Select value={climateModel} onValueChange={setClimateModel}>
                <SelectTrigger>
                  <SelectValue placeholder={t('selectClimateModel')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="normal">{t('normalCycleBaseline')}</SelectItem>
                  <SelectItem value="el_nino">{t('elNinoSevereDrought')}</SelectItem>
                  <SelectItem value="la_nina">{t('laNinaHeavyMonsoon')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <label className="text-sm font-medium flex items-center gap-2">
                  <Leaf className="h-4 w-4 text-emerald-600" />
                  {t('expectedMonthlyYield')}
                </label>
              </div>
              <Input 
                type="number" 
                value={expectedYield} 
                onChange={(e) => setExpectedYield(Number(e.target.value) || 0)}
                className="font-mono"
              />
              <p className="text-xs text-muted-foreground">
                {t('expectedYieldDesc')}
              </p>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <label className="text-sm font-medium flex items-center gap-2">
                  <Droplets className="h-4 w-4 text-blue-500" />
                  {t('irrigationFreq')}
                </label>
                <span className="text-sm font-bold text-blue-600 dark:text-blue-400">
                  {t('every')} {irrigationFreq[0]} {t('days2')}
                </span>
              </div>
              <Slider
                value={irrigationFreq}
                onValueChange={setIrrigationFreq}
                min={1}
                max={30}
                step={1}
                className="[&_[role=slider]]:bg-blue-500"
              />
              <p className="text-xs text-muted-foreground">
                {t('irrigationFreqDesc')}
              </p>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <label className="text-sm font-medium flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-emerald-500" />
                  {t('interventionSpeed')}
                </label>
                <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                  {interventionSpeed[0]} {t('days2')}
                </span>
              </div>
              <Slider
                value={interventionSpeed}
                onValueChange={setInterventionSpeed}
                min={1}
                max={14}
                step={1}
                className="[&_[role=slider]]:bg-emerald-500"
              />
              <p className="text-xs text-muted-foreground">
                {t('interventionSpeedDesc')}
              </p>
            </div>

          </Card>

          <Card className={`p-4 shadow-sm border-l-4 flex-shrink-0 ${forecastData.length && forecastData[forecastData.length - 1].optimistic >= 0.7 ? 'border-emerald-500' : 'border-amber-500'}`}>
            <h3 className="font-bold mb-2 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              {t('aiProjectionSummary')}
            </h3>
            <p className="text-sm leading-relaxed">
              {loading && !summary ? t('simulatingDataPoints') : summary}
            </p>
          </Card>

          {financials && (
            <Card className="p-4 shadow-sm border-l-4 border-blue-500 bg-blue-50/50 dark:bg-blue-950/20 flex-shrink-0">
              <h3 className="font-bold mb-3 flex items-center gap-2 text-sm">
                <IndianRupee className="h-4 w-4 text-blue-500" />
                {t('fiveYearFinancialImpact')}
              </h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('bauRevenueLoss')}</span>
                  <span className="font-semibold text-red-500">₹{(financials.bau_loss / 100000).toFixed(1)}L</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">{t('optimisticLoss')}</span>
                  <span className="font-semibold text-amber-500">₹{(financials.optimistic_loss / 100000).toFixed(1)}L</span>
                </div>
                <div className="pt-2 border-t flex justify-between font-bold">
                  <span>{t('netSavings')}</span>
                  <span className="text-emerald-500">₹{(financials.savings / 100000).toFixed(1)} Lakhs</span>
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Chart */}
        <div className="lg:col-span-3 min-h-[380px] lg:min-h-0 h-full">
          <Card className="p-3 sm:p-5 h-full flex flex-col shadow-sm">
            <div className="mb-3 sm:mb-4">
              <h3 className="font-bold text-sm sm:text-base">{t('ndviForecast5Year')}</h3>
              <p className="text-xs text-muted-foreground">
                {t('ndviForecastDesc')}
              </p>
            </div>
            
            <div className="flex-1 w-full min-h-[300px] relative">
              {loading && forecastData.length === 0 && (
                <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10 rounded-xl">
                  <div className="animate-pulse font-bold text-muted-foreground">{t('runningSimulation')}</div>
                </div>
              )}
              
              <ResponsiveContainer width="100%" height={340}>

                <LineChart data={forecastData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} vertical={false} />
                  <XAxis 
                    dataKey="date" 
                    tick={{ fontSize: 12 }} 
                    interval={5} 
                    stroke="#888888" 
                    tickMargin={10}
                  />
                  <YAxis 
                    domain={[0.1, 0.9]} 
                    tick={{ fontSize: 12 }} 
                    stroke="#888888"
                    tickMargin={10}
                    label={{ value: 'NDVI (Crop Health)', angle: -90, position: 'insideLeft', style: { fill: '#888888' } }}
                  />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'hsl(var(--background))', borderColor: 'hsl(var(--border))', borderRadius: '8px' }}
                    labelStyle={{ fontWeight: 'bold', color: 'hsl(var(--foreground))', marginBottom: '8px' }}
                  />
                  <Legend verticalAlign="top" height={36} iconType="circle" />
                  
                  <Line 
                    type="monotone" 
                    dataKey="optimistic" 
                    name={t('optimisticYourPlan')} 
                    stroke="#10b981" 
                    strokeWidth={4} 
                    dot={false}
                    activeDot={{ r: 8 }}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="bau" 
                    name={t('businessAsUsual')} 
                    stroke="#3b82f6" 
                    strokeWidth={2} 
                    strokeDasharray="5 5"
                    dot={false} 
                  />
                  <Line 
                    type="monotone" 
                    dataKey="stress" 
                    name={t('extremeStressScenario')} 
                    stroke="#ef4444" 
                    strokeWidth={2} 
                    strokeDasharray="3 3"
                    dot={false} 
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

      </div>
    </div>
  );
}
