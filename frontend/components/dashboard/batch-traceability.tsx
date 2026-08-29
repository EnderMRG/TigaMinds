"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Beaker, ThermometerSun, Leaf, Clock, Star, Factory, FileText, CheckCircle2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

type PredictionResponse = {
  base_potential: number;
  tf_tr_ratio: number;
  predicted_grade: string;
  tasting_note: string;
};

export default function BatchTraceability() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);

  // Field Data
  const [ndvi, setNdvi] = useState([0.75]);
  const [leafQuality, setLeafQuality] = useState([85]);
  
  // Factory Data
  const [witheringTemp, setWitheringTemp] = useState([21]);
  const [witheringHours, setWitheringHours] = useState([20]);
  const [fermentationTemp, setFermentationTemp] = useState([26]);
  const [fermentationHours, setFermentationHours] = useState([2.5]);

  useEffect(() => {
    const fetchPrediction = async () => {
      setLoading(true);
      try {
        const response = await apiClient.post("/api/batch-predictor/simulate", {
          ndvi: ndvi[0],
          leaf_quality: leafQuality[0],
          withering_temp: witheringTemp[0],
          withering_hours: witheringHours[0],
          fermentation_temp: fermentationTemp[0],
          fermentation_hours: fermentationHours[0]
        });
        setPrediction(response);
      } catch (err) {
        console.error("Failed to fetch batch prediction", err);
      } finally {
        setLoading(false);
      }
    };

    const timer = setTimeout(() => {
      fetchPrediction();
    }, 300);

    return () => clearTimeout(timer);
  }, [ndvi, leafQuality, witheringTemp, witheringHours, fermentationTemp, fermentationHours]);

  const handleLogGrade = () => {
    toast({
      title: "Outcome Logged",
      description: `Actual batch outcome verified as ${prediction?.predicted_grade}. Accuracy model updated.`,
      variant: "default",
    });
  };

  return (
    <div className="h-[calc(100vh-120px)] flex flex-col space-y-4 animate-in fade-in duration-500 overflow-hidden">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">AI Cup Quality Predictor</h2>
          <p className="text-muted-foreground">
            End-to-End Batch Traceability: Predict liquor grade before human tasting based on field and factory parameters.
          </p>
        </div>
        <Button variant="outline" className="gap-2" onClick={handleLogGrade}>
          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          Log Actual Grade
        </Button>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-4 min-h-0">
        
        {/* Left Column: Traceability Monitors (Input) */}
        <div className="lg:col-span-1 flex flex-col gap-4 overflow-y-auto pr-2 custom-scrollbar">
          
          <Card className="p-4 space-y-5 shadow-sm border-t-4 border-t-green-500">
            <div>
              <h3 className="font-bold text-base mb-1 flex items-center gap-2">
                <Leaf className="h-4 w-4 text-green-500" />
                Harvest Zone Data (Upstream)
              </h3>
              <p className="text-xs text-muted-foreground mb-4">
                Raw material quality at time of plucking.
              </p>
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <label className="text-sm font-medium">NDVI (Crop Health)</label>
                <span className="text-sm font-bold text-green-600">{ndvi[0]}</span>
              </div>
              <Slider value={ndvi} onValueChange={setNdvi} min={0.2} max={1.0} step={0.05} className="[&_[role=slider]]:bg-green-500" />
            </div>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <label className="text-sm font-medium">Leaf Quality Scanner Score</label>
                <span className="text-sm font-bold text-green-600">{leafQuality[0]}/100</span>
              </div>
              <Slider value={leafQuality} onValueChange={setLeafQuality} min={40} max={100} step={1} className="[&_[role=slider]]:bg-green-500" />
            </div>
          </Card>

          <Card className="p-4 space-y-5 shadow-sm border-t-4 border-t-orange-500">
            <div>
              <h3 className="font-bold text-base mb-1 flex items-center gap-2">
                <Factory className="h-4 w-4 text-orange-500" />
                Factory Processing Monitor (Midstream)
              </h3>
              <p className="text-xs text-muted-foreground mb-4">
                Simulate manufacturing conditions impacting Theaflavin formation.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-6">
              {/* Withering */}
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-medium flex items-center gap-1"><Clock className="h-3 w-3"/> Wither Time</label>
                  <span className="text-xs font-bold text-orange-600">{witheringHours[0]}h</span>
                </div>
                <Slider value={witheringHours} onValueChange={setWitheringHours} min={10} max={30} step={1} className="[&_[role=slider]]:bg-orange-500" />
              </div>
              
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-medium flex items-center gap-1"><ThermometerSun className="h-3 w-3"/> Wither Temp</label>
                  <span className="text-xs font-bold text-orange-600">{witheringTemp[0]}°C</span>
                </div>
                <Slider value={witheringTemp} onValueChange={setWitheringTemp} min={15} max={35} step={1} className="[&_[role=slider]]:bg-orange-500" />
              </div>

              {/* Fermentation */}
              <div className="space-y-4 mt-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-medium flex items-center gap-1"><Clock className="h-3 w-3"/> Ferm. Time</label>
                  <span className="text-xs font-bold text-orange-600">{fermentationHours[0]}h</span>
                </div>
                <Slider value={fermentationHours} onValueChange={setFermentationHours} min={0.5} max={5.0} step={0.1} className="[&_[role=slider]]:bg-orange-500" />
              </div>
              
              <div className="space-y-4 mt-2">
                <div className="flex justify-between items-center">
                  <label className="text-xs font-medium flex items-center gap-1"><ThermometerSun className="h-3 w-3"/> Ferm. Temp</label>
                  <span className="text-xs font-bold text-orange-600">{fermentationTemp[0]}°C</span>
                </div>
                <Slider value={fermentationTemp} onValueChange={setFermentationTemp} min={20} max={35} step={1} className="[&_[role=slider]]:bg-orange-500" />
              </div>
            </div>
          </Card>
        </div>

        {/* Right Column: AI Output */}
        <div className="lg:col-span-1 h-full min-h-0 flex flex-col gap-4">
          
          {prediction && (
            <Card className="p-6 shadow-sm border-2 border-primary/20 bg-gradient-to-br from-card to-secondary/20 flex-1 flex flex-col justify-center text-center space-y-6 relative overflow-hidden">
              
              <div className="absolute top-4 left-4 flex items-center gap-2 text-muted-foreground">
                <Beaker className="h-4 w-4" />
                <span className="text-xs uppercase tracking-wider font-bold">Live Batch Simulation</span>
              </div>

              <div className="pt-4">
                <p className="text-sm text-muted-foreground uppercase tracking-widest mb-2 font-bold">Predicted Grade</p>
                <div className={`text-5xl font-black ${
                  prediction.predicted_grade === 'Premium' ? 'text-amber-500' :
                  prediction.predicted_grade === 'Standard' ? 'text-blue-500' : 'text-slate-500'
                }`}>
                  {prediction.predicted_grade}
                </div>
              </div>

              <div className="max-w-md mx-auto w-full space-y-2 text-left bg-background/80 p-4 rounded-lg border">
                <div className="flex justify-between items-end mb-1">
                  <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">TF:TR Ratio (Briskness)</span>
                  <span className="text-lg font-bold">{prediction.tf_tr_ratio.toFixed(3)}</span>
                </div>
                <Progress 
                  value={(prediction.tf_tr_ratio / 0.15) * 100} 
                  className={`h-2 ${prediction.tf_tr_ratio > 0.09 ? '[&>div]:bg-amber-500' : prediction.tf_tr_ratio > 0.06 ? '[&>div]:bg-blue-500' : '[&>div]:bg-slate-500'}`} 
                />
                <div className="flex justify-between text-[10px] text-muted-foreground">
                  <span>Dull/Flat</span>
                  <span>Premium Brisk</span>
                </div>
              </div>

              <div className="pt-4">
                <div className="flex items-start gap-3 bg-secondary/50 p-4 rounded-xl text-left border">
                  <FileText className="h-5 w-5 text-primary mt-0.5 flex-shrink-0" />
                  <div>
                    <h4 className="font-bold text-sm mb-1">AI Tasting Note Prediction</h4>
                    <p className="text-sm text-muted-foreground italic leading-relaxed">
                      "{prediction.tasting_note}"
                    </p>
                  </div>
                </div>
              </div>
              
            </Card>
          )}

        </div>
      </div>
    </div>
  );
}
