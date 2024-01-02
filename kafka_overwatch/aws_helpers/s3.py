#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from boto3.exceptions import S3UploadFailedError
from boto3.session import Session
from botocore.exceptions import ClientError
from compose_x_common.aws import get_assume_role_session
from retry import retry

from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.specs.config import S3Output


class S3Handler:
    def __init__(self, s3_output_config: S3Output):
        self._config = s3_output_config

        if not self._config.IamOverride:
            self._session: Session = Session()
        else:
            if (
                self.config.IamOverride.ProfileName
                and not self.config.IamOverride.AssumeRole
            ):
                self._session = Session(
                    profile_name=self._config.IamOverride.ProfileName
                )
            elif (
                self.config.IamOverride.AssumeRole
                and self.config.IamOverride.ProfileName
            ):
                self._session = get_assume_role_session(
                    Session(), self._config.IamOverride.AssumeRole.RoleArn
                )
            else:
                self._session = get_assume_role_session(
                    Session(profile_name=self.config.IamOverride.ProfileName),
                    self.config.IamOverride.AssumeRole.RoleArn,
                )
        self._client = self._session.client("s3")

    @property
    def config(self) -> S3Output:
        return self._config

    @retry((S3UploadFailedError,), tries=3, delay=1, logger=KAFKA_LOG)
    def upload(self, report: str, report_name: str, mime_type: str = None):
        try:
            self._client.put_object(
                Bucket=self._config.BucketName,
                Key=f"{self._config.PrefixKey}/{report_name}",
                Body=report.encode("utf-8"),
                ContentType="application/json" if not mime_type else mime_type,
            )
            KAFKA_LOG.info(
                "Report uploaded to "
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
