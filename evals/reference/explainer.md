# How the Edge Cache Works

The edge cache sits between clients and the origin API. It serves hot responses
from the nearest region, collapses duplicate in-flight requests, and falls back
to the origin on a miss — so most reads never touch the database. This page
explains the request path, the configuration variants, and the common
questions.

## The request path

A read request flows through five stages:

1. **Resolve key.** The edge derives a cache key from the method, normalized
   path, and an allowlist of headers (never cookies or auth tokens).
2. **Lookup.** If a fresh entry exists, it is returned immediately as a HIT.
3. **Coalesce.** On a miss, concurrent requests for the same key are collapsed
   into a single origin fetch; the rest wait on that one fetch.
4. **Fetch origin.** The winning request calls the origin, then stores the
   response with a TTL derived from `Cache-Control`.
5. **Serve + revalidate.** Stale-but-usable entries are served instantly while
   an async revalidation refreshes them in the background.

## Configuration variants

The same cache runs in three modes. Pick one per route.

### Standard

Balanced defaults: 60s TTL, stale-while-revalidate enabled, coalescing on.
Good for most read-heavy JSON endpoints.

### Aggressive

Long TTL (1h), serves stale up to 24h on origin errors. Use for slow-changing
catalog data where staleness is acceptable and origin protection matters most.

### Bypass

No caching; every request hits the origin. Use for personalized or write
endpoints where a shared cache would leak data across users.

## Tuning knobs

- `ttl` — how long an entry is fresh.
- `stale_while_revalidate` — window to serve stale during async refresh.
- `stale_if_error` — window to serve stale when the origin is failing.
- `vary_headers` — the header allowlist that participates in the key.

## FAQ

**Does the cache store authenticated responses?**
No. Requests carrying an `Authorization` header or session cookie are routed in
Bypass mode and never written to a shared entry.

**What happens on an origin outage?**
With `stale_if_error` set, the edge keeps serving the last good response within
the configured window instead of returning an error.

**How do I force a refresh?**
Purge the key from the dashboard or send a request with `Cache-Control:
no-cache`, which revalidates that single entry without flushing the region.
