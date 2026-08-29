'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api';
import {
  Navigation, AlertTriangle, CheckCircle2, Clock, Route,
  Truck, ArrowRightLeft, Loader2, Info, TrendingDown, ShieldCheck, ShieldAlert
} from 'lucide-react';

// ── Leaflet route map (SSR-safe) ──────────────────────────────────────────────
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

// ── Types ─────────────────────────────────────────────────────────────────────
interface AuctionCenter { key: string; name: string; lat: number; lng: number }

interface Segment {
  coordinates: [number, number][];
  risk_level: string;
  risk_score: number;
  rainfall_intensity: number;
  slope_factor: number;
  delay_flag: number;
  corridor_name?: string | null;
  hazard_type?: string | null;
  hazard_description?: string | null;
  severity?: 'low' | 'moderate' | 'severe' | null;
}

interface RouteResult {
  origin: { lat: number; lng: number; name: string };
  destination: { lat: number; lng: number; name: string; key: string };
  distance_km: number;
  duration_min: number;
  route_risk: 'LOW' | 'MEDIUM' | 'HIGH';
  risk_score: number;
  segments: Segment[];
  geometry: { type: string; coordinates: [number, number][] };
  spoilage_probability: number;
  spoilage_pct: number;
  base_price: number;
  effective_price: number;
  recommended_harvest_shift: number;
  route_advisories?: Array<{ hazard_type: string; description: string; severity: string; corridor_name?: string }>;
  severe_hazard_warning?: string | null;
  alternate_route: {
    destination_key: string;
    destination_name: string;
    route_risk: string;
    risk_score: number;
    distance_km: number;
    duration_min: number;
    spoilage_pct: number;
    effective_price: number;
    segments: Segment[];
    geometry: { type: string; coordinates: [number, number][] };
  } | null;
  cached: boolean;
  demo_scenario?: boolean;
  fallback?: boolean;
  timestamp: string;
}

// ── Styling ───────────────────────────────────────────────────────────────────
const RISK_STYLE = {
  LOW:    { border: 'border-emerald-500/30', bg: 'bg-emerald-500/10', text: 'text-emerald-400', icon: ShieldCheck },
  MEDIUM: { border: 'border-amber-500/30',   bg: 'bg-amber-500/10',   text: 'text-amber-400',   icon: AlertTriangle },
  HIGH:   { border: 'border-red-500/30',     bg: 'bg-red-500/10',     text: 'text-red-400',     icon: ShieldAlert },
};

