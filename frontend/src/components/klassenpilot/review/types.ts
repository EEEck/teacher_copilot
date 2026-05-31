import type { WikiUpdateProposal } from "@/lib/api";

export type FileChange = {
  path: string;
  before: string;
  after: string;
  approved: boolean;
  required?: boolean;
};

export function fromWikiProposals(
  proposals: WikiUpdateProposal[],
  approvedByPath: Record<string, boolean>,
  contentByPath: Record<string, string>,
): FileChange[] {
  return proposals.map((p) => ({
    path: p.wiki_path,
    before: p.current_content,
    after: contentByPath[p.wiki_path] ?? p.proposed_content,
    approved: approvedByPath[p.wiki_path] ?? true,
    required: p.wiki_path.includes("lesson_results.md"),
  }));
}

export function fromPlanSave(
  classId: string,
  lessonDate: string,
  currentContent: string,
  proposedContent: string,
  approved = true,
): FileChange {
  const path = `wiki/classes/${classId}/lessons/${lessonDate}/lesson_plan.md`;
  return {
    path,
    before: currentContent,
    after: proposedContent,
    approved,
    required: true,
  };
}
