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

        if not self._config.iam_override:
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
        if not self._config.iam_override:
            return self._session
        else:
            return get_session_from_iam_override(self._config.iam_override)

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
    def upload(
        self, body: str | bytes, file_name: str, mime_type: str = None
    ) -> str | None:
        prefix_key: str = (
            f"{self._config.prefix_key}/{file_name}"
            if self._config.prefix_key != ""
            else file_name
        )
        upload_path: str = (
            f"{self.config.bucket_name}/{self.config.prefix_key}/{file_name}"
        )
        try:
            self.client.put_object(
                Bucket=self._config.bucket_name,
                Key=prefix_key,
                Body=body.encode("utf-8") if not isinstance(body, bytes) else body,
                ContentType="application/json" if not mime_type else mime_type,
            )
            KAFKA_LOG.info(f"File uploaded to {upload_path}")
            return upload_path
        except ClientError as error:
            KAFKA_LOG.exception(error)
            KAFKA_LOG.error(
                "Failed to upload report to "
                f"{self.config.bucket_name}/{self.config.prefix_key}/{file_name}"
            )
        except Exception as error:
            KAFKA_LOG.exception(error)
            KAFKA_LOG.error(
                "Failed to upload report to "
                f"{self.config.bucket_name}/{self.config.prefix_key}/{file_name}"
            )
