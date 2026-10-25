Make a page that explains our three hosting plans' monthly cost to my team. The plans and their prices are in `data/plans.csv`, and our expected traffic is in `docs/traffic.md`. Save it as `reports/hosting.html`. It must work when opened from disk with the network off. Deliver one HTML file with no companion files. Keep the scripts and styles needed for the report inline. Optional network libraries are allowed only when the required report works without them.

I will check the page through this small interface, so please keep to it:

- two inputs, `<input type="number">`, shown, enabled and editable: one with the id `requests` (millions of requests a month) and one with the id `storage` (GB stored), both starting at our expected traffic;
- each plan's monthly total, in dollars to the cent, as the text of an element with the id `total-<plan>`, where `<plan>` is the plan's name in lower case (`total-starter`, `total-team`, `total-metered`). The element holds only that total, and it follows the two inputs.
- If recalculation needs a button, give it the id `calculate`; the check clicks it after changing both inputs.
