#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from concurrent.futures import Future

import concurrent

from compose_x_common.compose_x_common import keyisset

from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.processing.signals import STOP_FLAG


def waiting_on_futures(
    executor,
    futures_to_data: list[Future] | dict[Future, Any],
    resource_type: str,
    resource_name: str,
    scan_type: str,
    stop_flag: dict,
):
    _pending = len(futures_to_data)
    KAFKA_LOG.debug(
        "{}: {} | {} to scan: {}".format(
            resource_type, resource_name, scan_type, _pending
        )
    )
    while _pending > 0:
        if STOP_FLAG.is_set() or stop_flag["stop"] is True:
            for _future in futures_to_data:
                _future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            return
        _, other = concurrent.futures.wait(futures_to_data, timeout=5)
        _pending = len([_f for _f in other if not _f.done()])
        KAFKA_LOG.debug(
            "%s: %s | %s pending: %s"
            % (resource_type, resource_name, scan_type, _pending)
        )
