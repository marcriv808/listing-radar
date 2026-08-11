# listing-radar

Demand research for Etsy sellers, from public listing data. Read-only — it never
writes to your shop.

Built by a solo seller whose own shop scores 91 on every listing-hygiene check
and has made five sales. That is exactly why this measures demand instead of
grading your listings.

## What it answers

```bash
listing-radar demand "clinical supervision hours tracker"
listing-radar traction shop:12345678
listing-radar rank "estate executor checklist" --listing 4514299502
listing-radar niche "budget spreadsheet"
```

| Command | Question |
|---|---|
| `demand` | Is anyone actually searching for this? |
| `traction` | How well is this competitor really doing? |
| `rank` | Why does my listing get no views? |
| `niche` | Is this worth building? |

## How it works

Etsy publishes no search-volume API. But `/v3/application/listings/active`
returns `views` and `num_favorers` for **any** active listing with only an app
key, and every listing carries an original creation date. So demand is inferable
from the traction of whoever currently ranks:

```
demand(phrase)      = median views/day of the listings ranking for it
winnable(phrase)    = min(1, 400 / median age in days of the top rankers)
opportunity(phrase) = demand / log10(competition + 10) * winnable
```

A phrase whose top rankers earn roughly zero views a day has no traffic, however
targeted it feels.

**These formulas are unvalidated heuristics.** They are the ones the author uses,
carried over unchanged. Treat the output as a ranking signal, not a measurement.

## Why `rank` has four answers, not a number

Zero views has different causes and each has a different fix:

- **TOP100** — it ranks; if views are low the problem is the listing
- **BURIED** — ranks too deep to be found; the gap is authority, not wording
- **ABSENT** — not in the results at all; not competing for that phrase
- **NO MARKET** — too few listings match; an empty room, not a cheap one

`/listings/active?keywords=` is the API's relevance search, not buyer-facing
Etsy ranking. Position is ordinal evidence only, and the command says so on
every run.

## Setup

You need your own Etsy app key. Registration and approval take a few days and no
tool can shortcut that.

```bash
export ETSY_KEYSTRING=your_keystring
export ETSY_SHARED_SECRET=your_shared_secret
pip install listing-radar
```

Both halves are required. Etsy's `x-api-key` header value is
`keystring:shared_secret`; a bare keystring returns 403.

Responses are cached to `~/.cache/listing-radar` for seven days. Rate limits are
per key, so this is a requirement rather than an optimisation.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | other client error (a bad request, an unrecognised response, etc.) |
| `2` | malformed invocation — argparse's own exit code for a bad flag or argument, e.g. a non-numeric `--listing` |
| `3` | `QuotaExhausted` — Etsy's daily quota is gone; cached results still work |
| `4` | `MissingCredentials` — `ETSY_KEYSTRING`/`ETSY_SHARED_SECRET` not set |

`2` is deliberately not shared with any of this tool's own errors: it is
argparse's code, raised before a client is ever constructed, so a script can
tell "you typo'd an argument" apart from every error this tool raises itself.

## What this replaces

eRank, Marmalade, and Alura charge roughly $20–50 a month for demand estimates.
This infers them from the same public data, for free.

## Related

I also build finished tools for solo sellers at
[listingresearchos.com](https://listingresearchos.com) — one-time purchase,
no subscription. The difference is that those are products for running a shop;
this is the research layer, and it is free.

## License

MIT.
