"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { Network } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  CourseNetworkAdoption,
  isExactCourseNetworkReview,
  isExactPassingReview,
  type CourseNetworkAdoptionAction,
} from "./course-network-adoption";
import { CourseNetworkOutline } from "./course-network-outline";
import { LearningBlockInspector } from "./learning-block-inspector";
import { ActionLink } from "@/components/klassenpilot/action-link";
import { PageHeader } from "@/components/layout/page-header";
import { useArtifactSessionShell } from "@/components/layout/shell-layout";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { SegmentedToggle } from "@/components/ui/segmented-toggle";
import { Skeleton } from "@/components/ui/skeleton";
import type { CourseNetwork } from "@/features/course-network/types";
import {
  client,
  type CourseNetworkDraftResponse,
} from "@/lib/api";

const CourseNetworkCanvas = dynamic(
  () =>
    import("./course-network-canvas").then(
      (module) => module.CourseNetworkCanvas,
    ),
  {
    ssr: false,
    loading: () => (
      <Skeleton
        className="h-full min-h-0 rounded-xl border border-border"
        aria-label="Loading course network graph"
      />
    ),
  },
);

function messageFromError(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function selectedOrFirst(
  network: CourseNetwork,
  selectedId: string | null,
): string | null {
  return network.nodes.some((node) => node.id === selectedId)
    ? selectedId
    : (network.nodes[0]?.id ?? null);
}

function CourseWorkspaceHeader({
  classId,
  status,
}: {
  classId: string;
  status: string;
}) {
  return (
    <div className="shrink-0">
      <PageHeader
        backHref={`/classes/${encodeURIComponent(classId)}`}
        backLabel="Class"
        title="Course network"
        description="Inspect the class learning structure and its curriculum evidence. Editing comes later."
        variant="compact"
        trailing={
          <SegmentedToggle
            value="network"
            onValueChange={() => {}}
            options={[
              { value: "network", label: "Network" },
              {
                value: "materials",
                label: (
                  <span className="inline-flex items-center gap-1">
                    Materials
                    <span className="text-[10px] font-normal">Coming soon</span>
                  </span>
                ),
                disabled: true,
                disabledReason: "Materials workspace coming soon",
              },
            ]}
            aria-label="Course workspace section"
          />
        }
      />
      <div className="mb-3 flex flex-wrap items-center gap-2 border-b border-border pb-3">
        <Badge variant="outline" className="bg-muted">
          {status}
        </Badge>
        <span className="text-xs text-muted-foreground">
          Read-only · view state is not saved
        </span>
      </div>
    </div>
  );
}

function CourseNetworkLoading({ classId }: { classId: string }) {
  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden" aria-busy="true">
      <CourseWorkspaceHeader classId={classId} status="Loading" />
      <div className="grid min-h-0 flex-1 overflow-hidden sm:grid-cols-[minmax(0,1fr)_minmax(16rem,20rem)] lg:grid-cols-[minmax(0,1fr)_360px]">
        <Skeleton className="h-full min-h-0 rounded-xl" />
        <div className="space-y-3 rounded-xl border border-border p-4">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
      </div>
      <p className="sr-only" role="status">
        Loading course network
      </p>
    </div>
  );
}

