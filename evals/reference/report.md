# Weekly Status — Growth Platform

**Week of 2026-06-01 · Owner: A. Rivera · Status: On track**

This is the weekly status for the Growth Platform team. We shipped the new
onboarding funnel to 50% of new signups, cut median activation time, and
unblocked the billing migration. One risk is trending the wrong way and is
called out below.

## Key metrics

| Metric                | This week | Last week | Target  |
|-----------------------|-----------|-----------|---------|
| Weekly active users   | 48,200    | 46,900    | 50,000  |
| Activation rate (7d)  | 41.3%     | 38.1%     | 45%     |
| Median activation time| 2h 10m    | 3h 05m    | < 2h    |
| Trial → paid          | 6.8%      | 6.9%      | 8%      |
| p95 API latency       | 410 ms    | 360 ms    | < 400ms |

## Highlights

- Rolled out the redesigned onboarding funnel to 50% of new signups; the
  variant lifts 7-day activation by 3.2 points with no regression in retention.
- Closed the billing-migration blocker — dual-writes to the new ledger are
  verified against the legacy system for the last 14 days with zero drift.
- Cut median activation time by ~55 minutes after moving workspace
  provisioning off the signup critical path.

## Risks and concerns

- **p95 latency is regressing** (360ms → 410ms) and has now crossed the 400ms
  budget. Suspected cause: the new funnel issues an extra synchronous call to
  the recommendations service. Owner: Platform. Mitigation: make the call async
  behind the first render. Target: back under budget by 2026-06-10.
- Trial → paid is flat at 6.8% versus an 8% target; pricing experiment is
  blocked on legal review of the new tier copy.

## Decisions made

- Approved rolling the onboarding funnel to 100% on 2026-06-09, contingent on
  the latency fix landing first.
- Deferred the referral program to next quarter to protect activation focus.

## Next week

- Land the async recommendations fix and confirm p95 < 400ms.
- Ramp the onboarding funnel to 100%.
- Unblock the pricing experiment with finalized tier copy.
