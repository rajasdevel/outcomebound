I added `query_params(url)` to `links.py`. It uses `urllib.parse.parse_qs` on the query that `urlparse` returns, with `keep_blank_values=True`. The standard library splits on `&`, keeps repeated names in order, decodes `%XX` and `+`, and leaves out the fragment, so I decoded nothing by hand. The project allows only the standard library, and I installed nothing.

I added four tests to `test_links.py` for repeated names, escapes and `+`, a name with no value, and a fragment or no query. `python3 -B -m unittest` passes. I changed no other file.
