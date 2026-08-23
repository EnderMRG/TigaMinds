'use client';

import { useState, useEffect, useMemo } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
  ReferenceLine,
} from 'recharts';
import { AlertCircle, Droplet, Thermometer, Wind, Sun, Lightbulb, Wifi, PenTool } from 'lucide-react';
import { collection, query, orderBy, limit, onSnapshot } from 'firebase/firestore';
import { db } from '@/lib/firebase';
import { CloudRain } from 'lucide-react';
import { apiClient } from '@/lib/api';

const IDEAL_RANGES = {
  soil_moisture: { min: 55, max: 65 },
  temperature: { min: 18, max: 26 },
  humidity: { min: 65, max: 75 },
  rainfall_7d: { min: 40, max: 80 },
};

const IDEAL_SOIL_MOISTURE =
  (IDEAL_RANGES.soil_moisture.min +
    IDEAL_RANGES.soil_moisture.max) / 2;

const IDEAL_TEMPERATURE =
  (IDEAL_RANGES.temperature.min +
    IDEAL_RANGES.temperature.max) / 2;

type Status = "optimal" | "warning" | "critical";

const getStatus = (
  value?: number,
  min?: number,
  max?: number
): Status => {
  if (value === undefined || min === undefined || max === undefined)
    return "warning";

  // optimal
  if (value >= min && value <= max) return "optimal";

  // critical if far away
  const range = max - min;
  if (value < min - range * 0.3 || value > max + range * 0.3)
    return "critical";

  // otherwise warning
  return "warning";
};

const statusStyles = {
  optimal: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  warning: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300",
  critical: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
};


