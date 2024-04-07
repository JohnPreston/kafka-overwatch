#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.config.config import OverwatchConfig

import concurrent.futures
import signal

from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.overwatch_resources.clusters import KafkaCluster
from kafka_overwatch.processing import handle_signals, stop_flag
from kafka_overwatch.processing.clusters import process_cluster
from kafka_overwatch.processing.schema_registries import process_schema_registry


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
        self.kafka_clusters: dict[str, KafkaCluster] = {}
        signal.signal(signal.SIGINT, handle_signals)
        signal.signal(signal.SIGTERM, handle_signals)

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
        self.kafka_clusters.update(
            {
                name: KafkaCluster(name, config, self.config)
                for name, config in self.config.input_config.clusters.items()
            }
        )
        sr_jobs: list = [
            [_sr, self.config.runtime_key, self.config]
            for _sr in self.config.schema_registries.values()
        ]
        for (
            cluster_name,
            cluster,
        ) in self.kafka_clusters.items():
            clusters_jobs.append([cluster, self.config])
        self.multi_clusters_processing(clusters_jobs, sr_jobs)

    def multi_clusters_processing(self, clusters_jobs: list, sr_jobs: list):
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=(len(clusters_jobs) + len(sr_jobs))
        ) as executor:
            futures_to_data: dict[concurrent.futures.Future, list] = {}
            if sr_jobs:
                futures_to_data.update(
                    {
                        executor.submit(process_schema_registry, *sr_job): sr_job
                        for sr_job in sr_jobs
                    }
                )
            futures_to_data.update(
                {
                    executor.submit(process_cluster, *cluster_job): cluster_job
                    for cluster_job in clusters_jobs
                }
            )
            try:
                while not stop_flag.is_set():
                    concurrent.futures.wait(futures_to_data, timeout=10)
            except KeyboardInterrupt:
                for _future in futures_to_data:
                    _future.cancel()
                executor.shutdown(wait=True, cancel_futures=True)
        return
