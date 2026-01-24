from __future__ import annotations

import dataclasses
import datetime
import json
import sys
from typing import Optional, TextIO

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


def output_markdown_table(
    orders: list[Payment | Charge],
    *,
    stream: TextIO = sys.stdout,
) -> None:
    # orders to rows
    rows: list[MarkdownTableRow] = []
    for order in orders:
        match order:
            case Payment():
                rows.extend(payment_to_markdown_rows(order))
            case Charge():
                rows.extend(charge_to_markdown_rows(order))
    # output
    stream.write("|日|時刻|店|商品|価格|\n")
    stream.write("|--:|--:|:--|:--|--:|\n")
    for row in rows:
        stream.write(row.to_string())
        stream.write("\n")


@dataclasses.dataclass(frozen=True)
class MarkdownTableRow:
    date: Optional[datetime.datetime]
    item: str
    price: int

    def to_string(self) -> str:
        columns: list[str] = [""]
        store = "BOOK☆WALKER"
        # YYYY/MM/DD, hh:mm, store
        if self.date is not None:
            columns.append(self.date.strftime("%Y/%m/%d"))
            columns.append(self.date.strftime("%H:%M"))
            columns.append(store)
        else:
            columns.extend(["", "", ""])
        # item, price
        columns.append(self.item)
        columns.append(str(self.price))
        columns.append("")
        return "|".join(columns)


def payment_to_markdown_rows(payment: Payment) -> list[MarkdownTableRow]:
    rows: list[MarkdownTableRow] = []
    # books
    for i, book in enumerate(payment.books):
        rows.append(
            MarkdownTableRow(
                date=payment.date if i == 0 else None,
                item=book.title.translate(MARKDOWN_ESCAPE_TABLE),
                price=book.price,
            )
        )
    # discount
    if payment.discount != 0:
        rows.append(
            MarkdownTableRow(
                date=None,
                item="クーポン割引",
                price=payment.discount,
            )
        )
    # tax
    if payment.tax != 0:
        rows.append(
            MarkdownTableRow(
                date=None,
                item="消費税",
                price=payment.tax,
            )
        )
    # coin usage
    if payment.coin_usage != 0:
        rows.append(
            MarkdownTableRow(
                date=None,
                item="コイン利用",
                price=payment.coin_usage,
            )
        )
    return rows


def charge_to_markdown_rows(charge: Charge) -> list[MarkdownTableRow]:
    rows: list[MarkdownTableRow] = []
    # coin
    item = charge.item
    if charge.amount > 1:
        item += f" x{charge.amount}"
    rows.append(
        MarkdownTableRow(
            date=charge.date,
            item=item,
            price=charge.coin,
        )
    )
    return rows


MARKDOWN_ESCAPE_TABLE = str.maketrans(dict((x, rf"\{x}") for x in r"*\_~"))
