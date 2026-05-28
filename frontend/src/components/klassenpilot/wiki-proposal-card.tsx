"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WikiUpdateProposal } from "@/lib/api";

export function WikiProposalCard({
  proposal,
  content,
  approved,
  onContentChange,
  onApprovedChange,
}: {
  proposal: WikiUpdateProposal;
  content: string;
  approved: boolean;
  onContentChange: (value: string) => void;
  onApprovedChange: (value: boolean) => void;
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-4">
          <CardTitle className="font-mono text-sm font-normal text-primary">{proposal.wiki_path}</CardTitle>
          <div className="flex items-center gap-2">
            <Checkbox id={`approve-${proposal.wiki_path}`} checked={approved} onCheckedChange={(v) => onApprovedChange(!!v)} />
            <Label htmlFor={`approve-${proposal.wiki_path}`} className="text-xs text-muted-foreground">
              Include in save
            </Label>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">{proposal.rationale}</p>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Current</p>
            <pre className="max-h-44 overflow-auto rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">
              {proposal.current_content || "(empty)"}
            </pre>
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-muted-foreground">Proposed (editable)</p>
            <Textarea
              className="min-h-44 font-mono text-xs"
              value={content}
              onChange={(e) => onContentChange(e.target.value)}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
