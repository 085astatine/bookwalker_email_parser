from __future__ import annotations

import dataclasses
import email.parser
import email.policy
import logging
from typing import TYPE_CHECKING, Literal, Optional, Self, cast

if TYPE_CHECKING:
    import datetime
    import email.headerregistry
    import email.message
    import pathlib


MailType = Literal["Payment", "PreOrderPayment", "PreOrder", "Other"]


@dataclasses.dataclass(frozen=True)
class Mail:
    subject: str
    date: datetime.datetime
    body: str

    def type(self) -> MailType:
        # pre-order payment
        if "Order Confirmation for Pre-ordered eBooks" in self.subject:
            return "PreOrderPayment"
        # payment
        if (
            "Order Confirmation" in self.subject
            or "お支払い完了のお知らせ" in self.subject
        ):
            return "Payment"
        # pre-order
        if "Pre-order Confirmation" in self.subject:
            return "PreOrder"
        # other
        return "Other"

    @classmethod
    def load_file(
        cls,
        path: pathlib.Path,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> Optional[Self]:
        logger = logger or logging.getLogger(__name__)
        # load file
        logger.info("load %s", path)
        with path.open(mode="rb") as file:
            data = email.parser.BytesParser(policy=email.policy.default).parse(file)
        # check loaded data
        error = False
        # header: from
        error |= check_from_header(data, logger)
        # header: subject
        subject_header = data.get("Subject")
        logger.debug("Subject header: %s", subject_header)
        if subject_header is None:
            logger.error("The subject header is missing")
            error = True
        subject = str(subject_header)
        # header: date
        date = parse_date_header(data, logger)
        # content type
        content_type = data.get_content_type()
        logger.debug("content type: %s", content_type)
        if content_type != "text/plain":
            logger.error("Unexpected content type: %s", content_type)
            error = True
        # multipart
        if data.is_multipart():
            logger.error("Multipart is not expected")
            error = True
        # result
        if error or date is None:
            return None
        return cls(
            subject=subject,
            date=date,
            body=data.get_content(),
        )


def check_from_header(
    data: email.message.Message,
    logger: logging.Logger,
) -> bool:
    header = cast(
        email.headerregistry.UniqueAddressHeader | None,
        data.get("From"),
    )
    logger.debug("From header: %s", header)
    if header is None:
        logger.error("The from header is missing")
        return False
    if len(header.addresses) != 1:
        logger.error("The from header has multiple addresses")
        return False
    address = header.addresses[0]
    expected = {
        "display_name": "BOOK☆WALKER",
        "username": "noreply",
        "domain": "bookwalker.jp",
    }
    for key, value in expected.items():
        if getattr(address, key) != value:
            logger.error(
                "Unexpected %s in the from header: %s",
                key,
                getattr(address, key),
            )
        return False
    return True


def parse_date_header(
    data: email.message.Message,
    logger: logging.Logger,
) -> Optional[datetime.datetime]:
    header = cast(
        email.headerregistry.UniqueDateHeader | None,
        data.get("Date"),
    )
    logger.debug("Date header: %s", header)
    if header is None:
        logger.error("The date header is missing")
        return None
    date = header.datetime
    if date is None:
        logger.error("Failed to get datetime from the date header: %s", header)
    return date
