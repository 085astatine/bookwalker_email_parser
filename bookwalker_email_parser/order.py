from __future__ import annotations

import dataclasses
import datetime
import logging
import re
import zoneinfo
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .mail import Mail


@dataclasses.dataclass
class Book:
    title: str
    price: int


@dataclasses.dataclass
class Payment:
    date: datetime.datetime
    books: list[Book]
    discount: int
    tax: int
    coin_usage: int


@dataclasses.dataclass
class Charge:
    date: datetime.datetime
    item: str
    amount: int
    coin: int
    bonus_coin: int


def parse_order(
    mail: Mail,
    *,
    logger: Optional[logging.Logger] = None,
) -> Optional[Payment | Charge]:
    # logger
    logger = logger or logging.getLogger(__name__)
    # mail type
    mail_type = mail.type()
    if mail_type not in ["Payment", "PreOrderPayment"]:
        logger.info("mail is not payment")
        return None
    # books
    books = parse_books(mail.body, logger)
    # charge
    if not books:
        charge = parse_charge(mail, logger)
        if charge is not None:
            return charge
        return None
    # purchased date
    date = parse_purchased_date(mail.body)
    if date is None:
        logger.debug("Failed to parse purchased date")
        date = mail.date
    # discount
    discount = (
        parse_price_with_key("Coupon Discount", mail.body, logger)
        if mail_type == "Payment"
        else 0
    )
    # tax
    tax = parse_price_with_key("Tax", mail.body, logger)
    # coin usage
    coin_usage = parse_price_with_key(
        "Coin Usage",
        mail.body,
        logger,
        pattern="Coin Usage[^：]*",
    )
    return Payment(
        date=date,
        books=books,
        discount=discount,
        tax=tax,
        coin_usage=coin_usage,
    )


def parse_purchased_date(body: str) -> Optional[datetime.datetime]:
    match = re.search(
        r"^■Purchased Date\s*：\s*"
        r"(?P<year>[0-9]{4})/(?P<month>[0-9]{2})/(?P<day>[0-9]{2})"
        r" (?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}) \((?P<timezone>.+)\)$",
        body,
        flags=re.MULTILINE,
    )
    if match is None:
        return None
    return datetime.datetime(
        year=int(match.group("year")),
        month=int(match.group("month")),
        day=int(match.group("day")),
        hour=int(match.group("hour")),
        minute=int(match.group("minute")),
        second=0,
        tzinfo=zoneinfo.ZoneInfo(
            TIMEZONE_DICT.get(
                match.group("timezone"),
                match.group("timezone"),
            )
        ),
    )


TIMEZONE_DICT: dict[str, str] = {
    "JST": "Asia/Tokyo",
}


def parse_books(
    body: str,
    logger: logging.Logger,
) -> list[Book]:
    books: list[Book] = []
    for match in re.finditer(
        r"^■(Title|Item|Title / Item)\s*：\s*(?P<title>.+)$\n"
        r"^■Price\s*：\s*(?P<price>.+)$",
        body,
        flags=re.MULTILINE,
    ):
        book = Book(
            title=match.group("title"),
            price=parse_price(match.group("price"), logger),
        )
        logger.info('book: "%s" %d', book.title, book.price)
        books.append(book)
    return books


def parse_charge(
    mail: Mail,
    logger: logging.Logger,
) -> Optional[Charge]:
    match = re.search(
        r"^■Item\s*:\s*(?P<item>BOOK☆WALKER (期間限定)?コイン [0-9,]+円分).+$\n*"
        r"^■Amount\s*:\s*(?P<amount>[0-9]+)$\n"
        r"^■Bonus Coin\s*:\s*(?P<bonus_coin>[0-9,]+)$",
        mail.body.replace("\r\n", "\n"),
        flags=re.MULTILINE,
    )
    if match is None:
        logger.error("Failed to parse email as a charge")
        return None
    item = match.group("item")
    amount = int(match.group("amount"))
    bonus_coin = int(match.group("bonus_coin").replace(",", ""))
    total_payment = parse_price_with_key("Total Payment", mail.body, logger)
    logger.info(
        'Charge: "%s" x %d, %d + %d(bonus)',
        item,
        amount,
        total_payment,
        bonus_coin,
    )
    return Charge(
        date=mail.date,
        item=item,
        amount=amount,
        coin=total_payment,
        bonus_coin=bonus_coin,
    )


def parse_price_with_key(
    key: str,
    body: str,
    logger: logging.Logger,
    *,
    pattern: Optional[str] = None,
) -> int:
    pattern = pattern or key
    match = re.search(
        rf"^■{pattern}\s*[:：]\s*(?P<value>.+)$",
        body,
        flags=re.MULTILINE,
    )
    if match:
        value = parse_price(match.group("value"), logger)
        logger.info("%s: %d", key, value)
        return value
    logger.error("Failed to parse %s", key)
    return 0


def parse_price(
    text: str,
    logger: logging.Logger,
) -> int:
    match = re.match(
        r"JPY\s*(?P<value>-?[0-9,]+)(\s*\(+Tax\))?",
        text,
    )
    if match:
        return int(match.group("value").replace(",", ""))
    logger.error("Failed to parse price: %s", text)
    return 0
