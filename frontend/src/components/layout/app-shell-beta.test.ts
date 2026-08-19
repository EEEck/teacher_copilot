// @vitest-environment happy-dom

import * as React from "react";
import { act, createElement, type ComponentProps } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "@/components/layout/app-shell";
import { client, type BetaIdentity } from "@/lib/api";

const navigation = vi.hoisted(() => ({
  pathname: "/",
  router: {
    push: vi.fn(),
    refresh: vi.fn(),
    replace: vi.fn(),
  },
  searchParams: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
  useRouter: () => navigation.router,
  useSearchParams: () => navigation.searchParams,
}));

const COMPLETE_BETA_IDENTITY: BetaIdentity = {
  tester_id: "tester-1",
  workspace_id: "workspace-1",
  role: "tester",
  display_name: "Ada",
  profile_complete: true,
  member_since: "2026-08-18T00:00:00Z",
  stats: {
    feedback_notes: 0,
    workflow_sessions: 0,
    wiki_commits: 0,
  },
};

let mountedRoots: Root[] = [];

function shellElement(betaEnabled?: boolean) {
  const props = {
    children: createElement("p", null, "Class navigation"),
    ...(betaEnabled === undefined ? {} : { betaEnabled }),
  } as ComponentProps<typeof AppShell> & { betaEnabled: boolean };
  return createElement(AppShell, props);
}

async function mountShell(betaEnabled?: boolean): Promise<Root> {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  mountedRoots.push(root);
  await act(async () => {
    root.render(shellElement(betaEnabled));
  });
  return root;
}

async function navigate(root: Root, betaEnabled?: boolean): Promise<void> {
  navigation.pathname = "/classes/chemie_8a_2026_27";
  await act(async () => {
    root.render(shellElement(betaEnabled));
  });
}

describe("AppShell beta identity integration", () => {
  beforeEach(() => {
    vi.stubGlobal("React", React);
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    mountedRoots = [];
    navigation.pathname = "/";
    navigation.router.push.mockReset();
    navigation.router.refresh.mockReset();
    navigation.router.replace.mockReset();
    vi.spyOn(client, "betaMe").mockResolvedValue(COMPLETE_BETA_IDENTITY);
  });

  afterEach(async () => {
    await act(async () => {
      for (const root of mountedRoots) root.unmount();
    });
    document.body.replaceChildren();
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it.each([
    [undefined, 0],
    ["false", 0],
    ["FALSE", 0],
    ["0", 0],
    ["off", 0],
    ["NO", 0],
    ["true", 2],
    ["TRUE", 2],
    ["1", 2],
    ["on", 2],
    ["ON", 2],
    ["yes", 2],
    ["YeS", 2],
  ] as const)("parses public beta setting %s at the AppShell default boundary", async (value, calls) => {
    vi.stubEnv("NEXT_PUBLIC_BETA_ENABLED", value);

    await mountShell();

    expect(client.betaMe).toHaveBeenCalledTimes(calls);
  });

  it("never probes beta identity when non-beta navigation mounts or changes route", async () => {
    const root = await mountShell(false);
    await navigate(root, false);

    expect(client.betaMe).not.toHaveBeenCalled();
  });

  it("preserves both beta identity probes across beta-enabled navigation", async () => {
    const root = await mountShell(true);
    expect(client.betaMe).toHaveBeenCalledTimes(2);

    await navigate(root, true);
    expect(client.betaMe).toHaveBeenCalledTimes(4);
  });
});
