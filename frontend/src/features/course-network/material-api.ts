import { api, apiForm, getApiBase } from "@/lib/api";
import type { CourseNetwork } from "./types";
import type { CourseDraft, CourseMaterial, GraphChanges, ImportArtifact } from "./material-types";
import { snapshot } from "./material-types";

const base = (id: string) => `/api/classes/${encodeURIComponent(id)}/course`;
const json = (body: unknown, method = "POST") => ({ method, body: JSON.stringify(body) });
export const courseApi = {
  sourceUrl: (id: string, materialId: string, page = 1) => `${getApiBase()}${base(id)}/materials/${encodeURIComponent(materialId)}/files/source.pdf#page=${page}`,
  list: (id: string) => api<{ materials: CourseMaterial[] }>(`${base(id)}/materials`),
  imports: (id: string) => api<{ drafts: CourseDraft<ImportArtifact>[] }>(`${base(id)}/material-imports`),
  upload: (id: string, form: FormData) => apiForm<CourseDraft<ImportArtifact>>(`${base(id)}/material-imports`, form),
  import: (id: string, draft: string) => api<CourseDraft<ImportArtifact>>(`${base(id)}/material-imports/${draft}`),
  importAction: (id: string, draft: CourseDraft<ImportArtifact>, action: "review" | "approve" | "retry") => api<CourseDraft<ImportArtifact>>(`${base(id)}/material-imports/${draft.draft_id}/${action}`, json(snapshot(draft))),
  saveImport: (id: string, draft: CourseDraft<ImportArtifact>, artifact: ImportArtifact) => api<CourseDraft<ImportArtifact>>(`${base(id)}/material-imports/${draft.draft_id}`, json({ ...snapshot(draft), artifact }, "PUT")),
  generate: (id: string, materialId: string, teacherRequest = "") => api<CourseDraft<GraphChanges>>(`${base(id)}/changes/generate`, json({ purpose: "material_enrichment", material_id: materialId, teacher_request: teacherRequest })),
  changes: (id: string) => api<{ drafts: CourseDraft<GraphChanges>[] }>(`${base(id)}/changes`),
  saveChanges: (id: string, draft: CourseDraft<GraphChanges>, changes: GraphChanges) => api<CourseDraft<GraphChanges>>(`${base(id)}/changes/${draft.draft_id}`, json({ ...snapshot(draft), changes }, "PUT")),
  reviewChanges: (id: string, draft: CourseDraft<GraphChanges>) => api<CourseDraft<GraphChanges>>(`${base(id)}/changes/${draft.draft_id}/review`, json({})),
  commitChanges: (id: string, draft: CourseDraft<GraphChanges>) => api<CourseNetwork>(`${base(id)}/changes/${draft.draft_id}/commit`, json(snapshot(draft))),
  section: (id: string, material: string, section: string) => api<{ content: string; material_title: string; page_start: number; page_end: number }>(`${base(id)}/materials/${encodeURIComponent(material)}/sections/${encodeURIComponent(section)}`),
};
