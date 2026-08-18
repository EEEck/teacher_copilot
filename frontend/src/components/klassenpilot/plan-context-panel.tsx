"use client";

import type { PlanClassCoreItem, PlanMaterialSummary } from "@/lib/api";
import { groupPlanMaterials } from "@/lib/plan-context-groups";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

const ALWAYS_IN_CONTEXT = [
  { key: "class_identity", label: "Class identity" },
  { key: "teacher_profile", label: "Teacher profile" },
  { key: "subject_guidance", label: "Subject guidance" },
] as const;

function MaterialRow({
  item,
  onRemove,
  busy,
}: {
  item: PlanMaterialSummary;
  onRemove: (materialId: string) => void;
  busy: boolean;
}) {
  const pages =
    item.page_count > 0
      ? `${item.page_count} page${item.page_count === 1 ? "" : "s"}`
      : null;
  return (
    <li className="flex items-start justify-between gap-2 border-b border-border py-2 last:border-b-0">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">
          {item.title || item.material_id}
        </p>
        {pages ? (
          <p className="text-xs text-muted-foreground">{pages}</p>
        ) : null}
        {item.summary ? (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {item.summary}
          </p>
        ) : null}
      </div>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        disabled={busy}
        onClick={() => onRemove(item.material_id)}
      >
        Remove
      </Button>
    </li>
  );
}

export function PlanContextPanel({
  materials,
  classCore,
  onRemoveMaterial,
  onToggleCore,
  busy = false,
}: {
  materials: PlanMaterialSummary[];
  classCore: PlanClassCoreItem[];
  onRemoveMaterial: (materialId: string) => void;
  onToggleCore: (key: string, included: boolean) => void;
  busy?: boolean;
}) {
  const grouped = groupPlanMaterials(materials);

  return (
    <div className="min-h-0 max-h-full w-full min-w-0 flex-1 basis-0 overflow-y-auto overscroll-contain rounded-md border bg-background p-3">
      <section className="space-y-2">
        <h3 className="text-sm font-medium">Uploaded materials</h3>
        {materials.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No PDFs in this plan yet. Use + in chat to attach one.
          </p>
        ) : (
          <>
            {grouped.textbook.length > 0 ? (
              <div>
                <p className="text-xs font-medium text-muted-foreground">
                  Textbook
                </p>
                <ul>
                  {grouped.textbook.map((item) => (
                    <MaterialRow
                      key={item.material_id}
                      item={item}
                      onRemove={onRemoveMaterial}
                      busy={busy}
                    />
                  ))}
                </ul>
              </div>
            ) : null}
            {grouped.personal.length > 0 ? (
              <div>
                <p className="text-xs font-medium text-muted-foreground">
                  Personal
                </p>
                <ul>
                  {grouped.personal.map((item) => (
                    <MaterialRow
                      key={item.material_id}
                      item={item}
                      onRemove={onRemoveMaterial}
                      busy={busy}
                    />
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
      </section>

      <section className="mt-5 space-y-2">
        <h3 className="text-sm font-medium">Class memory</h3>
        <p className="text-xs text-muted-foreground">
          Injected this session. Tools can still read a page you turn off.
        </p>
        <ul>
          {classCore.map((item) => (
            <li
              key={item.key}
              className="flex items-center justify-between gap-2 border-b border-border py-2 last:border-b-0"
            >
              <span className="min-w-0 truncate text-sm">{item.label}</span>
              <Switch
                size="sm"
                checked={item.included}
                disabled={busy || item.locked}
                onCheckedChange={(checked) => onToggleCore(item.key, checked)}
                aria-label={`${item.included ? "Exclude" : "Include"} ${item.label}`}
              />
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-5 space-y-2">
        <h3 className="text-sm font-medium">Always in context</h3>
        <ul>
          {ALWAYS_IN_CONTEXT.map((item) => (
            <li
              key={item.key}
              className="flex items-center justify-between gap-2 border-b border-border py-2 last:border-b-0"
            >
              <span className="text-sm">{item.label}</span>
              <span className="text-xs text-muted-foreground">On</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
