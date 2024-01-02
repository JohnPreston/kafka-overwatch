#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.config.config import OverwatchConfig

import signal
import threading
from multiprocessing import Process
from time import sleep

from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.config.threads_settings import NUM_THREADS
from kafka_overwatch.processing.clusters import process_cluster


class KafkaOverwatchService:

    """
    Main service which starts the prometheus server and the processes for each
    Kafka cluster to be processed independently.

    Upon receiving SIGTERM or SIGINT, it will send a SIGTERM to all child processes

    The prometheus dependency is imported at the last minute to make sure it will take the
    multiprocess folder env var into account.
    """

    def __init__(self, config: OverwatchConfig) -> None:
        self._config = config
        self.keep_running = 42
        self.processes: list[Process] = []
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    @property
    def config(self) -> OverwatchConfig:
        return self._config

    def init_system(self):
        """
        Import prometheus_client.start_http_server at the latest point to make sure the
        multiprocess folder env var is taken into account.
        """
        from prometheus_client import start_http_server

        start_http_server(8000, registry=self.config.prometheus_registry)

    def start(self):
        KAFKA_LOG.info("Starting Kafka Overwatch")
        KAFKA_LOG.info(f"CONCURRENT_THREADS for processing set to {NUM_THREADS}")
        try:
            self.init_system()
            for (
                cluster_name,
                cluster_config,
            ) in self.config.input_config.clusters.items():
                _cluster_process = Process(
                    target=process_cluster,
                    args=(
                        cluster_name,
                        cluster_config,
                        self.config,
                    ),
                )
                self.processes.append(_cluster_process)
                _cluster_process.start()

            while self.keep_running:
                sleep(1)

        except KeyboardInterrupt:
            self.exit_gracefully(None, None)

    def exit_gracefully(self, pid, frame):
        """
        Upon SIGNAL, stop the processes of each cluster.
        """
        from prometheus_client.multiprocess import mark_process_dead

        KAFKA_LOG.warning(f"Exiting gracefully due to signal/interruption - {pid}")
        self.keep_running = False
        KAFKA_LOG.info(
            f"{threading.get_native_id()} "
            f"- Signaling child processes {[_p.pid for _p in self.processes]}"
        )
        for process in self.processes:
            if process.is_alive():
                KAFKA_LOG.info(
                    f"Parent {threading.get_native_id()} - Sending SIGTERM to {process.pid}"
                )
                process.terminate()
                process.join()
            mark_process_dead(process.pid, self.config.prometheus_registry_dir.name)
