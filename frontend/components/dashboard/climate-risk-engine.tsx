'use client';

import { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ShieldAlert, Download, Activity, CloudRain, AlertTriangle } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

export default function ClimateRiskEngine({ autoRun = false }: { autoRun?: boolean }) {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const { toast } = useToast();
  const fieldId = 'demo_field';
  const hasRunRef = useRef(false);

  const fetchEvents = async () => {
    try {
      setLoading(true);
      const res = await apiClient.get(`/api/climate-risk/events/${fieldId}`);
      if (res.events) {
        setEvents(res.events);
      }
    } catch (error) {
      console.error("Failed to fetch climate risk events:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
    if (autoRun && !hasRunRef.current) {
      hasRunRef.current = true;
      evaluateRisk();
    }
  }, [autoRun]);

  const evaluateRisk = async () => {
    setEvaluating(true);
    try {
      const res = await apiClient.post(`/api/climate-risk/evaluate/${fieldId}`);
      if (res.status === 'triggered') {
        toast({
          title: 'Risk Event Triggered!',
          description: `A ${res.event.event_type} risk event was detected and logged.`,
          variant: 'destructive'
        });
      } else {
        toast({
          title: 'Evaluation Complete',
          description: res.message || 'No risk thresholds were met.',
        });
      }
    } catch (error) {
      console.error("Failed to evaluate risk:", error);
      toast({
        title: 'Error',
        description: 'Failed to evaluate climate risk',
        variant: 'destructive',
      });
    } finally {
      await fetchEvents();
      setEvaluating(false);
    }
  };

  const downloadTriggerDoc = (eventId: string) => {
    // API endpoint that returns the PDF directly
    window.open(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/climate-risk/export/${eventId}?token=demo_token`, '_blank');
  };

  return (
    <div className="space-y-6">
      <div className="mb-4">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 text-red-500" />
          Parametric Climate Risk Engine
        </h2>
        <p className="text-slate-500 dark:text-slate-400">
          Auto-insurance triggers based on multi-modal satellite & IoT ground truth analysis.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {(() => {
          const hasDrought = events.some(e => e.event_type === 'Drought' && e.status === 'Active');
          return (
            <Card className={hasDrought ? "bg-orange-50/50 dark:bg-orange-950/20 border-orange-200" : "bg-emerald-50/50 dark:bg-emerald-950/20 border-emerald-200"}>
              <CardHeader className="pb-2">
                <CardTitle className={`text-sm flex items-center gap-2 ${hasDrought ? "text-orange-700 dark:text-orange-400" : "text-emerald-700 dark:text-emerald-400"}`}>
                  <ShieldAlert className="h-4 w-4" /> Drought Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className={`text-2xl font-bold mb-2 ${hasDrought ? "text-orange-600 dark:text-orange-500" : "text-emerald-600 dark:text-emerald-500"}`}>
                  {hasDrought ? "CRITICAL ALERT" : "SAFE / NORMAL"}
                </p>
                <div className="flex flex-col gap-0.5 text-[11px] text-slate-500">
                  <p>Thresholds monitored:</p>
                  <p>• NDWI Drop &gt; 15%</p>
                  <p>• Moisture &lt; 20% (3+ Days)</p>
                </div>
              </CardContent>
            </Card>
          );
        })()}

        {(() => {
          const hasFlood = events.some(e => e.event_type === 'Flood' && e.status === 'Active');
          return (
            <Card className={hasFlood ? "bg-blue-50/50 dark:bg-blue-950/20 border-blue-200" : "bg-emerald-50/50 dark:bg-emerald-950/20 border-emerald-200"}>
              <CardHeader className="pb-2">
                <CardTitle className={`text-sm flex items-center gap-2 ${hasFlood ? "text-blue-700 dark:text-blue-400" : "text-emerald-700 dark:text-emerald-400"}`}>
                  <CloudRain className="h-4 w-4" /> Flood Status
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className={`text-2xl font-bold mb-2 ${hasFlood ? "text-blue-600 dark:text-blue-500" : "text-emerald-600 dark:text-emerald-500"}`}>
                  {hasFlood ? "CRITICAL ALERT" : "SAFE / NORMAL"}
                </p>
                <div className="flex flex-col gap-0.5 text-[11px] text-slate-500">
                  <p>Thresholds monitored:</p>
                  <p>• NDWI Spike &gt; 15%</p>
                  <p>• Moisture &gt; 90% (3+ Days)</p>
                </div>
              </CardContent>
            </Card>
          );
        })()}

        <Card className="bg-red-50 dark:bg-red-950/30 border-red-100 dark:border-red-900">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-red-700 dark:text-red-400 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" /> Total Claim Value
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-red-600 dark:text-red-400">
              ₹{events.filter(e => e.status === 'Active').reduce((sum, e) => sum + (e.financial_loss || 0), 0).toLocaleString('en-IN')}
            </p>
            <p className="text-xs text-red-500/80 mt-1">
              Across {events.filter(e => e.status === 'Active').length} active risk event(s)
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Risk Event History</CardTitle>
          <CardDescription>Generated parametric triggers based on index data thresholds</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-slate-500">Loading events...</div>
          ) : events.length === 0 ? (
            <div className="text-center py-12 border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-lg text-slate-500">
              <ShieldAlert className="h-12 w-12 mx-auto mb-3 opacity-20" />
              <p>No climate risk events triggered.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {events.map((evt, idx) => (
                <div key={idx} className="flex flex-col md:flex-row items-center justify-between p-4 border rounded-lg hover:border-red-200 hover:bg-red-50/50 dark:hover:bg-red-900/10 transition-colors">
                  <div className="flex items-center gap-4 mb-4 md:mb-0">
                    <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-full">
                      <AlertTriangle className="h-6 w-6 text-red-600" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-slate-900 dark:text-white flex items-center gap-2">
                        {evt.event_type} Trigger Event
                        <span className="px-2 py-0.5 text-[10px] uppercase font-bold bg-red-100 text-red-700 rounded-full">
                          {evt.severity}
                        </span>
                      </h4>
                      <p className="text-sm text-slate-500">
                        Date: {new Date(evt.date_triggered).toLocaleDateString()} | Field: {evt.field_id}
                      </p>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                        Yield Loss: <strong>{evt.estimated_yield_loss_pct}%</strong> | 
                        Financial Impact: <strong className="text-red-600 dark:text-red-400 ml-1">₹{evt.financial_loss?.toLocaleString('en-IN') || 0}</strong>
                      </p>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => downloadTriggerDoc(evt.id)} className="w-full md:w-auto gap-2">
                    <Download className="h-4 w-4" /> Export Trigger Doc
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
