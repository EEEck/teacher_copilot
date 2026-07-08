import { ClassHomeClient } from "./class-home-client";

export default async function ClassHomePage({
  params,
  searchParams,
}: {
  params: Promise<{ classId: string }>;
  searchParams: Promise<{ highlight?: string }>;
}) {
  const { classId } = await params;
  const { highlight } = await searchParams;
  return <ClassHomeClient classId={classId} highlightDate={highlight} />;
}
