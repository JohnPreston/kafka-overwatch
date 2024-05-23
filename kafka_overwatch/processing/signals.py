#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from multiprocessing import Event

STOP_FLAG = Event()


def handle_signals(pid, frame):
    print("Cluster processing received signal to stop", pid, frame)
    STOP_FLAG.set()
