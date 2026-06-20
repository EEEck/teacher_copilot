import { DocsCanvas, DocsContentFrame } from "@/components/docs/docs-canvas";

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <DocsCanvas>
      <DocsContentFrame>{children}</DocsContentFrame>
    </DocsCanvas>
  );
}
