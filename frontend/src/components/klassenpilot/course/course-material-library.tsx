"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { ActionLink } from "@/components/klassenpilot/action-link";
import { MaterialProcessingNote } from "@/components/klassenpilot/material-processing-note";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { LearningBlock, MaterialMapping, NetworkEdge } from "@/features/course-network/types";
import { courseApi } from "@/features/course-network/material-api";
import { summarizeGraphChanges } from "@/features/course-network/change-summary";
import { CourseChangeEditor } from "./course-change-editor";
import { client } from "@/lib/api";
import { passingReview, type CourseDraft, type CourseMaterial, type GraphChanges, type ImportArtifact } from "@/features/course-network/material-types";

export function CourseMaterialLibrary({ classId }: { classId: string }) {
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [nodes, setNodes] = useState<LearningBlock[]>([]);
  const [existingMappings, setExistingMappings] = useState<MaterialMapping[]>([]);
  const [existingEdges, setExistingEdges] = useState<NetworkEdge[]>([]);
  const [imports, setImports] = useState<CourseDraft<ImportArtifact>[]>([]);
  const [draft, setDraft] = useState<CourseDraft<ImportArtifact> | null>(null);
  const [artifact, setArtifact] = useState<ImportArtifact | null>(null);
  const [change, setChange] = useState<CourseDraft<GraphChanges> | null>(null);
  const [changes, setChanges] = useState<GraphChanges | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [sectionText, setSectionText] = useState("");
  const [correction, setCorrection] = useState("");
  const [generation, setGeneration] = useState<CourseDraft<unknown> | null>(null);
  const [requestingGeneration, setRequestingGeneration] = useState(false);
  const generationRunning = requestingGeneration || !!generation?.running;
  const localProposal = useRef({ classId, change, changes });
  localProposal.current = { classId, change, changes };
  const refresh = useCallback(async () => {
    const [library, active, proposals, network] = await Promise.all([courseApi.list(classId), courseApi.imports(classId), courseApi.changes(classId), client.getCourseNetwork(classId)]);
    setNodes(network.network?.nodes.filter(n => n.status !== "retired") || []);
    setExistingMappings(network.network?.material_mappings || []);
    setExistingEdges(network.network?.edges || []);
    setMaterials(library.materials); setImports(active.drafts);
    setGeneration(proposals.generation || null);
    const local = localProposal.current;
    const unsaved = local.classId === classId && local.change && JSON.stringify(local.changes) !== JSON.stringify(local.change.artifact);
    if (!unsaved) { setChange(proposals.drafts[0] || null); setChanges(proposals.drafts[0]?.artifact || null); }
  }, [classId]);
  useEffect(() => {
    if (!generationRunning) return;
    const timer = setInterval(() => { void refresh().catch(e => setError(String(e))); }, 2500);
    return () => clearInterval(timer);
  }, [generationRunning, refresh]);
  useEffect(() => { void refresh().catch(e => setError(String(e))); }, [refresh]);
  const run = async (operation: () => Promise<void>) => {
    if (busy) return;
    setBusy(true); setError(""); setNotice("");
    try { await operation(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const generateProposal = async (operation: () => Promise<CourseDraft<GraphChanges>>) => {
    setRequestingGeneration(true);
    try {
      const row = await operation();
      const local = localProposal.current;
      const unsaved = local.classId === classId && local.change && JSON.stringify(local.changes) !== JSON.stringify(local.change.artifact);
      if (!unsaved) { setChange(row); setChanges(row.artifact); }
      setGeneration(null);
    } catch (e) {
      // The request can fail after the server reserved or completed the job.
      // Recover its durable state without replacing any local proposal edits.
      await refresh().catch(() => undefined);
      throw e;
    } finally {
      setRequestingGeneration(false);
    }
  };
  const selectDraft = (row: CourseDraft<ImportArtifact>) => { setDraft(row); setArtifact(row.artifact); };
  useEffect(() => {
    if (!draft?.running) return;
    let cancelled = false;
    const timer = setInterval(() => { void courseApi.import(classId, draft.draft_id).then(row => {
      if (!cancelled) { setDraft(row); setArtifact(row.artifact); }
    }).catch(e => { if (!cancelled) setError(String(e)); }); }, 2500);
    return () => { cancelled = true; clearInterval(timer); };
  }, [classId, draft?.draft_id, draft?.running]);
  const dirty = !!draft && JSON.stringify(artifact) !== JSON.stringify(draft.artifact);
  const changesDirty = !!change && JSON.stringify(changes) !== JSON.stringify(change.artifact);
  const mappingNodes = [...nodes, ...(changes?.operations.flatMap(op => op.op === "add_node" ? [op.node] : []) || [])];
  const removedMappings = changes?.replacement_mappings == null ? [] : existingMappings.filter(old => old.material_id === changes.material_id && !changes.replacement_mappings!.some(next => next.material_id === old.material_id && next.section_id === old.section_id && next.node_id === old.node_id && next.relation === old.relation));
  const patchSection = (index: number, patch: Partial<ImportArtifact["sections"][number]>) => {
    if (artifact) setArtifact({ ...artifact, sections: artifact.sections.map((s, i) => i === index ? { ...s, ...patch } : s) });
  };
  return <div className="space-y-4 pb-8">
    <PageHeader title="Course materials" description="Review a chapter, connect it to the class map, and reuse it in lesson planning." backHref={`/classes/${encodeURIComponent(classId)}/course`} backLabel="Course network" />
    {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
    {notice && <Alert><AlertDescription>{notice}</AlertDescription></Alert>}
    {(generationRunning || generation) && <Alert><AlertDescription>{generationRunning ? <p role="status">Generating a map proposal. You can leave and return; the saved request will stay here.</p> : generation && <><p>{generation.runtime.error || "Generation was interrupted. Retry the saved request."}</p><Button variant="outline" disabled={busy || !!change} onClick={() => void run(() => generateProposal(() => courseApi.retryGeneration(classId)))}>Retry saved map request</Button><Button variant="ghost" disabled={busy} onClick={() => void run(async () => { await courseApi.discardGeneration(classId, generation); await refresh(); })}>Discard saved request</Button></>}</AlertDescription></Alert>}
    {!!nodes.length && <Card><CardHeader><CardTitle>Suggest a map correction</CardTitle></CardHeader><CardContent className="space-y-3"><Label htmlFor="course-correction">What should change?</Label><Textarea id="course-correction" value={correction} maxLength={6000} onChange={e => setCorrection(e.target.value)} placeholder="For example: clarify that catalysis changes the reaction path, not the reaction energy." /><Button variant="outline" disabled={busy || generationRunning || !!change || !correction.trim()} onClick={() => void run(() => generateProposal(() => courseApi.correct(classId, correction)))}>Suggest correction</Button><p className="text-sm text-muted-foreground">Suggestions change nothing until you review and approve them.</p></CardContent></Card>}
    <Card><CardHeader><CardTitle>Upload a chapter</CardTitle></CardHeader><CardContent>
      <form className="space-y-3" onSubmit={event => { event.preventDefault(); const form = new FormData(event.currentTarget); void run(async () => { selectDraft(await courseApi.upload(classId, form)); await refresh(); }); }}>
        <Label htmlFor="course-file">PDF, up to 40 MB and 30 selected pages</Label><Input id="course-file" name="file" type="file" accept="application/pdf" required disabled={busy} />
        <MaterialProcessingNote />
        <Label htmlFor="course-title">Title</Label><Input id="course-title" name="title" placeholder="Chapter or worksheet title" />
        <Label htmlFor="course-pages">PDF pages (optional)</Label><Input id="course-pages" name="pages" placeholder="For example: 4-12" />
        <Button type="submit" disabled={busy}>Extract chapter</Button>
      </form>
    </CardContent></Card>
    {!!imports.length && <div className="flex flex-wrap gap-2" aria-label="Resume imports">{imports.map(row => <Button key={row.draft_id} variant="outline" onClick={() => void run(async () => selectDraft(await courseApi.import(classId, row.draft_id)))} disabled={busy}>{row.artifact.title} · {row.runtime.stage?.replaceAll("_", " ")}</Button>)}</div>}
    {draft && artifact && <Card><CardHeader><CardTitle>{artifact.title} · document review</CardTitle></CardHeader><CardContent className="space-y-4">
      {draft.status === "draft" && <Button variant="ghost" disabled={busy || draft.running} onClick={() => void run(async () => { await client.discardWorkflowDraft(classId, draft.draft_id); setDraft(null); setArtifact(null); await refresh(); })}>Discard import</Button>}
      {draft.running && <p role="status">Extracting the chapter. You can leave and resume this import later.</p>}
      {draft.runtime.stage === "failed" && <><p>{draft.runtime.error}</p><Button disabled={busy} onClick={() => void run(async () => selectDraft(await courseApi.importAction(classId, draft, "retry")))}>Retry extraction</Button></>}
      {draft.runtime.stage === "document_review" && <>
        <p className="text-sm text-muted-foreground">Correct the text and section boundaries before approving. Excluded sections will not enter the library.</p>
        {artifact.sections.map((section, index) => <fieldset className="space-y-2 rounded-lg border border-border p-3" key={section.id}>
          <legend className="px-1 text-sm">Pages {section.page_start}–{section.page_end}</legend>
          <a className="text-sm text-primary underline" href={courseApi.importSourceUrl(classId, draft.draft_id, section.page_start)} target="_blank" rel="noreferrer">Inspect source PDF pages</a>
          <div className="flex gap-2"><div><Label htmlFor={`page-start-${section.id}`}>First PDF page</Label><Input id={`page-start-${section.id}`} aria-label="First PDF page" type="number" min={1} value={section.page_start} onChange={e => patchSection(index, { page_start: Number(e.target.value) })} /></div><div><Label htmlFor={`page-end-${section.id}`}>Last PDF page</Label><Input id={`page-end-${section.id}`} aria-label="Last PDF page" type="number" min={section.page_start} value={section.page_end} onChange={e => patchSection(index, { page_end: Number(e.target.value) })} /></div></div>
          <Label htmlFor={`title-${section.id}`}>Section title</Label><Input id={`title-${section.id}`} value={section.title} onChange={e => patchSection(index, { title: e.target.value })} />
          <Label htmlFor={`body-${section.id}`}>Extracted text</Label><Textarea id={`body-${section.id}`} rows={7} value={section.content} onChange={e => patchSection(index, { content: e.target.value })} />
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => patchSection(index, { included: !section.included })}>{section.included ? "Exclude section" : "Include section"}</Button>
            <Button variant="outline" onClick={() => { const at = section.content.indexOf("\n\n"); if (at < 1) { setError("Add a blank line where the section should split."); return; } const copy = [...artifact.sections]; copy.splice(index, 1, { ...section, content: section.content.slice(0, at) }, { ...section, id: `sec_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`, title: `${section.title} (continued)`, content: section.content.slice(at).trim() }); setArtifact({ ...artifact, sections: copy }); }}>Split at first blank line</Button>
            {index < artifact.sections.length - 1 && <Button variant="outline" onClick={() => { const next = artifact.sections[index + 1]; const copy = [...artifact.sections]; copy.splice(index, 2, { ...section, page_end: next.page_end, content: `${section.content}\n\n${next.content}` }); setArtifact({ ...artifact, sections: copy }); }}>Merge with next</Button>}
          </div>
        </fieldset>)}
        {draft.review && <div><p>{draft.review.summary}</p>{draft.review.findings.map((finding, i) => <p key={i}>{finding.message}</p>)}</div>}
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={busy || !dirty} onClick={() => void run(async () => selectDraft(await courseApi.saveImport(classId, draft, artifact)))}>Save corrections</Button>
          <Button variant="outline" disabled={busy || dirty} onClick={() => void run(async () => selectDraft(await courseApi.importAction(classId, draft, "review")))}>Review extraction</Button>
          <Button disabled={busy || dirty || !passingReview(draft)} onClick={() => void run(async () => { selectDraft(await courseApi.importAction(classId, draft, "approve")); await refresh(); setNotice("Chapter approved. It is available for lesson planning; connect it to the map below."); })}>Approve chapter</Button>
        </div>
      </>}
      {draft.runtime.stage === "mapping_review" && <p>This chapter is approved and available in the library below.</p>}
    </CardContent></Card>}
    <Card><CardHeader><CardTitle>Class materials library</CardTitle></CardHeader><CardContent className="space-y-4">
      {!materials.length && <p>No saved materials yet. Upload a chapter here or save a lesson with its PDF.</p>}
      {materials.map(material => <div key={material.material_id} className="space-y-2 border-b border-border pb-3">
        <h3 className="font-medium">{material.title}</h3>
        <p className="text-sm text-muted-foreground">{material.library_status === "saved" ? "Saved with a lesson — review sections before connecting to the course map." : "Approved for course planning."}{material.archived ? " Archived: kept for past lesson sources, excluded from new automatic retrieval." : ""}</p>
        <Button variant="ghost" disabled={busy} onClick={() => void run(async () => { await courseApi.archive(classId, material.material_id, !material.archived); await refresh(); })}>{material.archived ? "Restore material" : "Archive material"}</Button>
        {material.library_status === "saved" && !material.archived && <Button variant="outline" disabled={busy} onClick={() => void run(async () => { selectDraft(await courseApi.reviewSaved(classId, material.material_id)); await refresh(); })}>Review for course map</Button>}
        <a className="text-sm text-primary underline" href={courseApi.sourceUrl(classId, material.material_id)} target="_blank" rel="noreferrer">Open source PDF</a>
        <div className="flex flex-wrap gap-2">{material.sections.map(section => <Button variant="ghost" key={section.id} onClick={() => void run(async () => { const result = await courseApi.section(classId, material.material_id, section.id); setSectionText(`${material.title} · pages ${result.page_start}–${result.page_end}\n\n${result.content}`); })}>{section.title} · p. {section.page_start}–{section.page_end}</Button>)}</div>
        {material.library_status !== "saved" && !material.archived && <Button variant="outline" disabled={busy || generationRunning || !!change} onClick={() => void run(() => generateProposal(async () => { const row = await courseApi.generate(classId, material.material_id); const current = await client.getCourseNetwork(classId); setNodes(current.network?.nodes.filter(n => n.status !== "retired") || []); setExistingMappings(current.network?.material_mappings || []); setExistingEdges(current.network?.edges || []); if (current.network?.revision !== row.artifact.base_revision) throw new Error("The course map changed. Discard this stale proposal and generate it again."); return row; }))}>Connect to course map</Button>}
      </div>)}
      {sectionText && <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-sm">{sectionText}</pre>}
    </CardContent></Card>
    {change && changes && <Card><CardHeader><CardTitle>Review map changes</CardTitle></CardHeader><CardContent className="space-y-3">
      <p aria-label="Proposed changes">{summarizeGraphChanges(changes, existingMappings, existingEdges)}</p>
      <p className="text-sm text-muted-foreground">Review each proposed concept and connection. Saving a correction requires a fresh review.</p>
      {!!removedMappings.length && <Alert variant="destructive"><AlertDescription><p>These existing connections will be removed:</p><ul>{removedMappings.map(mapping => <li key={mapping.id}>{materials.find(m => m.material_id === mapping.material_id)?.sections.find(s => s.id === mapping.section_id)?.title || mapping.section_id} → {nodes.find(n => n.id === mapping.node_id)?.title || mapping.node_id} ({mapping.relation})</li>)}</ul></AlertDescription></Alert>}
      <CourseChangeEditor changes={changes} nodes={nodes} onChange={setChanges} />
      {changes.replacement_mappings?.map((mapping, index) => <div key={mapping.id} className="space-y-2 rounded-lg border border-border p-3"><p>{materials.find(m => m.material_id === mapping.material_id)?.sections.find(s => s.id === mapping.section_id)?.title || mapping.section_id}</p>
        <Label>Connect to concept</Label><Select value={mapping.node_id} onValueChange={node_id => setChanges({ ...changes, replacement_mappings: changes.replacement_mappings!.map((m, i) => i === index ? { ...m, node_id, origin: "teacher" } : m) })}><SelectTrigger aria-label="Connect to concept"><SelectValue /></SelectTrigger><SelectContent>{mappingNodes.map(node => <SelectItem key={node.id} value={node.id}>{node.title}</SelectItem>)}</SelectContent></Select>
        <Label>How this section helps</Label><Select value={mapping.relation} onValueChange={relation => setChanges({ ...changes, replacement_mappings: changes.replacement_mappings!.map((m, i) => i === index ? { ...m, relation: relation as MaterialMapping["relation"], origin: "teacher" } : m) })}><SelectTrigger aria-label="How this section helps"><SelectValue /></SelectTrigger><SelectContent>{["explains", "practices", "assesses", "extends"].map(relation => <SelectItem key={relation} value={relation}>{relation}</SelectItem>)}</SelectContent></Select>
        <Label htmlFor={`mapping-${mapping.id}`}>Teacher note</Label><Input id={`mapping-${mapping.id}`} value={mapping.teacher_note} onChange={e => setChanges({ ...changes, replacement_mappings: changes.replacement_mappings!.map((m, i) => i === index ? { ...m, teacher_note: e.target.value, origin: "teacher" } : m) })} />
        <Button variant="ghost" onClick={() => setChanges({ ...changes, replacement_mappings: changes.replacement_mappings!.filter((_, i) => i !== index) })}>Reject mapping</Button></div>)}
      {change.review && <div><p>{change.review.summary}</p>{change.review.findings.map((finding, i) => <p key={i}>{finding.message}</p>)}</div>}
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy || !changesDirty} onClick={() => void run(async () => { const row = await courseApi.saveChanges(classId, change, changes); setChange(row); setChanges(row.artifact); })}>Save map corrections</Button>
        <Button variant="outline" disabled={busy || changesDirty} onClick={() => void run(async () => setChange(await courseApi.reviewChanges(classId, change)))}>Review map proposal</Button>
        <Button disabled={busy || changesDirty || !passingReview(change)} onClick={() => void run(async () => { const published = await courseApi.commitChanges(classId, change); setNodes(published.nodes.filter(n => n.status !== "retired")); setExistingMappings(published.material_mappings); setExistingEdges(published.edges); setChange(null); setChanges(null); setNotice("Course map updated. Your next lesson plan can use these connections."); })}>Approve map changes</Button>
        <ActionLink href={`/classes/${encodeURIComponent(classId)}/course`} variant="outline">View course map</ActionLink>
        <Button variant="ghost" disabled={busy} onClick={() => void run(async () => { await client.discardWorkflowDraft(classId, change.draft_id); setChange(null); setChanges(null); })}>Discard proposal</Button>
      </div>
    </CardContent></Card>}
  </div>;
}
