from __future__ import annotations

import logging
from typing import Optional

import imapclient

from .config import Config


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
