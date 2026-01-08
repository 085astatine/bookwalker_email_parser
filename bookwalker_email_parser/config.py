from __future__ import annotations

import dataclasses
import logging
import pathlib
import tomllib
from typing import Optional

import dacite


@dataclasses.dataclass(frozen=True)
class ClientConfig:
    host: str
    username: str
    password: str


@dataclasses.dataclass
class Config:
    client: ClientConfig


def load_config(
    path: pathlib.Path,
    *,
    logger: Optional[logging.Logger] = None,
) -> Config:
    logger = logger or logging.getLogger(__name__)
    # load TOML
    logger.info('load config from "%s"', path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    logger.debug("loaded TOML: %s", data)
    # to dataclass
    config = dacite.from_dict(
        data_class=Config,
        data=data,
    )
    logger.debug("config: %s", config)
    return config
