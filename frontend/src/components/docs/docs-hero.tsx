export function DocsHero() {
  return (
    <section className="docs-sheet relative overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="absolute inset-x-0 top-0 h-1 bg-primary" aria-hidden="true" />
      <div className="px-6 py-8 lg:px-10 lg:py-10">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
          Beta guide
        </p>
        <h1 className="mt-4 max-w-2xl text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
          The AI Assistant That Knows Your Class
        </h1>
        <p className="mt-4 max-w-2xl text-lg leading-8 text-muted-foreground">
          KlassenPilot turns approved lesson updates into class memory, then uses it to
          accelerate drafting what&apos;s next: plans, notes, materials, and follow-ups
          for your review.
        </p>
      </div>
    </section>
  );
}
