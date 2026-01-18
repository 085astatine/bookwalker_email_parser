from __future__ import annotations

import argparse
import dataclasses
import logging
import pathlib
from typing import Optional

from .config import Config, load_config
from .download import download
from .mail import Mail
from .order import (
    Charge,
    Payment,
    parse_order,
    save_orders_as_json,
)


def main(
    *,
    logger: Optional[logging.Logger] = None,
    args: Optional[list[str]] = None,
) -> None:
    # logger
    if logger is None:
        logger = default_logger()
    logger.info("bookwalker_email_parser")
    # option
    option = parse_option(args)
    if option.verbose:
        logger.setLevel(logging.DEBUG)
    logger.debug("option: %s", option)
    # config
    config = load_config(option.config, logger=logger)
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


def default_logger() -> logging.Logger:
    logger = logging.getLogger("bookwalker_email_parser")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.formatter = logging.Formatter(
        fmt="%(asctime)s %(name)s:%(levelname)s:%(message)s"
    )
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


Option = DownloadOption | ParseOption


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


if __name__ == "__main__":
    main()
