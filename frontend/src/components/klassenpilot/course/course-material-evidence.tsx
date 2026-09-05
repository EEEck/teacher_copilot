"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { courseApi } from "@/features/course-network/material-api";

export function CourseMaterialEvidence({ classId, materialId, sectionId, label }: { classId: string; materialId: string; sectionId: string; label?: string }) {
  const [evidence, setEvidence] = useState<Awaited<ReturnType<typeof courseApi.section>> | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  return <div className="space-y-2">
    <Button variant="link" className="h-auto max-w-full whitespace-normal px-0 text-left" disabled={loading} onClick={async () => {
      if (evidence) { setEvidence(null); return; }
      setLoading(true); setError("");
      try { setEvidence(await courseApi.section(classId, materialId, sectionId)); }
      catch (e) { setError(e instanceof Error ? e.message : String(e)); }
      finally { setLoading(false); }
    }}>{loading ? "Loading section…" : label || `${materialId} · ${sectionId}`}</Button>
    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    {evidence && <div className="space-y-2 rounded-lg bg-muted p-3 text-sm">
      <p className="font-medium">{evidence.material_title} · pages {evidence.page_start}–{evidence.page_end}</p>
      <pre className="max-h-80 overflow-auto whitespace-pre-wrap font-sans">{evidence.content}</pre>
      <a href={courseApi.sourceUrl(classId, materialId, evidence.page_start)} target="_blank" rel="noreferrer" className="text-primary underline">Open source PDF</a>
    </div>}
  </div>;
}
