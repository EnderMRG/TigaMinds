"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import {
  Beaker, ThermometerSun, Leaf, Clock, Factory, FileText,
  CheckCircle2, RefreshCw, ArrowDown, Sprout, TrendingUp,
  Calculator
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis
} from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { LeafPotentialCard, type LeafPotentialResponse, type ZoneScore } from "./leaf-potential-card";

// ─── Types ────────────────────────────────────────────────────────────────────

type CupPrediction = {
  base_potential: number;
  tf_tr_ratio: number;
  predicted_grade: string;
  tasting_note: string;
};

// ─── Colour helpers ───────────────────────────────────────────────────────────
const gradeColor = (g: string) => {
  if (g === "A" || g === "Premium") return "text-amber-500";
  if (g === "B" || g === "Standard") return "text-blue-500";
  return "text-slate-400";
};

const gradeBg = (g: string) => {
  if (g === "A" || g === "Premium") return "bg-amber-500/10 border-amber-500/30 text-amber-600";
  if (g === "B" || g === "Standard") return "bg-blue-500/10 border-blue-500/30 text-blue-600";
  return "bg-slate-500/10 border-slate-500/30 text-slate-500";
};

// ─── Main component ───────────────────────────────────────────────────────────
export default function BatchTraceability() {
  const { toast } = useToast();

  // ── Stage 1 state ──
  const [leafData, setLeafData] = useState<LeafPotentialResponse | null>(null);
  const handleLogGrade = () => {
    toast({
      title: "Outcome Logged ✓",
      description: `Predicted ${cupPrediction?.predicted_grade ?? "—"} confirmed. Accuracy model updated.`,
    });
  };

  return (
    <div className="h-[calc(100vh-120px)] flex flex-col gap-3 animate-in fade-in duration-500 overflow-hidden">

      {/* ── Header ── */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Farm-to-Cup Quality Pipeline</h2>
          <p className="text-xs text-muted-foreground">
            Stage 1: Pre-Harvest Leaf Potential  ·  Stage 2: Factory Cup Prediction
          </p>
        </div>
        <Button size="sm" variant="outline" className="gap-2" onClick={handleLogGrade}>
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
          Log Actual Grade
        </Button>
      </div>

      {/* ── Two-column main layout ── */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-3 min-h-0">

        {/* ══════════════════════════════════════════════════
            STAGE 1 — Pre-Harvest Leaf Potential
            ══════════════════════════════════════════════════ */}
        <div className="flex flex-col gap-3 min-h-0 overflow-y-auto pr-1 scrollbar-thin">
          <LeafPotentialCard onDataLoaded={(data) => setLeafData(data)} />
        </div>

        {/* ══════════════════════════════════════════════════
            STAGE 2 — Factory Cup Predictor
            ══════════════════════════════════════════════════ */}
        <div className="flex flex-col gap-3 min-h-0 overflow-y-auto pr-1 scrollbar-thin">

          {/* Connector */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground flex-shrink-0">
            <ArrowDown className="h-3.5 w-3.5 text-primary flex-shrink-0" />
            <span className="font-medium text-foreground">Leaf enters factory</span>
            <span>— configure processing conditions below to predict the final cup</span>
          </div>

          {/* Factory controls */}
          <Card className="p-4 border-t-4 border-t-orange-500 flex-shrink-0">
            <h3 className="font-bold text-sm flex items-center gap-1.5 mb-1">
              <Factory className="h-4 w-4 text-orange-500" />
              Stage 2 — Factory Processing Monitor
            </h3>
            <p className="text-xs text-muted-foreground mb-4">
              Adjust withering &amp; fermentation to see how the factory transforms the leaf.
            </p>

            <div className="grid grid-cols-2 gap-4">
              {[
                { label: "Wither Time", value: witheringHours[0], unit: "h", set: setWitheringHours, min: 10, max: 30, step: 1, state: witheringHours },
                { label: "Wither Temp", value: witheringTemp[0], unit: "°C", set: setWitheringTemp, min: 15, max: 35, step: 1, state: witheringTemp },
                { label: "Ferm. Time", value: fermentationHours[0], unit: "h", set: setFermentationHours, min: 0.5, max: 5, step: 0.1, state: fermentationHours },
                { label: "Ferm. Temp", value: fermentationTemp[0], unit: "°C", set: setFermentationTemp, min: 20, max: 35, step: 1, state: fermentationTemp },
              ].map(({ label, value, unit, set, min, max, step, state }) => (
                <div key={label} className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label className="text-xs font-medium flex items-center gap-1">
                      {unit === "h" ? <Clock className="h-3 w-3 text-orange-500" /> : <ThermometerSun className="h-3 w-3 text-orange-500" />}
                      {label}
                    </label>
                    <span className="text-xs font-bold text-orange-600">{value}{unit}</span>
                  </div>
                  <Slider value={state} onValueChange={set} min={min} max={max} step={step}
                    className="[&_[role=slider]]:bg-orange-500" />
                </div>
              ))}
            </div>
          </Card>

          {/* Cup Prediction Output */}
          {cupPrediction && (
            <Card className={`p-4 flex-1 flex flex-col justify-center border-2 relative overflow-hidden ${
              cupPrediction.predicted_grade === "Premium" ? "border-amber-500/30 bg-amber-50/30 dark:bg-amber-950/10" :
              cupPrediction.predicted_grade === "Standard" ? "border-blue-500/30 bg-blue-50/30 dark:bg-blue-950/10" :
              "border-slate-500/30"
            }`}>
              <div className="absolute top-3 left-3 flex items-center gap-1.5 text-[10px] text-muted-foreground uppercase tracking-widest">
                <Beaker className="h-3 w-3" /> Predicted Cup Profile
              </div>

              <div className="text-center mt-4 mb-3">
                <p className="text-[10px] text-muted-foreground uppercase tracking-widest mb-1">Final Cup Grade</p>
                <div className={`text-4xl font-black ${gradeColor(cupPrediction.predicted_grade)}`}>
                  {cupPrediction.predicted_grade}
                </div>
              </div>

              {/* TF:TR gauge */}
              <div className="bg-background/70 rounded-lg border p-3 mb-3">
                <div className="flex justify-between items-end mb-1">
                  <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">TF:TR Ratio (Briskness)</span>
                  <span className="text-base font-bold">{cupPrediction.tf_tr_ratio.toFixed(3)}</span>
                </div>
                <Progress
                  value={(cupPrediction.tf_tr_ratio / 0.15) * 100}
                  className={`h-2 ${cupPrediction.tf_tr_ratio > 0.09 ? "[&>div]:bg-amber-500" : cupPrediction.tf_tr_ratio > 0.06 ? "[&>div]:bg-blue-500" : "[&>div]:bg-slate-500"}`}
                />
                <div className="flex justify-between text-[9px] text-muted-foreground mt-0.5">
                  <span>Dull/Flat</span>
                  <span>Premium Brisk</span>
                </div>
              </div>

              {/* Tasting note */}
              <div className="flex items-start gap-2 bg-secondary/40 rounded-lg p-2.5 border">
                <FileText className="h-3.5 w-3.5 text-primary mt-0.5 flex-shrink-0" />
                <p className="text-xs text-muted-foreground italic leading-relaxed">
                  "{cupPrediction.tasting_note}"
                </p>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
