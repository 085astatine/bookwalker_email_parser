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
    enable_log: bool = True
    log_format: str = "%(levelname)s:%(message)s"

    def orders(self) -> pathlib.Path:
        return self.path.joinpath("orders.json")

    def log(
        self,
        time: Optional[datetime.datetime] = None,
    ) -> pathlib.Path:
        if time is None:
            time = datetime.datetime.now()
        return self.log_directory().joinpath(time.strftime("%Y-%m-%d_%H-%M-%S.log"))

    def mail_directory(self) -> pathlib.Path:
        return self.path.joinpath("mail")

    def log_directory(self) -> pathlib.Path:
        return self.path.joinpath("log")

    def log_handler(
        self,
        time: Optional[datetime.datetime] = None,
    ) -> logging.FileHandler:
        if not self.log_directory().exists():
            self.log_directory().mkdir(parents=True)
        handler = logging.FileHandler(self.log(time), encoding="utf-8")
        handler.formatter = logging.Formatter(fmt=self.log_format)
        return handler


@dataclasses.dataclass(frozen=True)
class TargetConfig:
    folder: str
    since: Optional[datetime.date | datetime.datetime] = None


@dataclasses.dataclass(frozen=True)
class OutputConfig:
    normalize_title: bool = False
    since: Optional[datetime.datetime] = None
    until: Optional[datetime.datetime] = None

    def in_period(self, date: datetime.datetime) -> bool:
        if self.since is not None:
            if date.timestamp() < self.since.timestamp():
                return False
        if self.until is not None:
            if self.until.timestamp() < date.timestamp():
                return False
        return True


@dataclasses.dataclass
class Config:
    client: ClientConfig
    targets: list[TargetConfig]
    workspace: WorkspaceConfig
    output: OutputConfig = OutputConfig()


def load_config(path: pathlib.Path) -> Config:
    # load TOML
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    # to dataclass
    config = dacite.from_dict(
        data_class=Config,
        data=data,
        config=dacite.Config(
            type_hooks={
                pathlib.Path: pathlib.Path,
                datetime.datetime: to_datetime,
            },
            strict=True,
        ),
    )
    return config


def to_datetime(
    value: datetime.date | datetime.datetime,
) -> datetime.datetime:
    match value:
        case datetime.datetime():
            return value
        case datetime.date():
            # add time(00:00:00) to date
            return datetime.datetime.combine(value, datetime.time())
