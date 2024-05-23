#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

import os
import time


def wait_between_intervals(
    stop_flag: dict, time_to_wait: int, too_short_desc: str = None
) -> None:
    if time_to_wait <= 0:
        if too_short_desc is not None:
            print(too_short_desc)
    else:
        for _ in range(1, time_to_wait):
            if stop_flag["stop"] is True:
                break
            time.sleep(1)


def ensure_prometheus_multiproc(prometheus_dir_path: str):
    """
    Just in case the env_var had not propagated among processes,
    setting in child env var.
    """
    if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        os.environ["PROMETHEUS_MULTIPROC_DIR"] = prometheus_dir_path
    if not os.environ.get("prometheus_multiproc_dir"):
        os.environ["prometheus_multiproc_dir"] = prometheus_dir_path
