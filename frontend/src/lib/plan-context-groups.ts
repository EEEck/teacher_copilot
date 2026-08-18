import type { PlanMaterialSummary } from "@/lib/api";

export function groupPlanMaterials(materials: PlanMaterialSummary[]) {
  return {
    textbook: materials.filter((item) => item.arm === "textbook"),
    personal: materials.filter((item) => item.arm === "personal"),
  };
}
