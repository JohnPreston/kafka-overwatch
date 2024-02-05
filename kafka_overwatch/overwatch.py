#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.config.config import OverwatchConfig

import concurrent.futures
import signal
from multiprocessing import Event

from kafka_overwatch.config.logging import KAFKA_LOG
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
        self.stop_event = Event()
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
        self.init_system()
        clusters_jobs = []
        for (
            cluster_name,
            cluster_config,
        ) in self.config.input_config.clusters.items():
            clusters_jobs.append([cluster_name, cluster_config, self.config])

        if len(clusters_jobs) > 1:
            self.multi_clusters_processing(clusters_jobs)
        else:
            cluster_name = list(self.config.input_config.clusters.keys())[0]
            cluster_config = self.config.input_config.clusters[cluster_name]
            try:
                process_cluster(cluster_name, cluster_config, self.config)
            except Exception as error:
                KAFKA_LOG.error(f"Error processing cluster {cluster_name} - {error}")
                raise

    def multi_clusters_processing(self, clusters_jobs):
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=len(self.config.input_config.clusters)
        ) as executor:
            futures_to_data: dict[concurrent.futures.Future, list] = {
                executor.submit(process_cluster, *cluster_job): cluster_job
                for cluster_job in clusters_jobs
            }
            try:
                while not self.stop_event.is_set():
                    concurrent.futures.wait(futures_to_data, timeout=10)
            except KeyboardInterrupt:
                for _future in futures_to_data:
                    _future.cancel()
                executor.shutdown(wait=True, cancel_futures=True)
        return

    def exit_gracefully(self, pid, frame):
        """
        Upon SIGNAL, stop the processes of each cluster.
        """

        KAFKA_LOG.warning(
            f"main - Exiting gracefully due to signal/interruption - {pid}"
        )
        self.stop_event.set()