export default function CultivationIntelligence() {
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'iot' | 'manual'>('iot');
  const [manualValues, setManualValues] = useState({
    moisture: '',
    temperature: '',
    humidity: '',
    rainfall7d: '',
    location: 'Field A - North Sector',
  });
  type SensorReading = {
    soil_moisture: number;
    temperature: number;
    humidity: number;
    rainfall_7d: number;
  };

  const [averages, setAverages] = useState<{
    soil_moisture?: number;
    temperature?: number;
    humidity?: number;
    rainfall_7d?: number;
  }>({});

  useEffect(() => {
    const fetchAverages = async () => {
      try {
        const data = await apiClient.get("/api/farm/averages");

        if (data.status === "success") {
          setAverages(data.averages);
        }
      } catch (err) {
        console.error("Failed to fetch farm averages", err);
      }
    };

    fetchAverages();

    // refresh every 10 seconds (optional)
    const interval = setInterval(fetchAverages, 10000);
    return () => clearInterval(interval);
  }, []);

  const [temperatureSeries, setTemperatureSeries] = useState<
    { time: string; value: number }[]
  >([]);

  useEffect(() => {
    const fetchTemperatureSeries = async () => {
      try {
        const data = await apiClient.get("/api/farm/temperature-series");
        setTemperatureSeries(data);
      } catch (err) {
        console.error("Failed to fetch temperature series", err);
      }
    };

    fetchTemperatureSeries();

    const interval = setInterval(fetchTemperatureSeries, 300000);
    return () => clearInterval(interval);
  }, []);

  const [iotReadings, setIotReadings] = useState<SensorReading[]>([]);
  const [backendAverages, setBackendAverages] = useState<{
    soil_moisture: number;
    temperature: number;
    humidity: number;
    rainfall_7d: number;
  } | null>(null);
  const [soilMoistureSeries, setSoilMoistureSeries] = useState<
    { time: string; value: number }[]
  >([]);

  useEffect(() => {
    const fetchSoilMoistureSeries = async () => {
      try {
        const data = await apiClient.get("/api/farm/soil-moisture-series");
        setSoilMoistureSeries(data);
      } catch (err) {
        console.error("Failed to fetch soil moisture series", err);
      }
    };

    fetchSoilMoistureSeries();

    // refresh every 5 minutes
    const interval = setInterval(fetchSoilMoistureSeries, 300000);
    return () => clearInterval(interval);
  }, []);

  const handleManualInputChange = (field: string, value: string) => {
    setManualValues((prev) => ({ ...prev, [field]: value }));
  };

  useEffect(() => {
    if (mode !== 'iot') return;

    const q = query(
      collection(
        db,
        'farms',
        'demo_farm',
        'sensors',
        'sensors_root',
        'readings'
      ),
      orderBy('timestamp', 'desc'),
      limit(30)
    );

    const unsub = onSnapshot(q, (snapshot) => {
      const rows = snapshot.docs.map(
        (doc) => doc.data() as SensorReading
      );
      console.log("🔥 Firestore readings:", rows);
      setIotReadings(rows);
    });

    return () => unsub();
  }, [mode]);

  useEffect(() => {
    if (!iotReadings.length) return;

    const sendToBackend = async () => {
      try {
        const data = await apiClient.post('/api/cultivation/aggregate', { readings: iotReadings });

        console.log("✅ Backend response:", data);
        setBackendAverages(data.averages);
      } catch (err) {
        console.error('Backend aggregation error:', err);
      }
    };

    sendToBackend();
  }, [iotReadings]);

  useEffect(() => {
    if (mode !== 'iot') return;

    const fetchLatestCultivation = async () => {
      try {
        const data = await apiClient.get("/api/cultivation/latest");

        console.log('🔍 IoT cultivation result:', data);
        console.log('🔍 AI recommendations:', data.ai_recommendations);

        if (!data.error) {
          setResult(data);
        }
      } catch (err) {
        console.error("Failed to fetch cultivation intelligence", err);
      }
    };

    fetchLatestCultivation();

    // refresh every 5 minutes
    const interval = setInterval(fetchLatestCultivation, 300000);
    return () => clearInterval(interval);
  }, [mode]);

  const [dailyMetrics, setDailyMetrics] = useState<
    {
      day: string;
      soil_moisture: number;
      temperature: number;
      humidity: number;
      rainfall: number;
    }[]
  >([]);

  useEffect(() => {
    const fetchDailyMetrics = async () => {
      try {
        const data = await apiClient.get("/api/farm/daily-metrics");
        setDailyMetrics(data);
      } catch (err) {
        console.error("Failed to fetch daily metrics", err);
      }
    };

    fetchDailyMetrics();
  }, []);

  const [smartAlert, setSmartAlert] = useState<{
    alert: boolean;
    mode: 'AI' | 'FALLBACK';
    risk_score?: number;
    reason?: string;
  } | null>(null);

  useEffect(() => {
    if (mode !== 'iot') return;

    const fetchSmartAlert = async () => {
      try {
        const data = await apiClient.get('/api/cultivation/smart-alert');
        setSmartAlert(data);
      } catch (err) {
        console.error('Smart alert fetch failed', err);
      }
    };

    fetchSmartAlert();
    const interval = setInterval(fetchSmartAlert, 60000); // every 1 min
    return () => clearInterval(interval);
  }, [mode]);

  const submitManualData = async () => {
    try {
      setLoading(true);

      const data = await apiClient.post('/api/cultivation', {
        soil_moisture: Number(manualValues.moisture),
        temperature: Number(manualValues.temperature),
        humidity: Number(manualValues.humidity),
        rainfall_last_24h: 0,
        rainfall_7d: Number(manualValues.rainfall7d),
        soil_ph: 5.2, // default Assam tea soil pH
      });

      console.log('🔍 Manual cultivation result:', data);
      console.log('🔍 AI recommendations:', data.ai_recommendations);
      setResult(data);

    } catch (err) {
      console.error(err);
      alert('Backend unavailable or invalid input');
    } finally {
      setLoading(false);
    }
  };

  const parseAIRecommendations = (recs: string[]) => {
    console.log('🔍 Parsing AI recommendations, input:', recs);
    const parsed: { action: string; reason?: string }[] = [];
    let lastAction: string | null = null;

    recs.forEach((line) => {
      const clean = line
        .replace(/\*\*/g, '')
        .replace(/^•\s*/, '')
        .trim();

      if (/^why[:\-]/i.test(clean)) {

        if (lastAction) {
          parsed.push({
            action: lastAction,
            reason: clean.replace(/^why[:\-]?\s*/i, ''),
          });
          lastAction = null;
        }
      } else {

        lastAction = clean;
      }
    });

    // In case an action had no explicit "why"
    if (lastAction) {
      parsed.push({ action: lastAction });
    }

    console.log('🔍 Parsed AI recommendations, output:', parsed);
    return parsed;
  };



  return (
    <div className="space-y-6">
      {/* Header with Mode Toggle */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-foreground">Cultivation Intelligence</h2>
          <p className="text-muted-foreground mt-1">
            {mode === 'iot' ? 'Real-time IoT monitoring and environmental analytics' : 'Manual data entry mode'}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => setMode('iot')}
            variant={mode === 'iot' ? 'default' : 'outline'}
            className="gap-2"
          >
            <Wifi className="h-4 w-4" />
            IoT Mode
          </Button>
          <Button
            onClick={() => setMode('manual')}
            variant={mode === 'manual' ? 'default' : 'outline'}
            className="gap-2"
          >
            <PenTool className="h-4 w-4" />
            Manual Entry
          </Button>
        </div>
      </div>

      {mode === 'iot' ? (
        <>
          {/* Alerts */}
          {smartAlert && (
            <div
              className={`flex gap-3 rounded-lg border p-4 ${smartAlert.alert
                ? smartAlert.mode === 'AI'
                  ? 'border-red-400 bg-red-50'
                  : 'border-yellow-400 bg-yellow-50'
                : 'border-green-400 bg-green-50'
                }`}
            >
              <AlertCircle className="mt-1" />

              <div>
                <h4 className="font-semibold">
                  {smartAlert.alert
                    ? 'Smart Crop Stress Alert'
                    : 'Crop Conditions Stable'}
                </h4>

                <p className="text-sm">
                  {smartAlert.alert
                    ? `Risk Score: ${smartAlert.risk_score}/100`
                    : 'No critical stress detected by AI'}
                </p>
              </div>
            </div>
          )}



          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                key: 'soil_moisture',
                icon: Droplet,
                label: 'Avg Soil Moisture',
                value: averages.soil_moisture,
                unit: '%',
                color: 'text-blue-600 dark:text-blue-400',
              },
              {
                key: 'temperature',
                icon: Thermometer,
                label: 'Avg Temperature',
                value: averages.temperature,
                unit: '°C',
                color: 'text-red-600 dark:text-red-400',
              },
              {
                key: 'humidity',
                icon: Wind,
                label: 'Avg Humidity',
                value: averages.humidity,
                unit: '%',
                color: 'text-cyan-600 dark:text-cyan-400',
              },
              {
                key: 'rainfall_7d',
                icon: CloudRain,
                label: 'Avg Rainfall (Last 7 Days)',
                value: averages.rainfall_7d,
                unit: 'mm',
                color: 'text-indigo-600 dark:text-indigo-400',
              },
            ].map((metric, idx) => {
              const Icon = metric.icon;

              const range =
                IDEAL_RANGES[metric.key as keyof typeof IDEAL_RANGES];

              const status = getStatus(
                metric.value,
                range.min,
                range.max
              );

              return (
                <Card key={idx} className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <Icon className={`h-5 w-5 ${metric.color}`} />
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${statusStyles[status]
                        }`}
                    >
                      {status}
                    </span>
                  </div>

                  <p className="text-sm text-muted-foreground">
                    {metric.label}
                  </p>

                  <p className="text-2xl font-bold text-foreground mt-2">
                    {metric.value !== undefined
                      ? `${metric.value.toFixed(1)} ${metric.unit}`
                      : '--'}
                  </p>
                </Card>
              );
            })}
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Moisture Levels */}
            <Card className="p-6">
              <h3 className="font-semibold text-foreground mb-4">Soil Moisture Over Time (Last 24h) Vs Optimal</h3>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={soilMoistureSeries}                >
                  <defs>
                    <linearGradient id="colorMoisture" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#35a857" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#35a857" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="time"
                    stroke="#6b7280"
                    tick={{ fontSize: 12 }}
                    interval={3}
                  />

                  <YAxis stroke="#6b7280" />
                  <Tooltip
                    formatter={(value: number) => [`${value}%`, 'Soil Moisture']}
                    labelFormatter={(label) => `Time: ${label}`}
                    contentStyle={{
                      backgroundColor: '#1f2937',
                      border: 'none',
                      borderRadius: '8px',
                      color: '#f3f4f6',
                    }}
                  />
                  <Area type="monotone" dataKey="value" stroke="#35a857" fill="url(#colorMoisture)" />
                  <ReferenceLine
                    y={IDEAL_SOIL_MOISTURE}
                    stroke="#166534"
                    strokeWidth={2}
                    strokeDasharray="6 6"
                    label={{
                      value: "Optimal (60%)",
                      position: "right",
                      fill: "#166534",
                      fontSize: 12,
                    }}
                  />
                  <Legend />
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            {/* Temperature Comparison */}
            <Card className="p-6">
              <h3 className="font-semibold text-foreground mb-4">
                Temperature Over Time (Last 24h) vs Optimal
              </h3>

              <ResponsiveContainer width="100%" height={250}>
                <AreaChart
                  data={Array.isArray(temperatureSeries) ? temperatureSeries.map((d) => ({
                    ...d,
                    ideal: IDEAL_TEMPERATURE,
                  })) : []}
                >
                  {/* Gradient */}
                  <defs>
                    <linearGradient id="colorTemp" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>

                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />

                  <XAxis
                    dataKey="time"
                    stroke="#6b7280"
                    tick={{ fontSize: 12 }}
                    interval={3}
                  />

                  <YAxis stroke="#6b7280" />

                  <Tooltip
                    formatter={(value: number) => [`${value} °C`, 'Temperature']}
                    labelFormatter={(label) => `Time: ${label}`}
                    contentStyle={{
                      backgroundColor: '#1f2937',
                      border: 'none',
                      borderRadius: '8px',
                      color: '#f3f4f6',
                    }}
                  />

                  {/* Actual temperature */}
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#ef4444"
                    fill="url(#colorTemp)"
                    strokeWidth={2}
                    name="Temperature"
                  />

                  {/* Optimal dashed line */}
                  <ReferenceLine
                    y={IDEAL_TEMPERATURE}
                    stroke="#166534"
                    strokeWidth={2}
                    strokeDasharray="6 6"
                    label={{
                      value: "Optimal (60%)",
                      position: "right",
                      fill: "#166534",
                      fontSize: 12,
                    }}
                  />
                  <Legend />
                </AreaChart>
              </ResponsiveContainer>
            </Card>

            {/* Weekly Environmental Data */}
            <Card className="p-6 lg:col-span-2">
              <h3 className="font-semibold text-foreground mb-4">
                Environmental Metrics — Last 7 Days
              </h3>

              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={dailyMetrics}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="day" stroke="#6b7280" />
                  <YAxis stroke="#6b7280" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1f2937',
                      border: 'none',
                      borderRadius: '8px',
                      color: '#f3f4f6',
                    }}
                  />
                  <Legend />

                  <Bar dataKey="soil_moisture" fill="#22c55e" name="Soil Moisture (%)" />
                  <Bar dataKey="temperature" fill="#ef4444" name="Temperature (°C)" />
                  <Bar dataKey="humidity" fill="#06b6d4" name="Humidity (%)" />
                  <Bar dataKey="rainfall" fill="#3b82f6" name="Rainfall (mm)" />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </div>
          {result && (
            <Card className="p-6 border-green-300 bg-green-50 rounded-xl">
              <h3 className="font-semibold text-foreground mb-4">
                Live Cultivation Intelligence (IoT)
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Health Score</p>
                  <p className="text-2xl font-bold">{result.health_score}/100</p>
                </div>

                <div>
                  <p className="text-sm text-muted-foreground">Drought Risk</p>
                  <p className="font-semibold">{result.drought_risk}</p>
                </div>

                <div>
                  <p className="text-sm text-muted-foreground">Pest Risk</p>
                  <p className="font-semibold">{result.pest_risk}</p>
                </div>
              </div>

              <div className="mt-4">
                <p className="text-sm text-muted-foreground">Recommended Action</p>
                <p className="font-medium">{result.action}</p>
              </div>
            </Card>
          )}


        </>
      ) : (
        <>
          {/* Manual Entry Form */}
          <Card className="p-6">
            <h3 className="font-semibold text-foreground mb-6">Enter Environmental Data</h3>
            <div className="space-y-4">
              {/* Input Fields Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Soil Moisture (%)</label>
                  <input
                    type="number"
                    placeholder="Enter value (0-100)"
                    value={manualValues.moisture}
                    onChange={(e) => handleManualInputChange('moisture', e.target.value)}
                    className="w-full px-4 py-2 border border-border rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Temperature (°C)</label>
                  <input
                    type="number"
                    placeholder="Enter value"
                    value={manualValues.temperature}
                    onChange={(e) => handleManualInputChange('temperature', e.target.value)}
                    className="w-full px-4 py-2 border border-border rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">Humidity (%)</label>
                  <input
                    type="number"
                    placeholder="Enter value (0-100)"
                    value={manualValues.humidity}
                    onChange={(e) => handleManualInputChange('humidity', e.target.value)}
                    className="w-full px-4 py-2 border border-border rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-2">
                    Rainfall (Last 7 Days, mm)
                  </label>
                  <input
                    type="number"
                    placeholder="Enter rainfall in mm"
                    value={manualValues.rainfall7d}
                    onChange={(e) => handleManualInputChange('rainfall7d', e.target.value)}
                    className="w-full px-4 py-2 border border-border rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
              </div>

              {/* Submit Button */}
              <div className="flex gap-3 pt-4">
                <Button
                  className="flex-1 bg-primary text-primary-foreground hover:bg-primary/90"
                  onClick={submitManualData}
                  disabled={loading}
                >
                  {loading ? 'Analyzing...' : 'Analyze Field Data'}
                </Button>

                <Button
                  variant="outline"
                  onClick={() =>
                    setManualValues({
                      moisture: '',
                      temperature: '',
                      humidity: '',
                      rainfall7d: '',
                      location: manualValues.location,
                    })
                  }
                  className="flex-1"
                >
                  Clear Form
                </Button>
              </div>
            </div>
          </Card>
          {result && (
            <Card className="p-6 border-green-300 bg-green-50 mt-6 rounded-xl">
              <h3 className="font-semibold text-foreground mb-4">
                Cultivation Intelligence Result
              </h3>

              {/* Top summary */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <p className="text-sm text-muted-foreground">Health Score</p>
                  <p className="text-2xl font-bold text-foreground">
                    {result.health_score}/100
                  </p>
                </div>

                <div>
                  <p className="text-sm text-muted-foreground">Drought Risk</p>
                  <p
                    className={`font-semibold ${result.drought_risk === 'High'
                      ? 'text-red-600'
                      : result.drought_risk === 'Medium'
                        ? 'text-yellow-600'
                        : 'text-green-600'
                      }`}
                  >
                    {result.drought_risk}
                  </p>
                </div>

                <div>
                  <p className="text-sm text-muted-foreground">Pest Risk</p>
                  <p
                    className={`font-semibold ${result.pest_risk === 'High'
                      ? 'text-red-600'
                      : result.pest_risk === 'Medium'
                        ? 'text-yellow-600'
                        : 'text-green-600'
                      }`}
                  >
                    {result.pest_risk}
                  </p>
                </div>
              </div>

              {/* Action */}
              <div className="mt-4">
                <p className="text-sm text-muted-foreground">Recommended Action</p>
                <p className="font-medium text-foreground">{result.action}</p>
              </div>

              {/* Divider */}
              <div className="my-6 border-t border-green-200" />

              {/* ✅ Health Score Breakdown (NOW INSIDE GREEN CARD) */}
              {result.score_explanation && (
                <div>
                  <p className="text-sm font-semibold text-foreground mb-3">
                    Health Score Breakdown
                  </p>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {Object.entries(result.score_explanation).map(
                      ([key, value]: [string, any]) => (
                        <div
                          key={key}
                          className="p-3 rounded-lg border bg-white text-center"
                        >
                          <p className="text-xs text-muted-foreground uppercase">
                            {key.replace('_', ' ')}
                          </p>

                          <p
                            className={`mt-1 text-sm font-semibold ${value === 'Optimal'
                              ? 'text-green-600'
                              : 'text-yellow-600'
                              }`}
                          >
                            {value}
                          </p>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}
            </Card>
          )}


        </>
      )}

      {/* AI Recommendations */}
      <Card className="p-6 border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
        <div className="flex items-center gap-2 mb-4">
          <Lightbulb className="h-5 w-5 text-primary" />
          <h3 className="font-semibold text-foreground text-lg">
            AI Recommendations
          </h3>
        </div>

        {!result && (
          <p className="text-sm text-muted-foreground">
            Run analysis to generate AI-powered cultivation recommendations.
          </p>
        )}

        {loading && (
          <p className="text-sm text-muted-foreground">
            Generating AI insights…
          </p>
        )}

        {(() => {
          console.log('🔍 Checking AI recommendations rendering:');
          console.log('  - result exists:', !!result);
          console.log('  - result.ai_recommendations exists:', !!result?.ai_recommendations);
          console.log('  - result.ai_recommendations value:', result?.ai_recommendations);
          return null;
        })()}

        {result?.ai_recommendations && (
          <div className="space-y-4">
            {parseAIRecommendations(result.ai_recommendations).map(
              (rec, idx) => (
                <div
                  key={idx}
                  className="rounded-xl border bg-white p-4"
                >
                  <p className="font-medium text-foreground">
                    {rec.action}
                  </p>

                  {rec.reason && (
                    <p className="mt-2 text-sm text-muted-foreground">
                      <span className="font-medium text-foreground">
                        Why this matters:
                      </span>{' '}
                      {rec.reason}
                    </p>
                  )}
                </div>
              )
            )}
          </div>
        )}
      </Card>

    </div>
  );
}
