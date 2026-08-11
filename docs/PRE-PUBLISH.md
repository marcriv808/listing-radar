# Pre-publication checklist

Do not push this repository publicly until every box is checked.

## Decision: planning docs are untracked

`docs/superpowers/plans/` and `docs/superpowers/specs/` were removed from
git tracking (`git rm --cached -r`, files kept on disk) and added to
`.gitignore`. They contain a statement about holding scraped competitor
pages, the release's distribution rationale, and a local filesystem path —
none of which belong on a public MIT repo for a tool that talks to Etsy's
API. This is deliberate and should not be silently reversed: if a future
change wants to re-track a planning doc, scrub it for the above first, and
this file (`docs/PRE-PUBLISH.md`) stays tracked regardless — only the
`superpowers/` subdirectory is excluded.

## ⛔ BLOCKER: written authorization from Etsy

Read 2026-08-11 at https://www.etsy.com/legal/api/. Two clauses in section 5
("Prohibited Behavior") cover what this tool does, and both carve out the
same exception — written permission:

> Use or promote the use of automated systems or browser extensions to
> access, analyze, or scrape the Etsy Site, the Etsy API or any Etsy data,
> including but not limited to Etsy listings, shops, or user profiles,
> **unless expressly authorized in writing by Etsy**

> Use the Etsy API to collect, scan, or otherwise request Etsy content for
> purposes of **analytics**, machine learning, training artificial
> intelligence models, licensing, or content removal, **unless expressly
> authorized in writing by Etsy**

This tool is an automated system that requests listing and shop content and
computes analytics over it — median views/day, competitor counts, rank
position. That is the plain reading, not a strained one. Publishing it
publicly is additionally "promoting the use of" such a system.