function RiskBadge({ risk }: { risk: 'LOW' | 'MEDIUM' | 'HIGH' }) {
  const s = RISK_STYLE[risk];
  const Icon = s.icon;
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-sm font-bold ${s.bg} ${s.border} ${s.text}`}>
      <Icon className="h-3.5 w-3.5" />
      {risk} RISK
    </span>
  );
}

function StatCard({ icon: Icon, label, value, sub, iconClass = 'text-primary' }: any) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
      <div className="h-8 w-8 rounded-lg bg-muted flex items-center justify-center shrink-0">
        <Icon className={`h-4 w-4 ${iconClass}`} />
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="font-semibold text-foreground text-sm">{value}</p>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </div>
    </div>
  );
}

// ── Demo origin: Jorhat, Assam tea garden ─────────────────────────────────────
const DEMO_ORIGIN = { lat: 26.5714, lng: 93.8441, name: 'Tea Garden (Jorhat, Assam)' };

// ── Main component ────────────────────────────────────────────────────────────
export default function RouteRealityEngine() {
  const [centers, setCenters] = useState<AuctionCenter[]>([]);
  const [selectedDest, setSelectedDest] = useState<string>('guwahati');
  const [customQuery, setCustomQuery] = useState('');
  const [useCustom, setUseCustom] = useState(false);
  const [result, setResult] = useState<RouteResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAlt, setShowAlt] = useState(false);
  const [showSegments, setShowSegments] = useState(false);

  // Load auction centers on mount
  useEffect(() => {
    apiClient.get('/api/route/auction-centers')
      .then((d: any) => setCenters(d.centers || []))
      .catch(() => {});
  }, []);

  const analyze = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setShowAlt(false);
    try {
      const body: any = {
        origin_lat: DEMO_ORIGIN.lat,
        origin_lng: DEMO_ORIGIN.lng,
        origin_name: DEMO_ORIGIN.name,
        destination: useCustom ? customQuery : selectedDest,
      };
      const data: RouteResult = await apiClient.post('/api/route/analyze', body);
      setResult(data);
    } catch (err: any) {
      setError(err?.message || 'Route analysis failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const seedDemo = async () => {
    try {
      await apiClient.post('/api/route/seed-demo', {});
    } catch {}
  };

  const activeResult = showAlt && result?.alternate_route ? {
    ...result,
    destination: {
      lat: (centers.find(c => c.key === result.alternate_route!.destination_key))?.lat || result.destination.lat,
      lng: (centers.find(c => c.key === result.alternate_route!.destination_key))?.lng || result.destination.lng,
      name: result.alternate_route!.destination_name,
      key: result.alternate_route!.destination_key,
    },
    route_risk: result.alternate_route!.route_risk as 'LOW' | 'MEDIUM' | 'HIGH',
    risk_score: result.alternate_route!.risk_score,
    distance_km: result.alternate_route!.distance_km,
    duration_min: result.alternate_route!.duration_min,
    spoilage_pct: result.alternate_route!.spoilage_pct,
    effective_price: result.alternate_route!.effective_price,
    segments: result.alternate_route!.segments.length > 0 ? result.alternate_route!.segments : result.segments,
    geometry: result.alternate_route!.geometry,
  } : result;

  const riskStyle = activeResult ? RISK_STYLE[activeResult.route_risk] : RISK_STYLE.LOW;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Route className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-foreground">Last-Kilometer Reality Engine</h2>
            <p className="text-xs text-muted-foreground">OSRM routing · per-segment risk · spoilage impact on price</p>
          </div>
        </div>
      </div>

      {/* Controls */}
      <Card className="p-5 bg-card border-border">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Origin (pre-filled) */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Origin</label>
            <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-muted/50 border border-border">
              <div className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
              <span className="text-sm text-foreground">{DEMO_ORIGIN.name}</span>
            </div>
          </div>

          {/* Destination */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Destination</label>
            <div className="space-y-2">
              <div className="flex gap-2">
                <button
                  onClick={() => setUseCustom(false)}
                  className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${!useCustom ? 'bg-primary text-primary-foreground border-primary' : 'bg-transparent border-border text-muted-foreground hover:border-primary/50'}`}
                >
                  Known Center
                </button>
                <button
                  onClick={() => setUseCustom(true)}
                  className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${useCustom ? 'bg-primary text-primary-foreground border-primary' : 'bg-transparent border-border text-muted-foreground hover:border-primary/50'}`}
                >
                  Custom Location
                </button>
              </div>
              {!useCustom ? (
                <select
                  value={selectedDest}
                  onChange={(e) => setSelectedDest(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg bg-muted/50 border border-border text-sm text-foreground focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30"
                >
                  {centers.map((c) => (
                    <option key={c.key} value={c.key}>{c.name}</option>
                  ))}
                  {centers.length === 0 && (
                    <>
                      <option value="guwahati">Guwahati Tea Auction Centre</option>
                      <option value="siliguri">Siliguri Tea Auction Centre</option>
                      <option value="kolkata">Kolkata Tea Auction Centre</option>
                      <option value="jorhat">Jorhat Tea Auction Centre</option>
                    </>
                  )}
                </select>
              ) : (
                <input
                  type="text"
                  value={customQuery}
                  onChange={(e) => setCustomQuery(e.target.value)}
                  placeholder="e.g. Dibrugarh, Assam"
                  className="w-full px-3 py-2.5 rounded-lg bg-muted/50 border border-border text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary/60 focus:ring-1 focus:ring-primary/30"
                />
              )}
            </div>
          </div>

          {/* Analyze button */}
          <div className="flex flex-col justify-end">
            <Button
              onClick={analyze}
              disabled={loading || (useCustom && !customQuery.trim())}
              className="h-[42px] bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold rounded-lg transition-all duration-200 hover:shadow-lg hover:shadow-blue-500/25 disabled:opacity-40"
            >
              {loading ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Routing…
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Navigation className="h-4 w-4" />
                  Analyze Route
                </div>
              )}
            </Button>
          </div>
        </div>

        {error && (
          <p className="mt-3 text-sm text-red-400 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4" />{error}
          </p>
        )}
      </Card>

      {/* Result */}
      {result && activeResult && (
        <>
          {/* Alternate toggle */}
          {result.alternate_route && (
            <div className="flex items-center gap-3 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
              <ShieldAlert className="h-4 w-4 text-amber-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-amber-300 font-medium">HIGH risk detected. Alternate route available:</p>
                <p className="text-xs text-muted-foreground">
                  {result.alternate_route.destination_name} — {result.alternate_route.route_risk} risk · ₹{result.alternate_route.effective_price}/kg effective price
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAlt(!showAlt)}
                className="shrink-0 border-amber-500/40 text-amber-400 hover:bg-amber-500/10"
              >
                <ArrowRightLeft className="h-4 w-4 mr-1" />
                {showAlt ? 'Show Original' : 'Switch to Alternate'}
              </Button>
            </div>
          )}

          {/* Map + summary grid */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            {/* Route map */}
            <Card className="xl:col-span-2 p-4 bg-card border-border">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-foreground">
                  {activeResult.origin.name} → {activeResult.destination.name}
                </span>
                <RiskBadge risk={activeResult.route_risk} />
              </div>

              <RouteMap
                origin={activeResult.origin}
                destination={activeResult.destination}
                segments={activeResult.segments}
                alternateGeometry={
                  !showAlt && result.alternate_route
                    ? result.alternate_route.geometry
                    : undefined
                }
              />

              {/* Segment risk legend */}
              <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
                <span>Segment risk:</span>
                {[['LOW', '#22c55e'], ['MEDIUM', '#f59e0b'], ['HIGH', '#ef4444']].map(([label, color]) => (
                  <div key={label} className="flex items-center gap-1">
                    <div className="w-6 h-1 rounded-full" style={{ background: color }} />
                    <span>{label}</span>
                  </div>
                ))}
                {result.alternate_route && (
                  <div className="flex items-center gap-1">
                    <div className="w-6 h-0.5 rounded-full bg-blue-500" style={{ borderBottom: '2px dashed #3b82f6' }} />
                    <span>Alternate</span>
                  </div>
                )}
              </div>
            </Card>

            {/* Summary stats */}
            <div className="space-y-3">
              {activeResult.severe_hazard_warning && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-xs">
                  <ShieldAlert className="h-4 w-4 shrink-0" />
                  <span>This route passes through a severe-risk zone: {activeResult.severe_hazard_warning}. Consider the alternate route or delay dispatch by 1 day.</span>
                </div>
              )}
              <Card className={`p-4 border ${riskStyle.border} ${riskStyle.bg}`}>
                <div className="flex items-center gap-2 mb-4">
                  <riskStyle.icon className={`h-5 w-5 ${riskStyle.text}`} />
                  <div>
                    <p className={`font-bold text-lg ${riskStyle.text}`}>Route Risk: {activeResult.route_risk}</p>
                    <p className="text-xs text-muted-foreground" title="Based on rainfall + terrain + historical delay risk">
                      Score: {(activeResult.risk_score * 100).toFixed(0)}% · Based on rainfall + terrain + delay history ℹ
                    </p>
                  </div>
                </div>

                <div className="space-y-2.5">
                  <StatCard icon={Route} label="Distance" value={`${activeResult.distance_km} km`} iconClass="text-blue-400" />
                  <StatCard icon={Clock} label="Est. Duration" value={`${Math.floor(activeResult.duration_min / 60)}h ${activeResult.duration_min % 60}m`} iconClass="text-purple-400" />
                  <StatCard
                    icon={TrendingDown}
                    label="Spoilage Risk"
                    value={`${activeResult.spoilage_pct}%`}
                    sub={activeResult.route_risk === 'HIGH' ? '↑ Consider alternate route' : activeResult.route_risk === 'LOW' ? '✓ Minimal spoilage expected' : 'Moderate risk — monitor weather'}
                    iconClass={activeResult.route_risk === 'HIGH' ? 'text-red-400' : activeResult.route_risk === 'LOW' ? 'text-emerald-400' : 'text-amber-400'}
                  />
                </div>
              </Card>

              {activeResult.route_advisories && activeResult.route_advisories.length > 0 && (
                <Card className="p-4 bg-card border-border">
                  <p className="text-xs text-muted-foreground uppercase tracking-wide font-medium mb-3">Route Advisories</p>
                  <div className="space-y-2">
                    {activeResult.route_advisories.map((advisory) => (
                      <div key={advisory.hazard_type} className="flex items-start gap-2 text-xs">
                        <AlertTriangle className={advisory.severity === 'severe' ? 'h-4 w-4 text-red-400 shrink-0' : 'h-4 w-4 text-amber-400 shrink-0'} />
                        <span className="text-muted-foreground">{advisory.description} <strong className="capitalize text-foreground">({advisory.severity} risk)</strong></span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* Price impact card */}
              <Card className="p-4 bg-card border-border">
                <p className="text-xs text-muted-foreground uppercase tracking-wide font-medium mb-3">Price Impact</p>
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Base price</span>
                    <span className="text-foreground font-medium">₹{activeResult.base_price.toFixed(2)}/kg</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Spoilage deduction</span>
                    <span className="text-red-400 font-medium">−₹{(activeResult.base_price - activeResult.effective_price).toFixed(2)}</span>
                  </div>
                  <div className="h-px bg-border" />
                  <div className="flex justify-between">
                    <span className="text-foreground font-semibold">Effective price</span>
                    <span className="text-emerald-400 font-bold text-lg">₹{activeResult.effective_price.toFixed(2)}/kg</span>
                  </div>
                </div>

                {activeResult.recommended_harvest_shift > 0 && (
                  <div className="mt-3 p-2.5 rounded-lg bg-red-500/10 border border-red-500/20">
                    <p className="text-xs text-red-400 font-medium">
                      ⚠️ Recommendation: Delay harvest by {activeResult.recommended_harvest_shift} day(s) to avoid HIGH-risk dispatch window
                    </p>
                  </div>
                )}
              </Card>

              {/* Keep the dense segment data available without overwhelming the summary. */}
              <Card className="p-4 bg-card border-border">
                <button
                  type="button"
                  onClick={() => setShowSegments(!showSegments)}
                  className="w-full flex items-center justify-between text-xs text-muted-foreground uppercase tracking-wide font-medium"
                >
                  <span>Top 3 highest-risk segments</span>
                  <span>{showSegments ? 'Hide' : 'Show'}</span>
                </button>
                {showSegments && <div className="space-y-2 mt-3">
                  {[...activeResult.segments]
                    .sort((a, b) => b.risk_score - a.risk_score)
                    .slice(0, 3)
                    .map((seg, i) => {
                    const c = seg.risk_level === 'LOW' ? 'text-emerald-400' : seg.risk_level === 'HIGH' ? 'text-red-400' : 'text-amber-400';
                    return (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">Segment {i + 1}</span>
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 rounded-full bg-muted overflow-hidden">
                            <div
                              className={seg.risk_level === 'LOW' ? 'h-full bg-emerald-500' : seg.risk_level === 'HIGH' ? 'h-full bg-red-500' : 'h-full bg-amber-500'}
                              style={{ width: `${seg.risk_score * 100}%` }}
                            />
                          </div>
                          <span className={`font-semibold w-16 text-right ${c}`}>{seg.risk_level} ({(seg.risk_score * 100).toFixed(0)}%)</span>
                        </div>
                      </div>
                    );
                    })}
                </div>}
              </Card>
            </div>
          </div>

          {/* Status badges */}
          <div className="flex flex-wrap gap-2">
            {result.cached && <span className="text-xs px-2.5 py-1 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">📦 Cached result (6h)</span>}
            {result.demo_scenario && <span className="text-xs px-2.5 py-1 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">🎭 Demo scenario</span>}
            {result.fallback && <span className="text-xs px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">⚡ Fallback (OSRM unavailable)</span>}
          </div>
        </>
      )}

      {/* Info footer */}
      <Card className="p-4 bg-muted/20 border-border/50">
        <div className="flex items-start gap-2">
          <Info className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
          <p className="text-xs text-muted-foreground leading-relaxed">
            <strong className="text-foreground">How it works:</strong> Route geometry is fetched from the public OSRM server, then sliced into ~3 km segments. Each segment gets a risk score: 50% rainfall intensity + 30% terrain slope factor + 20% historical delay rate. Route risk is classified LOW/MEDIUM/HIGH, and spoilage probability (2%/7%/15%) is deducted from the predicted auction price. When HIGH risk is detected, the nearest alternate auction center is evaluated automatically.
          </p>
        </div>
      </Card>
    </div>
  );
}
