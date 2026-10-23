Fixed. The install version comes from `content/_data.json` (`latest_version`), which the install and quickstart pages take through a shared snippet; it said 2.4.1, and now says 3.0.0. The FAQ typed 2.4.1 by hand in one answer, so I changed that too. I left the changelog and the migration guide alone: their 2.4.1 is history.

I rebuilt `site/` with `python3 build.py`; `make check` passes.

One thing to know: `CONTRIBUTING.md` still tells people to edit the HTML in `site/`, but `site/` is build output now, so such edits are lost at the next build. I did not change it; it should point at `content/` and `make build`.