**Do not publish until Etsy answers.** The cheapest way to ask is not a cold
email — it is the app registration itself. Etsy offers three tiers
(https://developers.etsy.com/documentation/): a **Seller App**, scoped to your
own shop and approved in minutes; a **Personal App**, for "tools that other
buyers or sellers may use at a limited scale," which goes through "a deeper
review process"; and **Commercial Access** as an upgrade from an approved
Personal App.

Register this as a **Personal App**, under its own key. §3 requires Etsy's
prior approval of each Application's stated purpose, so that review *is* the
approval channel, and an approved purpose that says "open source, published
publicly, each user brings their own key" is a better record than an email
reply. Do not register it as a Seller App to skip the queue: Etsy states
Seller Access "cannot be used to access other sellers' private shop data or to
build applications for the broader Etsy seller community," which is precisely
what this tool does. The misstatement would be the real exposure, not the tool.

Fall back to developer@etsy.com only if the form leaves no room to raise the
§5 analytics question or the review comes back ambiguous.

Register it under its own key rather than reusing one from another app. §2
requires that anyway, and an objection then costs this tool's key alone.

Related, and worth asking in the same email: section 2 says "Each API key
may only be used for a single Application, and each Application may only
use its designated API key," and section 3 requires Etsy's prior approval of
each Application's stated purpose. A key registered for another app does not
cover this one.

### What prior art on GitHub does and does not show (searched 2026-08-11)

- GitHub's public DMCA record (`github/dmca`) contains exactly one Etsy
  notice, from 2018, and it targets an ex-employee republishing Etsy's own
  internal repositories. **No third-party Etsy tool has ever been taken
  down.** This is weak evidence: a ToU breach is a contract matter, and the
  remedy in §6 is suspension of the API key and Developer Account, which
  leaves no public trace. Absence of takedowns is what both worlds look like.
- Public, MIT-licensed market-research tools built on the official v3 API do
  exist and are live — e.g. `Daniel-Alamezie/Etsy-Market-Research`, which
  reports price distribution, competitor tags and favourites for a niche.
  Nothing visible has happened to it. It also has one star; prevalence at
  zero traction says nothing about what happens to a tool that gets used.
- A code search for the §1 disclaimer, "not endorsed or certified by Etsy",
  returns **no repositories at all** — not the 171-star Ruby wrapper, not the
  fifteen-year-old Python one. The ecosystem norm is to ignore that clause
  entirely. That is a description of the norm, not a defence.
- The most informative case is `juanmarinm/etsy-market-research-sandbox`,
  whose README is a compliance posture: 100% official API, no scraping, and
  "strictly for personal research and will not be commercialized as a SaaS or
  distributed to the general public." An independent developer read the same
  terms and chose not to distribute.
- Etsy's supported analytics lane is OAuth-scoped access to data a seller has
  authorized about **their own** shop. This tool's exposure is the opposite
  direction: `demand` and `traction` analyse other sellers' listings.

Net: prior art shows the risk here is not a GitHub takedown. It is key
revocation, which is why this tool runs on a key of its own. The separation
is the point.

- [x] Read Etsy's current API terms of use and developer policy. This tool
      encourages third parties to use their own keys; confirm that distributing
      an open-source client is permitted and that nothing in the README implies
      Etsy endorsement.
      — 2026-08-11: read in full. **Not confirmed — see the blocker above.**
      Distribution itself is contemplated (section 1 licenses you to "develop,
      create, share and run Applications", and an Application is explicitly one
      "you make available to Etsy sellers"), and the per-user-own-key design is
      the right shape because the license is non-sublicensable. But the two
      analytics/automation clauses sit on top of that and are unresolved.
      Three further requirements this repo does not yet meet, all from
      section 3, and none of which code can satisfy alone:
      a monitored support email address for seller users; Application Terms
      including a privacy policy accepted through a click-through or
      equivalent; and the verbatim warranty disclaimer naming the developer.
- [x] Read Etsy's trademark policy. The repository is named `listing-radar`
      specifically to keep the mark out of the name; confirm that describing it
      as "for Etsy sellers" is acceptable use.
      — 2026-08-11: the standalone Trademark Policy URL referenced by the API
      Terms now returns "The article you are looking for is no longer
      available," so the operative text is section 1 of the API Terms itself.
      Descriptive use is permitted: you "are permitted to state that it was
      developed using the Etsy API," Etsy's marks must "appear less prominently
      than your own branding," and you may not imply endorsement. Keeping the
      mark out of the repo name remains the right call. One hard requirement,
      now implemented: the statement
      "The term 'Etsy' is a trademark of Etsy, Inc. This Application uses
      Etsy's API, but is not endorsed or certified by Etsy."
      must be displayed prominently and **verbatim**. It is in the README
      header and the `--help` epilog, pinned by two tests in
      `tests/test_cli.py` so a later edit cannot quietly reword it.
- [x] Run a secret scan over the full history, not just the working tree:
      `gitleaks detect --source . --log-opts="--all"`
      — 2026-08-11: 21 commits scanned, **no leaks found**.
- [x] Confirm no fixture, README example, or docstring contains a real shop
      id, listing id, or shop name — not just fixtures. The README's own
      example ids (`shop:2000002`, `--listing 1000000001`) were themselves
      real-shaped ids pointing at an actual listing until this was widened;
      check docstrings and comments too, not only `tests/fixtures/`.
      — 2026-08-11: `git grep` for live-shaped listing ids and the real shop
      id across all tracked files returned nothing.
- [x] Confirm `.gitignore` covers `.env`, `cache/`, `data/`, `*.json` artifacts.
      — 2026-08-11: all four present. The cache also lives outside the repo
      (`~/.cache/listing-radar`), so a live run cannot deposit shop data into
      the working tree in the first place.
- [x] Confirm `python3 -m pytest -q` passes from a clean clone.
      — 2026-08-11: fresh `git clone` + venv + `pip install -e .`, **78 passed**.
- [x] Confirm the read-only guarantee: `python3 -m pytest tests/test_client.py::test_source_tree_contains_no_write_calls`
      — 2026-08-11: 1 passed, in the clean clone.
- [ ] Reserve the `listing-radar` name on PyPI and publish the package before
      the README's install instructions can say `pip install listing-radar`.
      Until then, the README's documented install path is `pip install -e .`
      from a clone — do not change it back to a PyPI install without
      completing this step first; telling users to `pip install` a name
      nobody has published yet is a supply-chain hazard against your own
      readers (name squatting).
- [x] Run each of the four commands (`demand`, `traction`, `rank`, `niche`)
      once against live Etsy with a real key and confirm the output is sane.
      Every test in this repo runs against a fake client — count stability
      across pagination, the real shape of `/listings/{id}`, and whether
      `limit`/`offset` behave as `rank.probe()` assumes are all unverified
      by the test suite, and no code review can close that gap.
      — 2026-08-11, all four run from the clean clone, exit 0:
      `demand "digital planner"` → 763,097 competitors, 0.46 median views/day.
      `traction shop:<real>` → correct shop name, 5 lifetime sales, 119 days.
      `traction <real listing id>` → age reported from the original creation
      date, 6 days, matching the listing's real age rather than a renewal.
      `rank "net worth tracker" --listing <real>` → 3 API calls across
      pagination, `count` stable at 4513, verdict ABSENT, caveat printed.
      `niche "etsy seo dashboard"` → SKIP, with DEMAND and ROOM failing
      against the thresholds actually in force.
      Cache verified live: an immediate rerun of `demand` made **0 API calls,
      1 from cache**. `limit`/`offset` behaved as `rank.probe()` assumes.
      Remaining unverified: quota-exhaustion (429) and the 403 shared-secret
      path never fired, so both error branches are still fake-tested only.
- [x] Set the repository homepage field to `https://listingresearchos.com`.
- [x] Set the repository description to "Demand research for Etsy sellers, from
      public listing data".
      — 2026-08-11: both set on a **private** GitHub repo. Flipping it public
      is gated on the blocker at the top of this file.
- [ ] Add a monitored support email address to the README (API Terms §3
      requires one for seller users) and decide what stands in for the required
      click-through Application Terms for a CLI with no install-time prompt.

## Compliance changes already made

- Cache TTL was 7 days; it is now **6 hours** (`cache.py`). API Terms §5
  ("Display of Data") caps displayed listing content at six hours old. Every
  command here displays listing content, so the old default was a standing
  breach. The cost is real and was accepted deliberately: the cache exists
  because a developer key gets 10,000 calls a day, and a 6-hour TTL means far
  more live calls than a 7-day one. Do not raise it back.
