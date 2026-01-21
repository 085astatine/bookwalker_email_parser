from __future__ import annotations

import argparse
import contextlib
import dataclasses
import logging
import pathlib
import shutil
import sys
from typing import Iterator, Literal, Optional, TextIO, get_args

from .config import Config, load_config
from .download import download
from .mail import Mail
from .order import (
    Book,
    Charge,
    Payment,
    load_orders_from_json,
    normalize_title,
    parse_order,
    save_orders_as_json,
)
from .output import output_json, output_titles


def main(
    *,
    logger: Optional[logging.Logger] = None,
    args: Optional[list[str]] = None,
) -> None:
    # option
    option = parse_option(args)
    # config
    config = load_config(option.config)
    # logger
    if logger is None:
        logger = default_logger()
    if config.workspace.enable_log:
        logger.addHandler(config.workspace.log_handler())
    if option.verbose:
        logger.setLevel(logging.DEBUG)
    logger.info("bookwalker_email_parser")
    logger.debug("option: %s", option)
    logger.debug("config: %s", config)
    # commands
    match option:
        case DownloadOption():
            # download emails to the workspace
            download(config, logger=logger)
        case ParseOption():
            # parse mails into orders
            mails = load_mails(config, logger=logger)
            orders = parse_orders(mails, logger=logger)
            save_orders_as_json(config.workspace.orders(), orders)
        case OutputOption():
            # output orders
            orders = load_output_targets(config, logger=logger)
            with option.stream() as stream:
                match option.format:
                    case "json":
                        output_json(orders, stream=stream)
                    case "titles":
                        output_titles(orders, stream=stream)
        case CleanOption():
            # clean workspace
            clean(config, option, logger)


def default_logger() -> logging.Logger:
    logger = logging.getLogger("bookwalker_email_parser")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.formatter = logging.Formatter(fmt="%(levelname)s:%(message)s")
    logger.addHandler(handler)
    return logger


@dataclasses.dataclass
class BaseOption:
    verbose: bool
    config: pathlib.Path

    @classmethod
    def add_common_arguments(
        cls,
        parser: argparse.ArgumentParser,
    ) -> None:
        # verbose
        parser.add_argument(
            "-v",
            "-verbose",
            dest="verbose",
            action="store_true",
            help="set log level to debug",
        )
        # config
        parser.add_argument(
            "--config",
            dest="config",
            default="config.toml",
            metavar="TOML",
            type=pathlib.Path,
            help=".toml file (default %(default)s)",
        )

    @classmethod
    def add_arguments(
        cls,
        parser: argparse.ArgumentParser,
    ) -> None:
        parser.set_defaults(cls=cls)


@dataclasses.dataclass
class DownloadOption(BaseOption):
    pass


@dataclasses.dataclass
class ParseOption(BaseOption):
    pass


OutputFormat = Literal["json", "titles"]


@dataclasses.dataclass
class OutputOption(BaseOption):
    format: OutputFormat
    output: Optional[pathlib.Path] = None

    @contextlib.contextmanager
    def stream(self) -> Iterator[TextIO]:
        try:
            if self.output is None:
                yield sys.stdout
            else:
                with self.output.open(mode="w", encoding="utf-8") as file:
                    yield file
        finally:
            pass

    @classmethod
    def add_arguments(
        cls,
        parser: argparse.ArgumentParser,
    ) -> None:
        super().add_arguments(parser)
        # format
        parser.add_argument(
            "--format",
            dest="format",
            choices=get_args(OutputFormat),
            required=True,
            help="select output format",
        )
        # output
        parser.add_argument(
            "-o",
            "--output",
            dest="output",
            type=pathlib.Path,
            metavar="FILE",
            help="output messages to FILE",
        )


CleanTarget = Literal["all", "email", "log"]


@dataclasses.dataclass
class CleanOption(BaseOption):
    target: CleanTarget = "all"

    @classmethod
    def add_arguments(
        cls,
        parser: argparse.ArgumentParser,
    ) -> None:
        super().add_arguments(parser)
        # target
        parser.add_argument(
            "--target",
            dest="target",
            default="all",
            choices=get_args(CleanTarget),
            help="clean target",
        )


Option = DownloadOption | ParseOption | OutputOption | CleanOption


def option_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    BaseOption.add_common_arguments(parser)
    # command
    sub_parsers = parser.add_subparsers(
        title="command",
        description="command to be executed",
        required=True,
    )
    # download
    DownloadOption.add_arguments(
        sub_parsers.add_parser(
            "download",
            help="download emails to the workspace",
        )
    )
    # parse
    ParseOption.add_arguments(
        sub_parsers.add_parser(
            "parse",
            help="parse emails into orders",
        )
    )
    # output
    OutputOption.add_arguments(
        sub_parsers.add_parser(
            "output",
            help="output orders",
        )
    )
    # clean
    CleanOption.add_arguments(
        sub_parsers.add_parser(
            "clean",
            help="clean the workspace",
        )
    )
    return parser


def parse_option(args: Optional[list[str]] = None) -> Option:
    option = vars(option_parser().parse_args(args))
    cls = option.pop("cls")
    return cls(**option)


def load_mails(
    config: Config,
    *,
    logger: Optional[logging.Logger] = None,
) -> list[Mail]:
    mails: list[Mail] = []
    for target in config.targets:
        directory = config.workspace.mail_directory().joinpath(target.folder)
        for path in directory.iterdir():
            mail = Mail.load_file(path, logger=logger)
            if mail is not None:
                mails.append(mail)
    # sort from oldest to newest
    mails.sort(key=lambda mail: mail.date)
    return mails


def parse_orders(
    mails: list[Mail],
    *,
    logger: Optional[logging.Logger] = None,
) -> list[Payment | Charge]:
    orders: list[Payment | Charge] = []
    for mail in mails:
        order = parse_order(mail, logger=logger)
        if order is not None:
            orders.append(order)
    return orders


def load_output_targets(
    config: Config,
    *,
    logger: Optional[logging.Logger] = None,
) -> list[Payment | Charge]:
    logger = logger or logging.getLogger(__name__)
    result: list[Payment | Charge] = []
    # load orders from the workspace
    orders = load_orders_from_json(config.workspace.orders())
    # parse mails into orders
    for order in orders:
        # check order date is within period
        if not config.output.in_period(order.date):
            logger.info("order.date %s is not within the target period", order.date)
            continue
        match order:
            case Payment() if config.output.normalize_title:
                result.append(normalize_book_titles(order))
            case _:
                result.append(order)
    return result


def normalize_book_titles(payment: Payment) -> Payment:
    books: list[Book] = [
        Book(title=normalize_title(book.title), price=book.price)
        for book in payment.books
    ]
    return Payment(
        date=payment.date,
        books=books,
        discount=payment.discount,
        tax=payment.tax,
        coin_usage=payment.coin_usage,
        granted_coins=[*payment.granted_coins],
    )


def clean(
    config: Config,
    option: CleanOption,
    logger: logging.Logger,
) -> None:
    match option.target:
        case "all":
            logger.info("clean workspace")
            shutil.rmtree(config.workspace.path)
        case "email":
            logger.info("clean emails")
            shutil.rmtree(config.workspace.mail_directory())
        case "log":
            logger.info("clean logs")
            shutil.rmtree(config.workspace.log_directory())


if __name__ == "__main__":
    main()
