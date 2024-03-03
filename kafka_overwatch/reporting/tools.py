#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

from pandas import DataFrame

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
            mime_type=mime_type,
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


def export_df(kafka_cluster: KafkaCluster, df: DataFrame, resource_name: str) -> None:
    """
    If DF exporters are set, write/export to these.
    """
    export_to_mime: dict = {"csv": "text/csv", "json": "application/json"}
    if (
        kafka_cluster.config.reporting_config.output_formats
        and not kafka_cluster.config.reporting_config.output_formats.pandas_dataframe
    ):
        return
    for (
        export_type
    ) in kafka_cluster.config.reporting_config.output_formats.pandas_dataframe:
        export_fn = None
        if hasattr(df, f"to_{export_type}"):
            export_fn = getattr(df, f"to_{export_type}")

        if export_type in export_to_mime and export_fn:
            output_dataframe(
                kafka_cluster,
                export_fn(),
                f"{kafka_cluster.name}.{resource_name}_dataframe.{export_type}",
                mime_type=export_to_mime[export_type],
            )
