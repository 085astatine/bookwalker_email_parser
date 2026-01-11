from __future__ import annotations

import dataclasses
import datetime
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
    fetch_size: Optional[int] = None
    request_interval: float = 1.0


@dataclasses.dataclass(frozen=True)
class WorkspaceConfig:
    path: pathlib.Path

    def mail_directory(self) -> pathlib.Path:
        return self.path.joinpath("mail")


@dataclasses.dataclass(frozen=True)
class TargetConfig:
    folder: str
    since: Optional[datetime.date | datetime.datetime] = None


@dataclasses.dataclass
class Config:
    client: ClientConfig
    workspace: WorkspaceConfig
    targets: list[TargetConfig] = dataclasses.field(default_factory=list)


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
        config=dacite.Config(
            type_hooks={
                pathlib.Path: pathlib.Path,
            },
            strict=True,
        ),
    )
    logger.debug("config: %s", config)
    return config
