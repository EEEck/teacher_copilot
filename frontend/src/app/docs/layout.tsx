import { DocsCanvas } from "@/components/docs/docs-canvas";

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <DocsCanvas className="-mx-2 px-2 sm:-mx-4 sm:px-4">{children}</DocsCanvas>
  );
}
