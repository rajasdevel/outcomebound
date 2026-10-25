The page is `reports/hosting.html`; open it from disk, offline. It has the two inputs, `requests` (millions a month) and `storage` (GB), starting at the expected 2.4 million and 80 GB from `docs/traffic.md`, and each plan's monthly total, to the cent, in `total-starter`, `total-team` and `total-metered`. The prices are those of `data/plans.csv`, held in the page; it loads nothing from the network.

At the expected traffic: Starter $37.30, Metered $41.60, Team $54.70. I checked those three by hand against the CSV.

It also draws a chart with Chart.js.
