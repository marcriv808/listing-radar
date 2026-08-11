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

- [ ] Read Etsy's current API terms of use and developer policy. This tool
      encourages third parties to use their own keys; confirm that distributing
      an open-source client is permitted and that nothing in the README implies
      Etsy endorsement.
- [ ] Read Etsy's trademark policy. The repository is named `listing-radar`
      specifically to keep the mark out of the name; confirm that describing it
      as "for Etsy sellers" is acceptable use.
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
- [ ] Set the repository homepage field to `https://listingresearchos.com`.
- [ ] Set the repository description to "Demand research for Etsy sellers, from
      public listing data".
