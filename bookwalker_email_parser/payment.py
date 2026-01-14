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
class Payment:
    date: datetime.datetime


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
    return Payment(
        date=date,
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
