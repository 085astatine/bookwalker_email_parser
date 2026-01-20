from __future__ import annotations

import dataclasses
import json
import sys
from typing import TextIO

from .order import Charge, OrdersJSONEncoder, Payment


def output_json(
    orders: list[Payment | Charge],
    *,
    stream: TextIO = sys.stdout,
) -> None:
    json.dump(
        [dataclasses.asdict(order) for order in orders],
        stream,
        ensure_ascii=False,
        cls=OrdersJSONEncoder,
        indent=2,
    )
    stream.write("\n")


def output_titles(
    orders: list[Payment | Charge],
    *,
    stream: TextIO = sys.stdout,
) -> None:
    titles: list[str] = []
    for order in orders:
        match order:
            case Payment(books=books):
                titles.extend(book.title for book in books)
    # sort titles
    titles.sort()
    # output
    for title in titles:
        stream.write(f"{title}\n")
