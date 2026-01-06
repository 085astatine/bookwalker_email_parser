from __future__ import annotations

import argparse
import dataclasses
import logging
from typing import Optional


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
class Option:
    verbose: bool

    @classmethod
    def parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        # verbose
        parser.add_argument(
            "-v",
            "-verbose",
            dest="verbose",
            action="store_true",
            help="set log level to debug",
        )
        return parser


def parse_option(args: Optional[list[str]] = None) -> Option:
    option = Option.parser().parse_args(args)
    return Option(**vars(option))


if __name__ == "__main__":
    main()
