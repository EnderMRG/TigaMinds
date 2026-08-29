'use client';

import { useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api';
import { useAlerts } from '@/context/alerts-context';
import {
  Satellite, AlertTriangle, CheckCircle2, Leaf, Droplets,
  Sun, RefreshCw, Info, Loader2, Zap, Activity
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';

// ── Dynamic import: Leaflet MUST NOT render on server ─────────────────────────
const SatelliteMapDraw = dynamic(
  () => import('./satellite-map-draw'),
  {
    ssr: false,
    loading: () => (
      <div className="h-[420px] w-full bg-muted/20 rounded-xl flex items-center justify-center border border-dashed border-muted-foreground/20">
        <div className="text-muted-foreground text-sm flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading satellite map…
        </div>
      </div>
    ),
  }
);

// ── Types ─────────────────────────────────────────────────────────────────────
interface AnalysisResult {
  mean_ndvi: number;
  mean_evi: number;
  mean_ndwi: number;
  health_class: 'Healthy' | 'Moderate' | 'Stressed';
  heatmap_b64: string;
  scene_id: string;
  acquired: string;
  cloud_cover: number;
  data_source: 'sentinel-2' | 'synthetic';
  field_id: string;
  scan_id: string;
  cached: boolean;
  history: Array<{ date: string; mean_ndvi: number; mean_evi: number; mean_ndwi: number; health_class: string }>;
  anomaly: { is_anomaly: boolean; drop: number; message: string };
  timestamp: string;
}

// ── Health class styling ──────────────────────────────────────────────────────
const HEALTH_CONFIG = {
  Healthy:  { color: 'text-emerald-400', bg: 'bg-emerald-500/15 border-emerald-500/30', icon: CheckCircle2 },
  Moderate: { color: 'text-amber-400',   bg: 'bg-amber-500/15 border-amber-500/30',     icon: AlertTriangle },
  Stressed: { color: 'text-red-400',     bg: 'bg-red-500/15 border-red-500/30',         icon: AlertTriangle },
};

// ── NDVI gauge bar ────────────────────────────────────────────────────────────
function NDVIBar({ value, label }: { value: number; label: string }) {
  const pct = Math.round(((value + 1) / 2) * 100);
  const color = value >= 0.6 ? 'bg-emerald-500' : value >= 0.3 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className="font-mono font-semibold text-foreground">{value.toFixed(3)}</span>
      </div>
      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${Math.max(2, pct)}%` }}
        />
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function SatelliteCropHealth() {
  const [drawnGeometry, setDrawnGeometry] = useState<any>(null);
  const [heatmapBounds, setHeatmapBounds] = useState<[[number, number], [number, number]] | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(true);
  const { addAlert } = useAlerts();

  // ── Handle polygon drawn ───────────────────────────────────────────────────
  const handlePolygonDrawn = useCallback((geometry: any, bounds: any) => {
    setDrawnGeometry(geometry);
    setResult(null);
    setError(null);
    // Store bounds as [[sw_lat, sw_lng], [ne_lat, ne_lng]]
    setHeatmapBounds([
      [bounds.getSouth(), bounds.getWest()],
      [bounds.getNorth(), bounds.getEast()],
    ]);
  }, []);

  // ── Run analysis ───────────────────────────────────────────────────────────
  const runAnalysis = async () => {
    if (!drawnGeometry) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const stages = [
      'Searching public Sentinel-2 archive…',
      'Selecting optimal scene (cloud cover < 20%)…',
      'Loading Sentinel-2 surface-reflectance bands…',
      'Computing NDVI · EVI · NDWI indices…',
      'Generating colorized heatmap…',
    ];
    let si = 0;
    setLoadingStage(stages[0]);
    const stageTimer = setInterval(() => {
      si = Math.min(si + 1, stages.length - 1);
      setLoadingStage(stages[si]);
    }, 8000);

    try {
      const data: AnalysisResult = await apiClient.post('/api/crop-health/analyze', {
        geometry: drawnGeometry,
        field_id: 'demo_field_jorhat',
        demo_mode: demoMode,
      });
      setResult(data);
      // Fire alerts based on health class and anomaly
      if (data.health_class === 'Stressed') {
        addAlert({
          title: 'Satellite: Crop Stress Detected',
          message: `NDVI ${data.mean_ndvi.toFixed(3)} indicates stressed vegetation. Immediate field inspection recommended.`,
          severity: 'critical',
          source: 'satellite_health_class',
        });
      } else if (data.health_class === 'Moderate') {
        addAlert({
          title: 'Satellite: Moderate Crop Health',
          message: `NDVI ${data.mean_ndvi.toFixed(3)} — crop health is below optimal. Monitor closely.`,
          severity: 'info',
          source: 'satellite_health_class',
        });
      }
      if (data.anomaly?.is_anomaly) {
        addAlert({
          title: 'Satellite: NDVI Anomaly Detected',
          message: data.anomaly.message || `Unusual NDVI drop of ${data.anomaly.drop?.toFixed(3)} detected vs historical baseline.`,
          severity: 'warning',
          source: 'satellite_ndvi_anomaly',
        });
      }
    } catch (err: any) {
      setError(err?.message || 'Analysis failed. Please try again.');
    } finally {
      clearInterval(stageTimer);
      setLoading(false);
      setLoadingStage('');
    }
  };

  const heatmapDataUrl = result?.heatmap_b64
    ? `data:image/png;base64,${result.heatmap_b64}`
    : undefined;

  const hc = result ? HEALTH_CONFIG[result.health_class] : null;
  const HCIcon = hc?.icon ?? CheckCircle2;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Satellite className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-foreground">Satellite Crop Health Monitor</h2>
            <p className="text-xs text-muted-foreground">Draw a field boundary → Sentinel-2 imagery → NDVI heatmap</p>
          </div>
        </div>
        {result && (
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            {result.cached && <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 text-xs border border-blue-500/20">Cached (24h)</span>}
            {result.data_source === 'sentinel-2' && (
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 text-xs border border-emerald-500/20">Sentinel-2 live</span>
            )}
            {result.data_source === 'synthetic' && (
              <span className="px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 text-xs border border-purple-500/20">Demo data</span>
            )}
          </span>
        )}
      </div>

      {/* Anomaly warning banner */}
      {result?.anomaly?.is_anomaly && result.anomaly.message && (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{result.anomaly.message} (NDVI Δ {result.anomaly.drop.toFixed(3)})</span>
        </div>
      )}

      {/* Map + controls grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Map panel */}
        <Card className="xl:col-span-2 p-4 space-y-3 bg-card border-border">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm font-semibold text-foreground">Field Boundary</span>
            <span className="text-xs text-muted-foreground">Use the polygon or rectangle tool to mark your field</span>
          </div>
          <SatelliteMapDraw
            onPolygonDrawn={handlePolygonDrawn}
            heatmapDataUrl={heatmapDataUrl}
            heatmapBounds={result && heatmapBounds ? heatmapBounds : undefined}
            center={[26.57, 93.84]}
            zoom={13}
          />

          {/* NDVI heatmap legend */}
          <div className="flex items-center gap-2 pt-1">
            <span className="text-xs text-muted-foreground">NDVI Scale:</span>
            <div className="flex-1 h-3 rounded-full" style={{ background: 'linear-gradient(to right, #d73027, #fc8d59, #fee08b, #d9ef8b, #91cf60, #1a9850)' }} />
            <div className="flex gap-4 text-xs text-muted-foreground">
              <span>Stressed</span>
              <span>Moderate</span>
              <span>Healthy</span>
            </div>
          </div>
        </Card>

        {/* Right panel */}
        <div className="space-y-4">
          {/* Analyze button */}
          <Card className="p-4 bg-gradient-to-br from-emerald-950/50 to-background border-emerald-800/30">
            <Button
              onClick={runAnalysis}
              disabled={!drawnGeometry || loading}
              className="w-full h-12 bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-semibold rounded-lg transition-all duration-200 hover:shadow-lg hover:shadow-emerald-500/25 disabled:opacity-40"
            >
              {loading ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Analyzing…</span>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Satellite className="h-4 w-4" />
                  <span>{drawnGeometry ? 'Run Satellite Analysis' : 'Draw a field boundary first'}</span>
                </div>
              )}
            </Button>

            <label className="mt-3 flex items-center justify-center gap-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={demoMode}
                onChange={(event) => setDemoMode(event.target.checked)}
                className="h-3.5 w-3.5 accent-emerald-500"
              />
              Use demo data if Planet imagery is unavailable
            </label>

            {loading && (
              <div className="mt-3 space-y-2">
                <p className="text-xs text-muted-foreground text-center animate-pulse">{loadingStage}</p>
                <div className="h-1 bg-muted rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-emerald-500 to-cyan-500 rounded-full animate-[pulse_2s_ease-in-out_infinite]" style={{ width: '60%' }} />
                </div>
                <p className="text-xs text-center text-muted-foreground/60">Planet scene activation may take 10–60 s</p>
              </div>
            )}

            {error && (
              <p className="mt-3 text-xs text-red-400 text-center">{error}</p>
            )}

            {!drawnGeometry && !loading && (
              <p className="mt-3 text-xs text-muted-foreground text-center">
                1. Use the map tools to outline your field<br />
                2. Click <strong>Run Satellite Analysis</strong>
              </p>
            )}
          </Card>

          {/* Results summary card */}
          {result && (
            <Card className={`p-4 border ${hc?.bg}`}>
              {/* Health classification */}
              <div className="flex items-center gap-2 mb-4">
                <HCIcon className={`h-5 w-5 ${hc?.color}`} />
                <div>
                  <p className={`font-bold text-lg ${hc?.color}`}>{result.health_class}</p>
                  <p className="text-xs text-muted-foreground">
                    {result.acquired ? new Date(result.acquired).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : 'Recent scan'}
                    {result.cloud_cover > 0 && ` · ☁ ${(result.cloud_cover * 100).toFixed(0)}%`}
                  </p>
                </div>
              </div>

              {/* Index gauges */}
              <div className="space-y-3">
                <NDVIBar value={result.mean_ndvi} label="NDVI  (Vegetation)" />
                <NDVIBar value={result.mean_evi}  label="EVI   (Enhanced Veg.)" />
                <NDVIBar value={result.mean_ndwi} label="NDWI  (Water Content)" />
              </div>

              {/* Threshold legend */}
              <div className="mt-3 pt-3 border-t border-border/50 grid grid-cols-3 gap-1 text-center">
                {[['≥ 0.6', 'Healthy', 'text-emerald-400'], ['0.3–0.6', 'Moderate', 'text-amber-400'], ['< 0.3', 'Stressed', 'text-red-400']].map(([range, label, cls]) => (
                  <div key={range}>
                    <p className={`text-xs font-semibold ${cls}`}>{range}</p>
                    <p className="text-xs text-muted-foreground">{label}</p>
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground/60 mt-2 text-center italic">Thresholds are indicative, not universal</p>
            </Card>
          )}
        </div>
      </div>

      {/* Temporal trend chart */}
      {result && result.history && result.history.length > 0 && (
        <Card className="p-6 bg-card border-border">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="h-5 w-5 text-emerald-400" />
            <h3 className="font-semibold text-foreground">NDVI Temporal Health Curve</h3>
            <span className="ml-auto text-xs text-muted-foreground">Historical Data · {result.history.length} scans</span>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={result.history} margin={{ top: 5, right: 16, left: -10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                tickFormatter={(v) => v.slice(5)}
              />
              <YAxis domain={[-0.1, 1]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8, fontSize: 12 }}
                formatter={(v: any) => [Number(v).toFixed(3)]}
              />
              {/* Health threshold lines */}
              <ReferenceLine y={0.6} stroke="#22c55e" strokeDasharray="5 3" strokeOpacity={0.5}
                label={{ value: 'Healthy', position: 'right', fontSize: 10, fill: '#22c55e' }} />
              <ReferenceLine y={0.3} stroke="#f59e0b" strokeDasharray="5 3" strokeOpacity={0.5}
                label={{ value: 'Stressed', position: 'right', fontSize: 10, fill: '#f59e0b' }} />

              <Line type="monotone" dataKey="mean_ndvi" name="NDVI" stroke="#22c55e" strokeWidth={2.5} dot={{ r: 4, fill: '#22c55e' }} activeDot={{ r: 6 }} />
              <Line type="monotone" dataKey="mean_evi"  name="EVI"  stroke="#06b6d4" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
              <Line type="monotone" dataKey="mean_ndwi" name="NDWI" stroke="#8b5cf6" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
            </LineChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div className="flex gap-4 justify-center mt-2">
            {[['NDVI', '#22c55e'], ['EVI', '#06b6d4'], ['NDWI', '#8b5cf6']].map(([name, color]) => (
              <div key={name} className="flex items-center gap-1.5">
                <div className="w-4 h-0.5 rounded" style={{ background: color }} />
                <span className="text-xs text-muted-foreground">{name}</span>
              </div>
            ))}
          </div>
        </Card>
      )}



      {/* How it works */}
      <Card className="p-4 bg-muted/20 border-border/50">
        <div className="flex items-start gap-2">
          <Info className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <p className="text-xs text-muted-foreground leading-relaxed">
            <strong className="text-foreground">How it works:</strong> The polygon is sent to the public Earth Search Sentinel-2 catalog for a recent low-cloud scene. Red, green, blue, and NIR surface-reflectance bands are clipped to the field and processed: NDVI=(NIR−Red)/(NIR+Red), EVI=2.5·(NIR−Red)/(NIR+6·Red−7.5·Blue+1), NDWI=(Green−NIR)/(Green+NIR). Results are stored in SQLite history.
          </p>
        </div>
      </Card>
    </div>
  );
}
