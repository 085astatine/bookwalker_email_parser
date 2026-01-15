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


def parse_payment(
    mail: Mail,
    *,
    logger: Optional[logging.Logger] = None,
) -> Optional[Payment]:
    # logger
    logger = logger or logging.getLogger(__name__)
    # mail type
    if mail.type() not in ["Payment", "PreOrderPayment"]:
        logger.info("mail is not payment")
        return None
    # purchased date
    date = parse_purchased_date(mail.body)
    if date is None:
        logger.debug("Failed to parse purchased date")
        date = mail.date
    # books
    books = parse_books(mail.body, logger)
    # discount
    discount = parse_discount(mail.body, logger)
    return Payment(
        date=date,
        books=books,
        discount=discount,
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


def parse_discount(
    body: str,
    logger: logging.Logger,
) -> int:
    match = re.search(
        r"^■Coupon Discount\s*：\s*(?P<discount>.+)$",
        body,
        flags=re.MULTILINE,
    )
    if match:
        value = parse_price(match.group("discount"), logger)
        logger.info("discount: %d", value)
        return value
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
