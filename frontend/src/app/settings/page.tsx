import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div>
      <PageHeader
        title="Settings"
        description="Account and app preferences will live here."
      />
      <Card>
        <CardContent className="space-y-2 p-6 text-sm text-muted-foreground">
          <p>Nothing to configure yet.</p>
          <p>
            This placeholder keeps a clear home for future preferences without
            cluttering the top bar.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
