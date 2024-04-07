#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

import concurrent.futures
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.schema_registry import SchemaRegistry
    from kafka_overwatch.config.config import OverwatchConfig

import pickle
import signal
from datetime import datetime, timedelta

from prometheus_client import Gauge

from kafka_overwatch.common import waiting_on_futures
from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.config.threads_settings import NUM_THREADS
from kafka_overwatch.overwatch_resources.schema_registry import (
    Schema,
    Subject,
    refresh_subject_metadata,
)
from kafka_overwatch.processing import ensure_prometheus_multiproc

from . import FOREVER, handle_signals, stop_flag, wait_between_intervals


def retrieve_from_subjects(schema_registry: SchemaRegistry, sr_client) -> None:
    """
    Much longer way to retrieve all the schemas & subjects, using the subjects endpoints.
    Using threading to speed up the processing, but still slower by an order of magnitude
    than retrieving the schemas directly.
    """
    KAFKA_LOG.info(f"{schema_registry.name} - Retrieving all subjects")
    all_subjects = sr_client.get_all_subjects().json()
    KAFKA_LOG.info(f"{schema_registry.name} - Retrieved all subjects")
    for subject_name in all_subjects:
        if subject_name not in schema_registry.subjects:
            _subject = Subject(subject_name, schema_registry)
            schema_registry.subjects[subject_name] = _subject
    KAFKA_LOG.info(
        "%s - Started subjects/schemas update at %s"
        % (schema_registry.name, datetime.utcnow().isoformat())
    )
    subject_jobs: list = [
        [_subject, sr_client] for _subject in schema_registry.subjects.values()
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures_to_data: dict[concurrent.futures, list] = {}
        futures_to_data.update(
            {
                executor.submit(refresh_subject_metadata, *job): job
                for job in subject_jobs
            }
        )
        _pending = len(futures_to_data)
        KAFKA_LOG.debug(
            "Schema registry: %s | Subjects to scan: %s"
            % (schema_registry.name, _pending)
        )
        waiting_on_futures(
            executor,
            futures_to_data,
            "Schema Registry",
            schema_registry.name,
            "Subjects",
        )


def retrieve_from_schemas(schema_registry: SchemaRegistry, schemas: list[dict]) -> None:
    """
    Fastest way, used if /schemas worked
    """
    KAFKA_LOG.info(f"Schema Registry: {schema_registry.name} | Retrieving all schemas")
    for _schema in schemas:
        schema_subject: str = _schema["subject"]
        schema_id: int = _schema["id"]
        schema_version: int = _schema["version"]
        _schema_content: str = _schema["schema"]

        if schema_id not in schema_registry.schemas:
            schema = Schema(schema_id, schema_registry)
            schema_registry.schemas[schema_id] = schema
        else:
            schema = schema_registry.schemas[schema_id]

        if schema_subject not in schema_registry.subjects:
            subject = Subject(schema_subject, schema_registry)
            schema_registry.subjects[schema_subject] = subject
        else:
            subject = schema_registry.subjects[schema_subject]
        if schema_version not in subject.versions:
            subject.versions[schema_version] = schema


def init_schema_registry_prometheus_reporting(
    schema_registry: SchemaRegistry, overwatch_config: OverwatchConfig
):
    ensure_prometheus_multiproc(overwatch_config.prometheus_registry_dir.name)
    subjects_count: Gauge = overwatch_config.prometheus_collectors["subjects_count"]
    schemas_count: Gauge = overwatch_config.prometheus_collectors["schemas_count"]

    subjects_count = subjects_count.labels(schema_registry=schema_registry.name)
    schemas_count = schemas_count.labels(schema_registry=schema_registry.name)
    return subjects_count, schemas_count


def import_subjects(
    schema_registry: SchemaRegistry, runtime_key, overwatch_config: OverwatchConfig
) -> None:
    signal.signal(signal.SIGINT, handle_signals)
    signal.signal(signal.SIGTERM, handle_signals)
    subjects_count, schemas_count = init_schema_registry_prometheus_reporting(
        schema_registry, overwatch_config
    )
    sr_client = schema_registry.get_client(runtime_key)
    while FOREVER:
        if stop_flag.is_set():
            break
        now = datetime.utcnow()
        next_scan = now + timedelta(
            seconds=schema_registry.config.schema_registry_scan_interval
        )
        try:
            schemas_r = sr_client.get_all_schemas()
            if 200 <= schemas_r.status_code <= 299:
                retrieve_from_schemas(schema_registry, schemas_r.json())
        except Exception as error:
            KAFKA_LOG.exception(error)
            KAFKA_LOG.error(
                "{} Failed to retrieve schemas via /schemas".format(
                    schema_registry.name
                )
            )
            retrieve_from_subjects(schema_registry, sr_client)
        try:
            subjects_count.set(len(schema_registry.subjects))
            schemas_count.set(len(schema_registry.schemas))
        except Exception as error:
            print(error)
            KAFKA_LOG.error(
                "Schema registry: %s | Unable to set prometheus metrics"
                % (schema_registry.name,)
            )
        then = datetime.utcnow()
        delta = int((next_scan - then).total_seconds())
        try:
            with open(schema_registry.mmap_file, "wb") as bin_fd:
                bin_fd.write(pickle.dumps(schema_registry))
                KAFKA_LOG.info(
                    "%s Wrote schema registry to %s"
                    % (schema_registry.name, schema_registry.mmap_file)
                )
        except Exception as error:
            KAFKA_LOG.exception(error)
            KAFKA_LOG.error(
                "Schema Registry: %s | Failed to write mmap file to %s"
                % (schema_registry.name, schema_registry.mmap_file)
            )
        if delta > 0:
            KAFKA_LOG.info("%s - Waiting %d seconds" % (schema_registry.name, delta))
            wait_between_intervals(
                delta,
            )
        else:
            KAFKA_LOG.warning(
                "%s - Interval is %d - yet it took %d to complete processing."
                % (
                    schema_registry.name,
                    schema_registry.config.schema_registry_scan_interval,
                    (then - now).total_seconds(),
                )
            )
