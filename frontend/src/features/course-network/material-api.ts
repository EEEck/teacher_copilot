import { api, apiForm, getApiBase } from "@/lib/api";
import type { CourseNetwork } from "./types";
import type { CourseDraft, CourseMaterial, GraphChanges, ImportArtifact } from "./material-types";
import { snapshot } from "./material-types";

const base = (id: string) => `/api/classes/${encodeURIComponent(id)}/course`;
const json = (body: unknown, method = "POST") => ({ method, body: JSON.stringify(body) });
export const courseApi = {
  correct: (id: string, teacherRequest: string) => api<CourseDraft<GraphChanges>>(`${base(id)}/changes/generate`, json({ purpose: "correction", teacher_request: teacherRequest })),
  importSourceUrl: (id: string, draft: string, page = 1) => `${getApiBase()}${base(id)}/material-imports/${encodeURIComponent(draft)}/source?original_page=${page}`,
  reviewSaved: (id: string, materialId: string) => api<CourseDraft<ImportArtifact>>(`${base(id)}/materials/${encodeURIComponent(materialId)}/review-import`, json({})),
  archive: (id: string, materialId: string, archived: boolean) => api(`${base(id)}/materials/${encodeURIComponent(materialId)}/archive`, json({ archived }, "PATCH")),
  sourceUrl: (id: string, materialId: string, page?: number) => `${getApiBase()}${base(id)}/materials/${encodeURIComponent(materialId)}/files/source.pdf${page == null ? "" : `?original_page=${page}`}`,
  list: (id: string) => api<{ materials: CourseMaterial[] }>(`${base(id)}/materials`),
  imports: (id: string) => api<{ drafts: CourseDraft<ImportArtifact>[] }>(`${base(id)}/material-imports`),
  upload: (id: string, form: FormData) => apiForm<CourseDraft<ImportArtifact>>(`${base(id)}/material-imports`, form),
  import: (id: string, draft: string) => api<CourseDraft<ImportArtifact>>(`${base(id)}/material-imports/${draft}`),
  importAction: (id: string, draft: CourseDraft<ImportArtifact>, action: "review" | "approve" | "retry") => api<CourseDraft<ImportArtifact>>(`${base(id)}/material-imports/${draft.draft_id}/${action}`, json(snapshot(draft))),
  saveImport: (id: string, draft: CourseDraft<ImportArtifact>, artifact: ImportArtifact) => api<CourseDraft<ImportArtifact>>(`${base(id)}/material-imports/${draft.draft_id}`, json({ ...snapshot(draft), artifact }, "PUT")),
  generate: (id: string, materialId: string, teacherRequest = "") => api<CourseDraft<GraphChanges>>(`${base(id)}/changes/generate`, json({ purpose: "material_enrichment", material_id: materialId, teacher_request: teacherRequest })),
  changes: (id: string) => api<{ drafts: CourseDraft<GraphChanges>[]; generation?: CourseDraft<unknown> | null }>(`${base(id)}/changes`),
  retryGeneration: (id: string) => api<CourseDraft<GraphChanges>>(`${base(id)}/changes/retry-generation`, json({})),
  discardGeneration: (id: string, draft: CourseDraft<unknown>) => api(`${base(id)}/changes/${draft.draft_id}/discard-generation`, json(snapshot(draft))),
  saveChanges: (id: string, draft: CourseDraft<GraphChanges>, changes: GraphChanges) => api<CourseDraft<GraphChanges>>(`${base(id)}/changes/${draft.draft_id}`, json({ ...snapshot(draft), changes }, "PUT")),
  reviewChanges: (id: string, draft: CourseDraft<GraphChanges>) => api<CourseDraft<GraphChanges>>(`${base(id)}/changes/${draft.draft_id}/review`, json({})),
  commitChanges: (id: string, draft: CourseDraft<GraphChanges>) => api<CourseNetwork>(`${base(id)}/changes/${draft.draft_id}/commit`, json(snapshot(draft))),
  section: (id: string, material: string, section: string) => api<{ content: string; material_title: string; page_start: number; page_end: number }>(`${base(id)}/materials/${encodeURIComponent(material)}/sections/${encodeURIComponent(section)}`),
};
