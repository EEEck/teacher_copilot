"use client";

import { useCallback, useMemo, useState } from "react";
import type { WikiUpdateProposal } from "@/lib/api";
import { fromWikiProposals, type FileChange } from "./types";

export function useFileChangeReview(proposals: WikiUpdateProposal[]) {
  const [approvedByPath, setApprovedByPath] = useState<Record<string, boolean>>({});
  const [contentByPath, setContentByPath] = useState<Record<string, string>>({});
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const initFromProposals = useCallback((list: WikiUpdateProposal[]) => {
    const approved: Record<string, boolean> = {};
    const content: Record<string, string> = {};
    for (const p of list) {
      approved[p.wiki_path] = true;
      content[p.wiki_path] = p.proposed_content;
    }
    setApprovedByPath(approved);
    setContentByPath(content);
    setSelectedPath(list[0]?.wiki_path ?? null);
  }, []);

  const items: FileChange[] = useMemo(
    () => fromWikiProposals(proposals, approvedByPath, contentByPath),
    [proposals, approvedByPath, contentByPath],
  );

  const selected = useMemo(() => {
    if (items.length === 0) return null;
    return items.find((i) => i.path === selectedPath) ?? items[0];
  }, [items, selectedPath]);

  const updateContent = useCallback((path: string, markdown: string) => {
    setContentByPath((prev) => ({ ...prev, [path]: markdown }));
  }, []);

  const getCommitPayload = useCallback(() => {
    return proposals
      .filter((p) => approvedByPath[p.wiki_path])
      .map((p) => ({
        wiki_path: p.wiki_path,
        content: contentByPath[p.wiki_path] ?? p.proposed_content,
        approved: true as const,
      }));
  }, [proposals, approvedByPath, contentByPath]);

  const setApproved = useCallback(
    (path: string, approved: boolean) => {
      const item = items.find((i) => i.path === path);
      if (item?.required && !approved) return;
      setApprovedByPath((prev) => ({ ...prev, [path]: approved }));
    },
    [items],
  );

  const approveAll = useCallback(() => {
    const next: Record<string, boolean> = {};
    for (const p of proposals) next[p.wiki_path] = true;
    setApprovedByPath(next);
  }, [proposals]);

  const clear = useCallback(() => {
    setApprovedByPath({});
    setContentByPath({});
    setSelectedPath(null);
  }, []);

  const hasLessonResultsApproved = items.some(
    (i) => i.approved && i.path.includes("lesson_results.md"),
  );

  return {
    items,
    selected,
    selectedPath,
    setSelectedPath,
    contentByPath,
    updateContent,
    getCommitPayload,
    setApproved,
    approveAll,
    initFromProposals,
    clear,
    hasLessonResultsApproved,
    approvedByPath,
  };
}
