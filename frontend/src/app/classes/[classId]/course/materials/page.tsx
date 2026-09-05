import { CourseMaterialLibrary } from "@/components/klassenpilot/course/course-material-library";

export default async function CourseMaterialsPage({ params }: { params: Promise<{ classId: string }> }) {
  const { classId } = await params;
  return <CourseMaterialLibrary classId={classId} />;
}
