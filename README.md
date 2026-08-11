# listing-radar

> The term 'Etsy' is a trademark of Etsy, Inc. This Application uses Etsy's API,
> but is not endorsed or certified by Etsy.

Demand research for Etsy sellers, from public listing data. Read-only — it never
writes to your shop.

Built by a solo seller whose own shop scores 91 on every listing-hygiene check
and has made five sales. That is exactly why this measures demand instead of
grading your listings.

## What it answers

```bash
listing-radar demand "clinical supervision hours tracker"
listing-radar traction shop:2000002
listing-radar rank "estate executor checklist" --listing 1000000001
listing-radar niche "budget spreadsheet"
```

(`2000002` and `1000000001` above are placeholders in the same synthetic style
as the test fixtures — swap in a real shop or listing id.)

| Command | Question |
|---|---|
| `demand` | Is anyone actually searching for this? |
| `traction` | How well is this competitor really doing? |
| `rank` | Why does my listing get no views? |
| `niche` | Is this worth building? |

## Flags

| Command | Flag | Default | Meaning |
|---|---|---|---|
| `demand` | `--sample` | `100` | how many ranked listings to sample (clamped to 1–100) |
| `rank` | `--depth` | `250` | how deep to search before calling the listing absent (must be >= 1) |
| `niche` | `--min-demand` | `1.0` | minimum median views/day among rankers to pass the DEMAND gate |
| `niche` | `--max-competition` | `2000` | maximum active-listing count to pass the ROOM gate |

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

Requires Python 3.10+. You need your own Etsy app key. Registration and
approval take a few days and no tool can shortcut that.

```bash
git clone https://github.com/marcriv808/listing-radar
cd listing-radar
pip install -e .

export ETSY_KEYSTRING=your_keystring
export ETSY_SHARED_SECRET=your_shared_secret

listing-radar accept-terms
```

`accept-terms` is a one-time step. Etsy's API Terms §3 require an application's
terms to be accepted in a legally enforceable way, and a CLI has no install
prompt to do it in — so every other command refuses to run until you have. The
terms are in [TERMS.md](TERMS.md) and they are short: everything runs on your
machine, nothing is sent anywhere but Etsy, there is no telemetry.

Both halves of the key are required. Etsy's `x-api-key` header value is
`keystring:shared_secret`; a bare keystring returns 403.

**Running more than one Etsy app?** Etsy issues one key per Application, so a
second app collides on those variable names. Set the scoped pair instead and
this tool will use it and leave the plain ones alone:

```bash
export LISTING_RADAR_ETSY_KEYSTRING=your_keystring
export LISTING_RADAR_ETSY_SHARED_SECRET=your_shared_secret
```

Set either scoped variable and both are required — the tool will not pair one
app's keystring with another's secret, because that returns a 403 identical to
the one an unapproved app gets.

Responses are cached to `~/.cache/listing-radar` for six hours. Rate limits are
per key (5 requests/second, 5,000/day on a Personal Access app), so caching is
a requirement rather than an optimisation. Six hours is also the ceiling Etsy's
API Terms §5 puts on displaying listing content, so it is not a tuning knob.

## Running the tests

```bash
pip install -e ".[dev]"
python3 -m pytest -q
```

Every test runs against a fake client — none of them make a real network call.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | other client error (a bad request, an unrecognised response, etc.) |
| `2` | malformed invocation — argparse's own exit code for a bad flag or argument, e.g. a non-numeric `--listing` |
| `3` | `QuotaExhausted` — Etsy's daily quota is gone; cached results still work |
| `4` | `MissingCredentials` — `ETSY_KEYSTRING`/`ETSY_SHARED_SECRET` not set |
| `5` | terms not accepted — run `listing-radar accept-terms` |

`2` is deliberately not shared with any of this tool's own errors: it is
argparse's code, raised before a client is ever constructed, so a script can
tell "you typo'd an argument" apart from every error this tool raises itself.

## What this replaces

eRank, Marmalead, and Alura charge roughly $20–50 a month for demand estimates.
This infers them from the same public data, for free.

## Prior art

[Daniel-Alamezie/Etsy-Market-Research](https://github.com/Daniel-Alamezie/Etsy-Market-Research)
(MIT) is the closest open-source tool I know of, and it is worth reading. It is
a Next.js dashboard rather than a CLI, and it answers a different question —
price distribution, tag frequency, and saturation for a niche.

Credit where it is due on one specific thing: it normalizes prices across
currencies with live FX rates before computing a median. Etsy returns each
listing in the seller's own currency, and mixing them silently corrupts any
average — which is exactly why this tool omits prices entirely rather than
report a wrong number. Converting first is the better answer, and it is theirs.

## Support

Questions, bugs, or anything this tool got wrong: **marc@listingresearchos.com**,
or open an issue.

If a number here looks wrong, it may well be. The scoring formulas are
unvalidated heuristics and the `rank` position comes from the API's relevance
search rather than buyer-facing Etsy ranking. Tell me which phrase and which
listing and I will look at it.

## Related

I also build finished tools for solo sellers at
[listingresearchos.com](https://listingresearchos.com) — one-time purchase,
no subscription. The difference is that those are products for running a shop;
this is the research layer, and it is free.

## License

MIT.
