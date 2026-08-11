# listing-radar — design

**Date:** 2026-08-10
**Status:** approved, ready for implementation planning

## What this is

A read-only command-line tool that answers four questions an Etsy seller has before
they build a product, using only data Etsy already makes public. It is extracted
from a private working repo (`~/01-projects/ai-infra/etsy-intel`) and published
under MIT.

The tool measures **demand**. It does not grade listings. That distinction is the
product, and it comes from a measured fact about the author's own shop: it scores
91 on every listing-hygiene check and has made five lifetime sales. Listing quality
was never the constraint, so a tool that grades listing quality answers the wrong
question.

## Why it can exist at all

Etsy publishes no search-volume API. But `GET /v3/application/listings/active`
returns `views` and `num_favorers` for **any** active listing with only an app key,
and each listing carries an original creation date. Lifetime views over listing age
gives views/day. `GET /shops/{id}` gives `transaction_sold_count` and shop age. So
every competitor's traction is public, and demand can be inferred from the traction
of whoever currently ranks:

```
demand(phrase)       = median views/day of the listings ranking for that phrase
competition(phrase)  = count of active listings matching it
entrenchment(phrase) = median age in days of the top rankers
winnable(phrase)     = min(1.0, 400 / max(entrenchment, 1))
opportunity(phrase)  = demand / log10(competition + 10) * winnable
```

`winnable` encodes that young top-rankers mean the result page is displaceable and
ancient ones mean it is not; it saturates at 1.0 below roughly 400 days. The `+10`
inside the log keeps low-competition phrases from dividing by a number near zero.
These are the formulas as implemented in the source repo and they are carried over
unchanged — they are heuristics with no published validation, and the README says so.

A phrase whose top rankers earn ~0 views/day has no traffic, however targeted it
feels. That single sentence is what the tool exists to make cheap to check.

## Commands

Four commands behind one entry point. Each maps to a real question and each emits
the caveat that makes its answer safe to act on.

### `demand <phrase>`

Returns demand, competition, entrenchment, and the opportunity score for a search
phrase. When the phrase returns few listings and near-zero rankers' traffic, it is
labelled **NO MARKET** rather than given a low score — a dead phrase must never be
mistaken for a cheap one.

### `traction <shop|listing>`

Returns views/day, lifetime views, favorers, and (for shops) sold count and shop
age. This is the competitor-research primitive.

**Hard requirement:** uses `original_creation_timestamp`, never `creation_timestamp`.
Digital listings auto-renew roughly every four months and the naive field reports
the last renewal, which makes every settled listing read as brand new. In the source
repo this bug caused a recon pass to return "0 settled listings" across four phrases,
and made a 69-day-old listing report as 17 days old. The tool must not repeat it, and
the field choice is asserted in tests.

### `rank <phrase> --listing <id>`

Answers "why does my listing get no views" by classifying the cause, because the
three causes have completely different fixes:

| Verdict | Meaning | Implication |
|---|---|---|
| `BURIED` | ranks, but deep (page 3+) | competitive niche; the gap is authority, not wording |
| `ABSENT` | not present in 250 results | not actually competing for that phrase |
| `NO MARKET` | phrase returns few listings | nobody sells it because nobody buys it |

**Blocking caveat, printed on every run:** `listings/active?keywords=` is the API's
relevance search, not buyer-facing Etsy search ranking. Position is ordinal evidence
only. The tool states this in its own output rather than burying it in documentation.

### `niche <vertical>`

Screens a candidate vertical against three gates, all of which must pass:

- **DEMAND** — sellers in that vertical actually sell, not merely accumulate views
- **FORMAT** — what currently wins is a format you can beat
- **ROOM** — enough competitors to imply a market, few enough that a new listing can
  realistically place

The third gate exists because demand alone is a trap. In the source shop, 39 of 70
listings targeted phrases carrying 5,000–99,000 competitors and never appeared in the
top 250 results for their own lead phrase. Demand you cannot surface against is not
an opportunity.

## Architecture

Five units, each independently testable:

| Unit | Responsibility | Depends on |
|---|---|---|
| `client` | thin Etsy API wrapper; auth is opt-in and defaults off; rate-limit aware | nothing |
| `cache` | on-disk response cache keyed by endpoint + params; reports cache hits | nothing |
| `scoring` | the four formulas as pure functions over plain dicts | nothing |
| `commands/*` | one module per command: argument parsing, orchestration, output | client, cache, scoring |
| `cli` | entry point, subcommand dispatch, `--help` | commands |

