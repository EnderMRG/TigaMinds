'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api';
import { ExternalLink, FileText, Search, Send } from 'lucide-react';

interface Scheme {
  id: number;
  name: string;
  provider: string;
  category: string;
  subsidy_details: string;
  eligibility_criteria: string;
  application_window: string;
  source_url: string;
  match_reason: string;
  region_specificity: 'National' | 'Assam-specific';
}

export default function SubsidyInsuranceNavigator() {
  const [estateSize, setEstateSize] = useState('2');
  const [growerType, setGrowerType] = useState('individual');
  const [activity, setActivity] = useState('replanting');
  const [region, setRegion] = useState('All');
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);

  const findSchemes = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ estate_size_ha: estateSize, grower_type: growerType, activity, region });
      const data = await apiClient.get(`/api/subsidies/match?${params.toString()}`);
      setSchemes(data.schemes || []);
    } finally {
      setLoading(false);
    }
  };

  const askAdvisor = async () => {
    if (!question.trim()) return;
    const data = await apiClient.post('/api/subsidies/advisor', {
      question,
      matched_scheme_ids: schemes.map((scheme) => scheme.id),
    });
    setAnswer(data.answer);
  };

  const downloadDossier = async () => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const response = await fetch(`${baseUrl}/api/subsidies/insurance-dossier/demo_field_jorhat`, { headers: { Authorization: 'Bearer demo_token', 'X-Force-Demo': 'true' } });
    if (!response.ok) throw new Error('Dossier generation failed');
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = 'chainet-insurance-evidence-dossier.pdf';
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-foreground">Subsidy & Insurance Navigator</h2>
        <p className="mt-1 text-sm text-muted-foreground">Official scheme records for tea growers. Assam Budget 2026–27 items are recently announced; confirm disbursement status with the relevant department.</p>
      </div>

      <Card className="p-5">
        <div className="grid gap-4 md:grid-cols-5">
          <label className="text-sm text-muted-foreground">Estate size (ha)<Input className="mt-1" type="number" min="0" value={estateSize} onChange={(event) => setEstateSize(event.target.value)} /></label>
          <label className="text-sm text-muted-foreground">Grower type<select className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm text-foreground" value={growerType} onChange={(event) => setGrowerType(event.target.value)}><option value="individual">Individual</option><option value="shg">SHG</option><option value="registered garden">Registered garden</option></select></label>
          <label className="text-sm text-muted-foreground">Intended activity<select className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm text-foreground" value={activity} onChange={(event) => setActivity(event.target.value)}><option value="all">All activities</option><option value="replanting">Replanting</option><option value="irrigation">Irrigation</option><option value="machinery">Machinery</option><option value="certification">Certification</option><option value="export">Export</option></select></label>
          <label className="text-sm text-muted-foreground">Show<select className="mt-1 h-10 w-full rounded-md border bg-background px-3 text-sm text-foreground" value={region} onChange={(event) => setRegion(event.target.value)}><option value="All">All</option><option value="National">National</option><option value="Assam-specific">Assam-specific</option></select></label>
          <Button className="mt-auto gap-2" onClick={findSchemes} disabled={loading}><Search className="h-4 w-4" />Find schemes</Button>
        </div>
      </Card>

      {schemes.length > 0 && <div className="grid gap-4 lg:grid-cols-2">{schemes.map((scheme) => <Card key={scheme.id} className="p-5"><div className="flex items-start justify-between gap-3"><div><div className="flex items-center gap-2"><p className="text-xs uppercase tracking-wide text-emerald-600">{scheme.provider}</p><span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">{scheme.region_specificity}</span></div><h3 className="mt-1 font-semibold text-foreground">{scheme.name}</h3></div><a className="text-muted-foreground hover:text-foreground" href={scheme.source_url} target="_blank" rel="noreferrer" title="Open official source"><ExternalLink className="h-4 w-4" /></a></div><p className="mt-3 text-sm text-foreground">{scheme.subsidy_details}</p><p className="mt-2 text-xs text-muted-foreground">Eligibility: {scheme.eligibility_criteria}</p><p className="mt-2 text-xs text-muted-foreground">Window: {scheme.application_window}</p></Card>)}</div>}

      <Card className="p-5"><div className="flex items-center gap-2"><FileText className="h-4 w-4 text-emerald-600" /><h3 className="font-semibold text-foreground">Subsidy Advisor</h3></div><div className="mt-3 flex gap-2"><Input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Do I qualify for the replanting scheme?" onKeyDown={(event) => event.key === 'Enter' && askAdvisor()} /><Button onClick={askAdvisor} disabled={!question.trim()} aria-label="Ask subsidy advisor"><Send className="h-4 w-4" /></Button></div>{answer && <p className="mt-4 rounded-md bg-muted p-3 text-sm text-foreground">{answer}</p>}</Card>

      <Card className="flex items-center justify-between gap-4 p-5"><div><h3 className="font-semibold text-foreground">Insurance Evidence Dossier</h3><p className="mt-1 text-xs text-muted-foreground">Compile the last 90 days of satellite and sensor evidence for a private insurer or claims assessor.</p></div><Button variant="outline" onClick={downloadDossier} className="shrink-0 gap-2"><FileText className="h-4 w-4" />Download PDF</Button></Card>

      <p className="text-xs text-muted-foreground">The navigator does not provide legal or financial advice. Scheme details are limited to the cited official records and may change.</p>
    </div>
  );
}
