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


def output_gnucash(
    orders: list[Payment | Charge],
    *,
    stream: TextIO = sys.stdout,
) -> None:
    # to records
    records: list[GnucashRecord] = []
    for order in orders:
        match order:
            case Payment():
                records.append(payment_to_gnucash_record(order))
            case Charge():
                records.append(charge_to_gnucash_record(order))
    # write
    last_number: Optional[str] = None
    for record in records:
        date = record.date.strftime("%Y-%m-%d")
        number = record.date.strftime("%Y%m%d%H%M")
        if last_number == number:
            number += "#"
        last_number = number
        for i, row in enumerate(record.rows):
            if i == 0:
                stream.write(f"{date},{number},{record.description},")
            else:
                stream.write(",,,")
            stream.write(f"{row.account},{row.value}\n")


@dataclasses.dataclass(frozen=True)
class GnucashRow:
    account: str
    value: int


@dataclasses.dataclass(frozen=True)
class GnucashRecord:
    date: datetime.datetime
    description: str
    rows: list[GnucashRow]


def payment_to_gnucash_record(payment: Payment) -> GnucashRecord:
    rows: list[GnucashRow] = []
    # book
    rows.append(GnucashRow(account="book", value=payment.total_amount()))
    # coin
    rows.append(GnucashRow(account="coin", value=payment.total_granted_coin()))
    # payment
    total_payment = payment.total_payment()
    if total_payment != 0:
        rows.append(GnucashRow(account="payment", value=total_payment))
    # coin usage
    if payment.coin_usage != 0:
        rows.append(GnucashRow(account="coin", value=payment.coin_usage))
    # granted coin
    granted_coins = [granted_coin.coin for granted_coin in payment.granted_coins]
    for coin in granted_coins or [0]:
        rows.append(GnucashRow(account="granted coin", value=-coin))
    return GnucashRecord(
        date=payment.date,
        description="BOOK☆WALKER",
        rows=rows,
    )


def charge_to_gnucash_record(charge: Charge) -> GnucashRecord:
    rows: list[GnucashRow] = []
    # coin
    rows.append(GnucashRow(account="coin", value=charge.coin + charge.bonus_coin))
    # payment
    rows.append(GnucashRow(account="payment", value=charge.coin))
    # granted coin
    rows.append(GnucashRow(account="granted coin", value=charge.bonus_coin))
    return GnucashRecord(
        date=charge.date,
        description="BOOK☆WALKER コイン購入",
        rows=rows,
    )
