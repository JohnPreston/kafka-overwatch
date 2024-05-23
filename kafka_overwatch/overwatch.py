#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.config.config import OverwatchConfig

import concurrent.futures
import signal
from multiprocessing import Event, Manager

from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.overwatch_resources.clusters import KafkaCluster
from kafka_overwatch.processing.clusters import process_cluster
from kafka_overwatch.processing.schema_registries import process_schema_registry

STOP_FLAG = Event()


def handle_signals(pid, frame, stop_flag):
    print("Cluster processing received signal to stop", pid, frame)
    stop_flag["stop"] = True
    STOP_FLAG.set()


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

    @property
    def config(self) -> OverwatchConfig:
        return self._config

    def init_prometheus(self):
        """
        Import prometheus_client.start_http_server at the latest point to make sure the
        multiprocess folder env var is taken into account.
        """
        from prometheus_client import start_http_server

        return start_http_server(8000, registry=self.config.prometheus_registry)

    def start(self):
        KAFKA_LOG.info("Starting Kafka Overwatch")
        httpd, _ = self.init_prometheus()
        clusters_jobs = []
        manager = Manager()
        stop_flag = manager.dict()
        stop_flag["stop"] = False

        signal.signal(
            signal.SIGTERM,
            lambda signum, frame: handle_signals(signum, frame, stop_flag),
        )
        signal.signal(
            signal.SIGINT,
            lambda signum, frame: handle_signals(signum, frame, stop_flag),
        )

        self.kafka_clusters.update(
            {
                name: KafkaCluster(name, config, self.config)
                for name, config in self.config.input_config.clusters.items()
            }
        )
        sr_jobs: list = [
            [_sr, self.config.runtime_key, self.config, stop_flag]
            for _sr in self.config.schema_registries.values()
        ]
        for (
            cluster_name,
            cluster,
        ) in self.kafka_clusters.items():
            clusters_jobs.append([cluster, self.config, stop_flag])
        self.multi_clusters_processing(clusters_jobs, sr_jobs, httpd)

    @staticmethod
    def multi_clusters_processing(clusters_jobs: list, sr_jobs: list, httpd):
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
                while not STOP_FLAG.is_set():
                    concurrent.futures.wait(futures_to_data, timeout=10)
            except KeyboardInterrupt:
                executor.shutdown(wait=True, cancel_futures=True)
            finally:
                executor.shutdown(wait=True, cancel_futures=True)
                print("Executor has been shut down")
                httpd.shutdown()
        return