export function CourseNetworkWorkspace({ classId }: { classId: string }) {
  const router = useRouter();
  const [network, setNetwork] = useState<CourseNetwork | null>(null);
  const [draft, setDraft] = useState<CourseNetworkDraftResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [discarded, setDiscarded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busyAction, setBusyAction] =
    useState<CourseNetworkAdoptionAction | null>(null);
  const requestIdRef = useRef(0);
  const actionLockedRef = useRef(false);

  useArtifactSessionShell(true);

  const transitionToAdoptedNetwork = useCallback(
    (adoptedNetwork: CourseNetwork, refreshRoute = false) => {
      setNetwork(adoptedNetwork);
      setDraft(null);
      setSelectedId((current) => selectedOrFirst(adoptedNetwork, current));
      if (refreshRoute) {
        router.replace(`/classes/${encodeURIComponent(classId)}/course`);
        router.refresh();
      }
    },
    [classId, router],
  );

  const loadWorkspace = useCallback(async () => {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    setDiscarded(false);
    try {
      const response = await client.getCourseNetwork(classId);
      if (requestId !== requestIdRef.current) return;
      if (response.network) {
        transitionToAdoptedNetwork(response.network);
        return;
      }

      try {
        const openedDraft = await client.openCourseNetworkSeedDraft(classId);
        if (requestId !== requestIdRef.current) return;
        setDraft(openedDraft);
        setNetwork(null);
        setSelectedId((current) => selectedOrFirst(openedDraft.network, current));
      } catch (openError) {
        // Adoption may have completed between the nullable GET and draft open.
        const latest = await client.getCourseNetwork(classId);
        if (requestId !== requestIdRef.current) return;
        if (!latest.network) throw openError;
        transitionToAdoptedNetwork(latest.network);
      }
    } catch (loadError) {
      if (requestId !== requestIdRef.current) return;
      setNetwork(null);
      setDraft(null);
      setError(
        messageFromError(loadError, "The course network could not be loaded."),
      );
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [classId, transitionToAdoptedNetwork]);

  useEffect(() => {
    void loadWorkspace();
    return () => {
      requestIdRef.current += 1;
    };
  }, [loadWorkspace]);

  const runAction = useCallback(
    async (
      action: CourseNetworkAdoptionAction,
      operation: () => Promise<void>,
    ) => {
      if (actionLockedRef.current) return;
      actionLockedRef.current = true;
      setBusyAction(action);
      setError(null);
      try {
        await operation();
      } catch (actionError) {
        setError(
          messageFromError(
            actionError,
            `The ${action} action could not be completed.`,
          ),
        );
      } finally {
        actionLockedRef.current = false;
        setBusyAction(null);
      }
    },
    [],
  );

  const reviewProposal = useCallback(async () => {
    if (!draft) return;
    await runAction("review", async () => {
      const reviewed = await client.reviewCourseNetworkSeed(
        classId,
        draft.draft_id,
      );
      setDraft(reviewed);
      setSelectedId((current) => selectedOrFirst(reviewed.network, current));
    });
  }, [classId, draft, runAction]);

  const adoptProposal = useCallback(async () => {
    if (!draft) return;
    await runAction("adopt", async () => {
      if (!isExactPassingReview(draft)) {
        throw new Error(
          "Adoption requires a passing review for this exact proposal revision and hash.",
        );
      }
      try {
        const adopted = await client.adoptCourseNetworkSeed(
          classId,
          draft.draft_id,
          {
            expected_revision: draft.artifact_revision,
            expected_hash: draft.artifact_hash,
          },
        );
        transitionToAdoptedNetwork(adopted.network, true);
      } catch (adoptError) {
        // The server may have committed before a timeout or stale response arrived.
        try {
          const latest = await client.getCourseNetwork(classId);
          if (latest.network) {
            transitionToAdoptedNetwork(latest.network, true);
            return;
          }
        } catch {
          // Preserve the original adoption failure if reconciliation is unavailable.
        }

        try {
          const latestDraft = await client.getCourseNetworkDraft(
            classId,
            draft.draft_id,
          );
          setDraft(latestDraft);
          setSelectedId((current) =>
            selectedOrFirst(latestDraft.network, current),
          );
        } catch {
          // The explicit refresh action remains available if the draft changed.
        }
        throw adoptError;
      }
    });
  }, [classId, draft, runAction, transitionToAdoptedNetwork]);

  const discardProposal = useCallback(async () => {
    if (!draft) return;
    await runAction("discard", async () => {
      await client.discardWorkflowDraft(classId, draft.draft_id);
      setDraft(null);
      setNetwork(null);
      setDiscarded(true);
      setSelectedId(null);
    });
  }, [classId, draft, runAction]);

  if (loading) return <CourseNetworkLoading classId={classId} />;

  const status = discarded
    ? "Legacy framework"
    : network
      ? `Adopted · revision ${network.revision}`
      : draft
        ? isExactPassingReview(draft)
          ? "Proposal · review passed"
          : isExactCourseNetworkReview(draft)
            ? "Proposal · review complete"
            : "Proposal · review required"
        : "Unavailable";

  if (!network && !draft && !discarded) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <CourseWorkspaceHeader classId={classId} status={status} />
        <Alert variant="destructive" className="max-w-3xl">
          <AlertTitle>Course network unavailable</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>{error ?? "No course network data was returned."}</p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" onClick={() => void loadWorkspace()}>
                Try again
              </Button>
              <ActionLink href={`/classes/${encodeURIComponent(classId)}`} variant="ghost">
                Return to class
              </ActionLink>
            </div>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  if (discarded) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <CourseWorkspaceHeader classId={classId} status={status} />
        <Card className="max-w-3xl">
          <CardHeader>
            <CardTitle>Proposal discarded</CardTitle>
            <CardDescription>
              No canonical course network was created. This class remains on its
              legacy teaching framework.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ActionLink href={`/classes/${encodeURIComponent(classId)}`} variant="default">
              Return to class
            </ActionLink>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      <CourseWorkspaceHeader classId={classId} status={status} />

      {error ? (
        <Alert variant="destructive" className="mb-3 shrink-0">
          <AlertTitle>Action not completed</AlertTitle>
          <AlertDescription className="space-y-3">
            <p>{error}</p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => void loadWorkspace()}
            >
              Refresh state
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {draft ? (
        <CourseNetworkAdoption
          classId={classId}
          draft={draft}
          selectedId={selectedId}
          onSelect={setSelectedId}
          busyAction={busyAction}
          onReview={reviewProposal}
          onAdopt={adoptProposal}
          onDiscard={discardProposal}
        />
      ) : network && network.nodes.length ? (
        <div className="grid items-start gap-3 pb-4 sm:grid-cols-[minmax(0,1fr)_minmax(16rem,20rem)] sm:gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div className="hidden min-h-[24rem] overflow-hidden sm:sticky sm:top-0 sm:block sm:h-[min(70dvh,36rem)]">
            <CourseNetworkCanvas
              network={network}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </div>
          <div className="flex flex-col gap-3 sm:hidden">
            <Alert className="border-border bg-muted">
              <AlertTitle>Outline view on smaller screens</AlertTitle>
              <AlertDescription>
                The searchable outline is the graph view on smaller screens. The
                canvas appears on wider screens.
              </AlertDescription>
            </Alert>
            <CourseNetworkOutline
              nodes={network.nodes}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />
          </div>
          <LearningBlockInspector
            classId={classId}
            nodes={network.nodes}
            edges={network.edges}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </div>
      ) : network ? (
        <Empty className="min-h-[28rem] border border-border bg-card shadow-sm">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Network aria-hidden="true" />
            </EmptyMedia>
            <EmptyTitle>No learning blocks yet</EmptyTitle>
            <EmptyDescription>
              The canonical course network exists, but it does not contain any
              learning blocks to inspect.
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <ActionLink href={`/classes/${encodeURIComponent(classId)}`} variant="outline">
              Return to class
            </ActionLink>
          </EmptyContent>
        </Empty>
      ) : null}
    </div>
  );
}
