# Pre-publication checklist

Do not push this repository publicly until every box is checked.

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
