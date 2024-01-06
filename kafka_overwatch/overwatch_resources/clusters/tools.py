#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster

from kafka_overwatch.config.logging import KAFKA_LOG


def output_dataframe(
    kafka_cluster: KafkaCluster, content, file_name: str, mime_type: str
):
    """Writes dataframe to S3 or to local disk (or both)"""
    if kafka_cluster.s3_report:
        kafka_cluster.s3_report.upload(
            content,
            file_name,
            mimetypes=mime_type,
        )
    if kafka_cluster.local_reports_directory_path:
        df_output_path: str = (
            f"{kafka_cluster.local_reports_directory_path}/{file_name}"
        )
        with open(
            df_output_path,
            "w",
        ) as df_fd:
            df_fd.write(content)
        KAFKA_LOG.info(f"{kafka_cluster.name} - Outputted DF to {df_output_path}")
