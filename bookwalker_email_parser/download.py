from __future__ import annotations

import logging
from typing import Any, Optional

import imapclient
import more_itertools

from .config import Config, TargetConfig


def download(
    config: Config,
    *,
    logger: Optional[logging.Logger] = None,
) -> None:
    logger = logger or logging.getLogger(__name__)
    # client
    with imapclient.IMAPClient(host=config.client.host) as client:
        # login
        logger.info('login to "%s"', config.client.host)
        result = client.login(config.client.username, config.client.password)
        logger.debug("login result: %s", result)
        # target
        for target in config.targets:
            # select folder
            result = client.select_folder(target.folder, readonly=True)
            logger.debug("select folder: %s", result)
            # search
            message_ids = client.search(search_criteria(target))
            if not message_ids:
                logger.debug("no message ids")
                continue
            logger.debug(
                "find %d message_ids: %d ~ %d",
                len(message_ids),
                message_ids[0],
                message_ids[-1],
            )
            # fetch & save
            directory = config.workspace.mail_directory().joinpath(target.folder)
            if not directory.exists():
                directory.mkdir(parents=True)
            for chunk in more_itertools.chunked(message_ids, config.client.fetch_size):
                logger.info(
                    "fetch %d messages: %d ~ %d",
                    len(chunk),
                    chunk[0],
                    chunk[-1],
                )
                for message_id, data in client.fetch(chunk, ["RFC822"]).items():
                    # save
                    logger.debug("save message: %d", message_id)
                    path = directory.joinpath(str(message_id))
                    path.write_bytes(data[b"RFC822"])


def search_criteria(config: TargetConfig) -> list[Any]:
    criteria: list[Any] = []
    # since
    if config.since is not None:
        criteria.extend(["SINCE", config.since])
    # all
    if not criteria:
        criteria.append("ALL")
    return criteria
