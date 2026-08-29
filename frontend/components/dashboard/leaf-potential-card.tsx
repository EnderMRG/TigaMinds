"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  FileText,
  RefreshCw, Sprout, TrendingUp,
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
} from "@/components/ui/chart";

// ─── Types ────────────────────────────────────────────────────────────────────

export type ZoneScore = {
  briskness: number;
  body: number;
  aroma: number;
  colour: number;
  composite: number;
  leaf_grade: "A" | "B" | "C";
  dominant_driver: string;
  dry_days: number;
  temp_swing: number;
  ndvi: number;
  ndwi: number;
  soil_moisture: number;
  humidity_avg: number;
  tasting_note: string;
  calculation_logs: string[];
};

export type LeafPotentialResponse = {
  farm_score: ZoneScore;
  overall_grade: string;
  overall_label: string;
  data_inputs: {
    base_ndvi: number;
    base_evi: number;
    base_ndwi: number;
    base_temp: number;
    base_humidity: number;
    base_soil_moisture: number;
    mock_sources: string[];
    real_sources: string[];
  };
};

const gradeBg = (g: string) => {
  if (g === "A" || g === "Premium") return "bg-amber-500/10 border-amber-500/30 text-amber-600 dark:text-amber-400";
  if (g === "B" || g === "Standard") return "bg-blue-500/10 border-blue-500/30 text-blue-600 dark:text-blue-400";
  return "bg-slate-500/10 border-slate-500/30 text-slate-500 dark:text-slate-400";
};

