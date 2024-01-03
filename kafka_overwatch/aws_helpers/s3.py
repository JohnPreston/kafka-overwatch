#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from boto3.exceptions import S3UploadFailedError
from boto3.session import Session
from botocore.exceptions import ClientError
from compose_x_common.aws import get_assume_role_session
from retry import retry

from kafka_overwatch.aws_helpers import get_session_from_iam_override
from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.specs.config import S3Output


class S3Handler:
    def __init__(self, s3_output_config: S3Output):
        self._config = s3_output_config

        if not self._config.IamOverride:
            self._session: Session = Session()
        else:
            self._session = None

        if self._session:
            self._client = self._session.client("s3")
        else:
            self._client = None

    @property
    def config(self) -> S3Output:
        return self._config

    @property
    def session(self) -> Session:
        if not self._config.IamOverride:
            return self._session
        else:
            return get_session_from_iam_override(self._config.IamOverride)

    @property
    def client(self):
        """Ensures to get client with a fresh session if needed"""
        if not self._client and self._session:
            self._client = self.session.client("s3")
            return self._client
        elif self._client:
            return self._client
        return self.session.client("s3")

    @retry((S3UploadFailedError,), tries=3, delay=1, logger=KAFKA_LOG)
    def upload(self, report: str, report_name: str, mime_type: str = None):
        try:
            self.client.put_object(
                Bucket=self._config.BucketName,
                Key=f"{self._config.PrefixKey}/{report_name}",
                Body=report.encode("utf-8"),
                ContentType="application/json" if not mime_type else mime_type,
            )
            KAFKA_LOG.info(
                "File uploaded to "
                f"{self.config.BucketName}/{self.config.PrefixKey}/{report_name}"
            )
            return
        except ClientError as error:
            KAFKA_LOG.exception(error)
            KAFKA_LOG.error(
                "Failed to upload report to "
                f"{self.config.BucketName}/{self.config.PrefixKey}/{report_name}"
            )
        except Exception as error:
            KAFKA_LOG.exception(error)
            KAFKA_LOG.error(
                "Failed to upload report to "
                f"{self.config.BucketName}/{self.config.PrefixKey}/{report_name}"
            )
