from __future__ import annotations

import dataclasses
import datetime
import json
import logging
import re
import unicodedata
import zoneinfo
from typing import TYPE_CHECKING, Any, Optional, Type, TypeVar

import dacite

if TYPE_CHECKING:
    import pathlib

    from .mail import Mail


@dataclasses.dataclass(frozen=True)
class Book:
    title: str
    price: int


@dataclasses.dataclass(frozen=True)
class GrantedCoin:
    label: str
    coin: int


@dataclasses.dataclass(frozen=True)
class Payment:
    date: datetime.datetime
    books: list[Book]
    discount: int
    tax: int
    coin_usage: int
    granted_coins: list[GrantedCoin]

    def subtotal(self) -> int:
        return sum(book.price for book in self.books)

    def total_amount(self) -> int:
        return self.subtotal() + self.discount + self.tax

    def total_payment(self) -> int:
        return self.total_amount() + self.coin_usage


@dataclasses.dataclass(frozen=True)
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
        logger.info("The mail is not a order")
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
    # granted coins
    granted_coins = parse_granted_coins(mail.body, logger)
    # payment
    payment = Payment(
        date=date,
        books=books,
        discount=discount,
        tax=tax,
        coin_usage=coin_usage,
        granted_coins=granted_coins,
    )
    # check: subtotal
    subtotal = parse_price_with_key("Subtotal", mail.body, logger)
    if subtotal != payment.subtotal():
        logger.error(
            "Subtotals are not equal: %d != %d",
            subtotal,
            payment.subtotal(),
        )
    # check: total amount
    total_amount = parse_price_with_key("Total Amount", mail.body, logger)
    if total_amount != payment.total_amount():
        logger.error(
            "Total Amounts not equal: %d != %d",
            total_amount,
            payment.total_amount(),
        )
    # check: total payment
    total_payment = parse_price_with_key(
        "Total Payment",
        mail.body,
        logger,
        pattern="(Payment Total|Total Payment)",
    )
    if total_payment != payment.total_payment():
        logger.error(
            "Total Payments not equal: %d != %d",
            total_payment,
            payment.total_payment(),
        )
    return payment


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


def parse_granted_coins(
    body: str,
    logger: logging.Logger,
) -> list[GrantedCoin]:
    match = re.search(
        r"^■Granted Coin(\(s\))?\s*：\s*(?P<total>[0-9,]+) [Cc]oin(s|\(s\))$\n"
        r"((?P<items1>(^[^\S\n]*\*.+$\n)+)"
        r"|(?P<items2>(^[^\S\n]*[-┗].+$\n)+))?",
        body,
        flags=re.MULTILINE,
    )
    granted_coins: list[GrantedCoin] = []
    if match is None:
        logger.info("No Granted Coins")
        return granted_coins
    total_coins = int(match.group("total").replace(",", ""))
    if match.group("items1"):
        # *Limited Time Coin valid through end of {month}, {year} (JST) : {coin} Coin(s)
        for item_match in re.finditer(
            r"^\s\*Limited Time Coin valid through end of"
            r" (?P<month>[A-Z][a-z]+), (?P<year>[0-9]{4}) \(JST\)"
            r" : (?P<coin>[0-9,]+) Coin\(s\)$",
            match.group("items1"),
            flags=re.MULTILINE,
        ):
            coin = int(item_match.group("coin").replace(",", ""))
            year = int(item_match.group("year"))
            month = MONTH_NAMES.index(item_match.group("month"))
            granted_coins.append(
                GrantedCoin(
                    label=f"limited {year:04d}/{month:02d}",
                    coin=coin,
                )
            )
        # unlimited coin
        unlimited_coin = total_coins - sum(x.coin for x in granted_coins)
        if unlimited_coin > 0:
            granted_coins.insert(
                0,
                GrantedCoin(label="unlimited", coin=unlimited_coin),
            )
    if match.group("items2"):
        # - xxx coins (Valid through end of {month}, {year} JST)  xx%
        # ┗ xxx coins (Valid through end of {month}, {year} JST)  xx%
        # ┗ xxx coin(s) (Valid until the end of {month}, {year} JST)  xx%
        for item_match in re.finditer(
            r"^\s[-┗] (?P<coin>[0-9,]+) coin(s|\(s\))"
            r" \(Valid (through|until the) end of"
            r" (?P<month>[A-Z][a-z]+), (?P<year>[0-9]{4}) JST\)"
            r"\s*(?P<percent>[0-9]+)%$",
            match.group("items2"),
            flags=re.MULTILINE,
        ):
            coin = int(item_match.group("coin").replace(",", ""))
            year = int(item_match.group("year"))
            month = MONTH_NAMES.index(item_match.group("month"))
            percent = int(item_match.group("percent"))
            granted_coins.append(
                GrantedCoin(
                    label=f"limited {year:04d}/{month:02d} {percent}%",
                    coin=coin,
                )
            )
        # check: total
        total = sum(x.coin for x in granted_coins)
        if total != total_coins:
            logger.error(
                "Total granted coins are not equal: %d != %d",
                total_coins,
                total,
            )
    # logger
    if granted_coins:
        logger.info(
            "Granted Coins: %s (total %d)",
            ", ".join(f"{x.coin}({x.label})" for x in granted_coins),
            total_coins,
        )
    else:
        logger.info("No Granted Coins")
    return granted_coins


