#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>
import time
from threading import Event

FOREVER = 42
stop_flag = Event()


def handle_signals(pid, frame):
    print("Cluster processing received signal to stop", pid, frame)
    global stop_flag
    stop_flag.set()


def wait_between_intervals(time_to_wait: int, too_short_desc: str = None) -> None:
    if time_to_wait <= 0:
        if too_short_desc is not None:
            print(too_short_desc)
        return
    else:
        for _ in range(1, time_to_wait):
            if stop_flag.is_set():
                break
            time.sleep(1)