export function LeafPotentialCard({ onDataLoaded }: { onDataLoaded?: (data: LeafPotentialResponse) => void }) {
  const { toast } = useToast();
  const [leafData, setLeafData] = useState<LeafPotentialResponse | null>(null);
  const [leafLoading, setLeafLoading] = useState(false);
  const [stage1Done, setStage1Done] = useState(false);

  const fetchLeafPotential = useCallback(async () => {
    setLeafLoading(true);
    try {
      const res = await apiClient.get("/api/leaf-potential/analyze");
      setLeafData(res);
      setStage1Done(true);
      if (onDataLoaded) onDataLoaded(res);
    } catch (err) {
      console.error("Leaf potential fetch failed", err);
      toast({ title: "Error", description: "Failed to analyse leaf potential.", variant: "destructive" });
    } finally {
      setLeafLoading(false);
    }
  }, [toast, onDataLoaded]);

  // Build radar data for recharts
  const chartData = leafData
    ? [
        { dimension: "Briskness", score: leafData.farm_score.briskness },
        { dimension: "Body", score: leafData.farm_score.body },
        { dimension: "Aroma", score: leafData.farm_score.aroma },
        { dimension: "Colour Depth", score: leafData.farm_score.colour },
      ]
    : [];

  const chartConfig = {
    score: {
      label: "Score",
      color: "var(--primary)",
    },
  } satisfies ChartConfig;

  return (
    <Card className="p-6 border-border bg-card rounded-xl shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-foreground flex items-center gap-1.5 text-lg">
            Pre-Harvest Leaf Potential
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            IoT sensors + satellite data → whole farm quality radar
          </p>
        </div>
        <Button size="sm" onClick={fetchLeafPotential} disabled={leafLoading} className="gap-1.5">
          {leafLoading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          {leafLoading ? "Analysing…" : stage1Done ? "Re-Analyse" : "Run Analysis"}
        </Button>
      </div>

      {!leafData && !leafLoading && (
        <div className="h-32 flex items-center justify-center border border-dashed rounded-lg text-sm text-muted-foreground bg-muted/20">
          Click "Run Analysis" to generate pre-harvest leaf potential scores.
        </div>
      )}

      {leafLoading && (
        <div className="h-32 flex items-center justify-center gap-2 text-sm text-muted-foreground bg-muted/20 rounded-lg">
          <RefreshCw className="h-4 w-4 animate-spin text-primary" />
          Pulling sensor history, satellite indices, generating scores…
        </div>
      )}

      {leafData && !leafLoading && (
        <div className="space-y-6">
          {/* Overall Grade Badge */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-3">
            <div className={`px-4 py-1.5 rounded-full border text-sm font-bold w-fit ${gradeBg(leafData.overall_label)}`}>
              Leaf Grade {leafData.overall_label} — {leafData.overall_grade}
            </div>
            <span className="text-sm text-muted-foreground">
              Farm composite: <span className="font-bold text-foreground">{leafData.farm_score.composite}/100</span>
            </span>
            <div className="sm:ml-auto flex gap-1.5 flex-wrap">
              {leafData.data_inputs.real_sources.map(s => (
                <span key={s} className="text-[11px] bg-primary/10 text-primary px-2 py-0.5 rounded-md font-medium border border-primary/20">✓ {s}</span>
              ))}
              {leafData.data_inputs.mock_sources.slice(0, 2).map(s => (
                <span key={s} className="text-[11px] bg-muted text-muted-foreground px-2 py-0.5 rounded-md font-medium border">~ {s}</span>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Radar Chart */}
            <Card className="border shadow-sm">
              <CardHeader className="items-center pb-2">
                <CardTitle className="text-base">Leaf Potential Radar</CardTitle>
                <CardDescription>
                  Breakdown of the farm's 4 core quality dimensions
                </CardDescription>
              </CardHeader>
              <CardContent className="pb-0">
                <ChartContainer
                  config={chartConfig}
                  className="mx-auto w-full h-[250px]"
                >
                  <RadarChart data={chartData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                    <ChartTooltip cursor={false} content={<ChartTooltipContent />} />
                    <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 12, fill: "var(--foreground)" }} />
                    <PolarGrid stroke="var(--border)" />
                    <Radar
                      dataKey="score"
                      fill="var(--color-score)"
                      fillOpacity={0.6}
                      dot={{
                        r: 4,
                        fillOpacity: 1,
                      }}
                    />
                  </RadarChart>
                </ChartContainer>
              </CardContent>
              <CardFooter className="flex-col gap-1 text-sm pt-4">
                <div className="flex items-center gap-2 leading-none font-medium">
                  Dominant Driver: {leafData.farm_score.dominant_driver} <TrendingUp className="h-4 w-4 text-primary" />
                </div>
                <div className="flex items-center gap-2 leading-none text-muted-foreground text-xs text-center mt-1">
                  Based on past 7 days of field data
                </div>
              </CardFooter>
            </Card>

            <div className="flex flex-col gap-4">
              {/* Tasting Note */}
              <div className="p-4 bg-primary/5 rounded-xl border border-primary/10">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg shrink-0">
                    <FileText className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold mb-1 text-foreground">Field-level AI Tasting Note</p>
                    <p className="text-sm text-muted-foreground italic leading-relaxed">
                      "{leafData.farm_score.tasting_note}"
                    </p>
                    <div className="flex flex-wrap gap-x-4 gap-y-2 mt-3 text-xs font-medium text-muted-foreground">
                      <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-primary/50"></span>NDVI {leafData.farm_score.ndvi}</span>
                      <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-primary/50"></span>Dry days: {leafData.farm_score.dry_days}</span>
                      <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-primary/50"></span>Diurnal: {leafData.farm_score.temp_swing}°C</span>
                      <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-primary/50"></span>SM: {leafData.farm_score.soil_moisture}%</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Score Calculation Logs */}
              <div className="flex-1 flex flex-col">
                <h4 className="text-xs font-semibold flex items-center gap-1.5 mb-2 text-muted-foreground">
                  <Calculator className="h-3.5 w-3.5" /> Score Calculation Logs
                </h4>
                <div className="flex-1 bg-muted/30 rounded-lg p-3 text-[11px] font-mono leading-relaxed border space-y-1.5 overflow-x-auto text-muted-foreground overflow-y-auto scrollbar-thin min-h-[160px]">
                  {leafData.farm_score.calculation_logs.map((log, i) => (
                    <div key={i} className="flex gap-2">
                      <span className="text-primary/60">→</span>
                      <span>{log}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