MONTH_NAMES: list[str] = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def save_orders_as_json(
    path: pathlib.Path,
    orders: list[Payment | Charge],
) -> None:
    with path.open(mode="w", encoding="utf-8") as file:
        json.dump(
            [dataclasses.asdict(order) for order in orders],
            file,
            ensure_ascii=False,
            cls=OrdersJSONEncoder,
            indent=2,
        )
        file.write("\n")


class OrdersJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        return super().default(o)


def load_orders_from_json(
    path: pathlib.Path,
) -> list[Payment | Charge]:
    with path.open(mode="r", encoding="utf-8") as file:
        orders = json.load(file)
    return [to_order(order) for order in orders]


def to_order(data: Any) -> Payment | Charge:
    if "books" in data:
        return to_order_impl(Payment, data)
    return to_order_impl(Charge, data)


OrderT = TypeVar("OrderT")


def to_order_impl(
    data_class: Type[OrderT],
    data: dict,
) -> OrderT:
    return dacite.from_dict(
        data_class=data_class,
        data=data,
        config=dacite.Config(
            type_hooks={
                datetime.datetime: datetime.datetime.fromisoformat,
            },
            strict=True,
        ),
    )


def normalize_title(title: str) -> str:
    # replace
    title = title.translate(REPLACE_TABLE)
    # unicode
    title = unicodedata.normalize("NFKC", title)
    # hull width -> half width
    title = title.translate(FULLWIDTH_TO_HALFWIDTH_TABLE)
    # remove【...】
    title = re.sub(r"【[^【】]*(電子|特典|%OFF)[^【】]*】", "", title)
    title = re.sub(r"【(期間限定)?([^【】]+セット)】", r" \g<2>", title)
    title = title.strip()
    # '(N)' -> ' N'
    title = re.sub(r"\(([0-9]+)\)$", r" \g<1>", title)
    # ': N' -> ' N'
    title = re.sub(r": ([0-9]+)$", r" \g<1>", title)
    # '第?N巻' -> 'N'
    title = re.sub(r"第?([0-9]+)巻$", r"\g<1>", title)
    # consective spaces
    title = re.sub(r"\s+", " ", title)
    # ... -> …
    title = re.sub(r"\.{3}", "…", title)
    return title


# 〜(U+301C: wave dash) -> ～(U+FF5E: fullwidth tilda)
REPLACE_TABLE = str.maketrans(
    "\u301c",
    "\uff5e",
)


FULLWIDTH_TO_HALFWIDTH_TABLE = str.maketrans(
    "".join(chr(ord("！") + i) for i in range(94)) + "　・「」",
    "".join(chr(ord("!") + i) for i in range(94)) + " ･｢｣",
)
