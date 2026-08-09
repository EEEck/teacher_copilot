/** Plan-session PDF arm for the composer attachment adapter (Textbook vs Personal). */

export type PlanMaterialArm = "textbook" | "personal";

let currentArm: PlanMaterialArm = "textbook";

export function getPlanMaterialArm(): PlanMaterialArm {
  return currentArm;
}

export function setPlanMaterialArm(arm: PlanMaterialArm): void {
  currentArm = arm;
}
