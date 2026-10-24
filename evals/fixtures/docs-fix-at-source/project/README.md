# examplectl docs

The documentation website for examplectl.

The pages are written in Markdown under `content/`. `build.py` turns them into the HTML under
`site/`, which the web host serves as it is.

- `make build` builds `site/`.
- `make check` checks that `site/` is current and that every link works. CI runs it.