`scoring` holds no I/O, which is what makes the test suite meaningful and outside
pull requests safe to accept.

**Nothing writes to Etsy.** No OAuth flow, no write scopes, no token refresh. The
write-path scripts from the source repo (`apply_titles`, `retag`, `set_images`,
`publish_product`, `upload_files`) are explicitly out of scope and stay private.
`whats_selling` is also excluded: it requires the `transactions_r` OAuth scope.

## Data and secrets posture

- The repo is created in a **new directory**. The source repo carries 193M of scraped
  competitor pages and private shop figures with no `.gitignore`; it is never
  `git init`-ed and nothing is copied wholesale from it.
- `.gitignore` is written before the first commit: `.env`, `cache/`, `data/`,
  `*.json` artifacts, `__pycache__/`.
- Credentials are read from the environment only — `ETSY_KEYSTRING` and
  `ETSY_SHARED_SECRET`. Never from a file inside the repo.
- **Credential errors must be explicit.** Etsy rejects a bare keystring on these
  endpoints with `403 {"error":"Shared secret is required in x-api-key header."}`;
  the credential is `keystring:shared_secret`. In the source project this 403 was
  mapped to a generic fallback and read for weeks as "our app is not approved yet" —
  a plausible story that was wrong and undisprovable without calling Etsy by hand.
  The tool names the actual cause.
- A secret scan runs against the full history before the first push.

## Testing

- Unit tests over `scoring` using fixture JSON captured from real responses with
  identifying detail removed.
- A regression test asserting `traction` reads `original_creation_timestamp` and
  fails if `creation_timestamp` is used.
- A test that `demand` returns NO MARKET rather than a low score for a
  low-listing-count, low-traffic phrase.
- `client` tested against recorded fixtures, not live Etsy.

## Repository and positioning

- **Name:** `listing-radar`. Distinct name avoids the Etsy trademark surface;
  discoverability comes from the description, "demand research for Etsy sellers".
- **License:** MIT. AGPL was considered and rejected — running a CLI is not network
  use, so it would not trigger, and the moat was never the code.
- **README opening** leads with the author's own shop as the counterexample: 91 on
  hygiene checks, five sales. This is honest, it separates the tool from every
  "optimize your titles" product, and it is the opposite of the fabricated-authority
  pattern that had to be stripped from listingresearchos.com twice.
- The README states what the tool replaces: eRank, Marmalade and Alura charge
  roughly $20–50/month for demand estimates; this infers them for free.
- Repository homepage field points to `listingresearchos.com`. One honest paragraph
  describes what the paid product does that the CLI does not. No badges, no
  call-to-action section.

### Why open-sourcing this serves the author

The measured problem is that `listingresearchos.com` has **zero Common Crawl
captures** — it is absent from the corpus AI systems train and retrieve on, and the
documented fix is inbound links from already-crawled hosts. GitHub is crawled
relentlessly.

Stated precisely, because the naive version of this claim is wrong: GitHub renders
README links with `rel="nofollow ugc"`, so this passes little classic SEO authority.
Common Crawl ignores nofollow. The benefit is corpus presence and entity association,
not PageRank. Adoption is what produces captures, which is why the design optimises
for a tool someone uses twice rather than for the fastest possible publish.

## Known constraints

- Every user needs their own Etsy app key, which requires registration and approval.
  This is real adoption friction and no repository can remove it. The README states
  it in the first section rather than after installation instructions.
- Rate limits are per-key, so the cache is not an optimisation but a requirement, and
  the tool reports what it served from cache.
- Etsy's API terms and trademark policy have not been read as part of this design.
  They must be reviewed before the first public push, since the tool encourages third
  parties to use their own keys.

## Out of scope

- Any write to a live shop.
- The AI-visibility toolkit (`crawl_presence`, `bot_probe`, `fanout`, `relevance`,
  `report`). Separate audience, separate repository, separate decision.
- `run.py`, `pilot.py`, and the SEO-audit, alt-text and title-proposal scripts. These
  encode one shop's workflow rather than a general method.
- A hosted or web version.
