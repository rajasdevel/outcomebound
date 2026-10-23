"""A book in two currencies, written to a data folder, for the hidden tests of
v2-lh-stale-handoff."""

import json
from pathlib import Path


def data_folder(folder, rates="base,quote,rate\nEUR,CHF,0.9350\n", overrides=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    accounts = [
        {
            "id": "e",
            "owner": "hidden",
            "currency": "EUR",
            "balance": 10000,
            "limit": 0,
            "frozen": False,
        },
        {
            "id": "c",
            "owner": "hidden",
            "currency": "CHF",
            "balance": 0,
            "limit": 0,
            "frozen": False,
        },
    ]
    (folder / "accounts.json").write_text(json.dumps(accounts), encoding="utf-8")
    (folder / "journal.jsonl").write_text("", encoding="utf-8")
    (folder / "rates.csv").write_text(rates, encoding="utf-8")
    if overrides is not None:
        (folder / "overrides.csv").write_text(overrides, encoding="utf-8")
    return folder
