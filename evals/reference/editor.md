# Launch Readiness — Triage Board

This is the open triage list for the v2 launch. Each item has a priority, an
owner, and a state. The page should let a reader work the list — filter by
state, change priority, and copy the result back out — not just read a static
table. Every editor ends in an export button.

## Triage items

| ID    | Title                              | Priority | Owner   | State       |
|-------|------------------------------------|----------|---------|-------------|
| L-101 | Async recommendations call         | P0       | Platform| In progress |
| L-102 | Finalize pricing tier copy         | P1       | Legal   | Blocked     |
| L-103 | Onboarding funnel 100% rollout     | P0       | Growth  | Todo        |
| L-104 | Billing ledger cutover runbook     | P1       | Billing | In review   |
| L-105 | Dashboard empty-state polish       | P2       | Design  | Todo        |
| L-106 | Load test at 2x peak               | P1       | SRE     | Todo        |
| L-107 | Rotate staging API credentials     | P2       | SRE     | Done        |
| L-108 | Docs: edge cache config variants   | P2       | DevRel  | In progress |

## Workflow

States move left to right: **Todo → In progress → In review → Done**, with
**Blocked** as a side state any item can enter. A blocked item must name what it
is waiting on.

## Priority rubric

- **P0** — launch blocker. Must be Done before the rollout date.
- **P1** — should ship for launch; descope only with sign-off.
- **P2** — nice to have; safe to defer to the first patch.

## Exit criteria

- Every P0 is in the **Done** state.
- No item is in **Blocked**.
- The load test (L-106) has passed at 2x projected peak traffic.

## Notes

- L-102 is the long pole; it gates the pricing experiment, not the launch
  itself, so it can ship in the first patch if legal review slips.
- Export the working board as Markdown when you hand off at end of day.
