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
- [ ] Run a secret scan over the full history, not just the working tree:
      `gitleaks detect --source . --log-opts="--all"`
- [ ] Confirm no fixture contains a real shop id, listing id, or shop name.
- [ ] Confirm `.gitignore` covers `.env`, `cache/`, `data/`, `*.json` artifacts.
- [ ] Confirm `python3 -m pytest -q` passes from a clean clone.
- [ ] Confirm the read-only guarantee: `python3 -m pytest tests/test_client.py::test_source_tree_contains_no_write_calls`
- [ ] Set the repository homepage field to `https://listingresearchos.com`.
- [ ] Set the repository description to "Demand research for Etsy sellers, from
      public listing data".
