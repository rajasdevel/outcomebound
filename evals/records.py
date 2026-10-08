"""One internal command record; JSON serialization remains the existing three-value array."""

from typing import NamedTuple


class Command(NamedTuple):
    command: str
    status: str
    cwd: str
