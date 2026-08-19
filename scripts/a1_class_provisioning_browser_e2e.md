# A1 Class Provisioning — Browser HITL Acceptance

Run this against the existing worktree stack created for the A1 E2E sequence.
Reuse its sandbox: do **not** run `down`, `up`, or `--fresh-wiki`.

## Target

- Compose project: `kp_teacher_agent_v2_64977d`
- Frontend: `http://localhost:3303`
- Backend: `http://localhost:8578`
- Precondition: the seeded **Chemie 9b** and API-created **Chemie 8a** exist.
- Browser: use the Codex in-app browser and semantic locators/snapshots. Do not
  substitute APIs, curl, standalone Playwright, or another browser surface for
  the visible assertions.

## Visible browser assertions

1. Open `http://localhost:3303/`. Verify both **Chemie 9b** and **Chemie 8a**
   are visible.
2. Click **New class** and inspect **Curriculum route**.
3. Verify its only route options are **Chemie 8 NTG** and **Chemie 9 NTG**.
   Verify **Physik**, **Biologie**, and **SG** do not appear.
4. Select **Chemie 9 NTG** and enter exactly:
   - Section: `a`
   - School year: `2026_27`
   - Prior learning: `Atombau, Periodensystem und einfache Ionen wurden bereits behandelt.`
   - Roster, one name per line: `Clara Beispiel` and `David Beispiel`
5. Verify the preview reads **Creates Chemie 9a — 2026/27**. Click
   **Create class**.
6. Verify navigation to `/classes/chemie_9a_2026_27` and heading **Chemie 9a**.
7. Verify the new-class dashboard is empty: unit **Not set**, zero open loops,
   zero logged lessons, and no timeline lessons.
8. Verify seeded 9b content is absent: **Redox with ion**, **21 open loops**,
   and the seeded April/May lesson titles must not appear.
9. Open **Browse class files**. Verify these files are discoverable:
   `course_state.md`, `curriculum_profile.md`, `students.md`,
   `trusted_sources.md`, and the memory pages.
10. Verify `course_network/network.json` is absent. A2 owns course-network
    adoption.
11. Return home and verify **Chemie 8a**, **Chemie 9a**, and **Chemie 9b** are
    all listed.
12. Attempt to create **Chemie 9a** again using the same form data. Verify an
    inline error contains **already exists**, the browser remains on the
    creation form, and no duplicate class card appears.

## Browser console and network gate

At the end of the browser run, inspect the browser developer APIs:

- Console warnings/errors: none.
- Failed requests: none except the intentional duplicate `POST /api/classes`
  returning **422**.
- No unexpected **401**, **403**, **404**, or **500** response.
- No LLM reasoning UI, running-agent job, or model-generated copy appears
  during class creation.
- Navigate back to the all-classes page and leave that page open as the HITL
  deliverable.

## Docker log gate

Inspect the bounded logs for the same Compose project; do not follow logs
indefinitely:

```powershell
$composeProject = 'kp_teacher_agent_v2_64977d'
docker compose -p $composeProject logs --tail 300 backend frontend
```

During the class-creation interval, acceptance fails if the output contains
`500 Internal Server Error`, `Traceback`, `Unhandled error`, `duplicate column name`,
or a model-provider request. The intentional duplicate request may appear only
as a handled **422**.

## Evidence to record

Record the current URL after each key transition, every assertion's pass/fail
evidence, the console result, failed-request result (separating the intentional
422), the Docker-log scan, absence of model UI/calls, the final open URL, and
any concerns.
