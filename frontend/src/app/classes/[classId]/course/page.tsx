import { CourseNetworkWorkspace } from "@/components/klassenpilot/course/course-network-workspace";

export default async function CourseNetworkPage({
  params,
}: {
  params: Promise<{ classId: string }>;
}) {
  const { classId } = await params;
  return <CourseNetworkWorkspace classId={classId} />;
}
