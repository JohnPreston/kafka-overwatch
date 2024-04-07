#   SPDX-License-Identifier: MPL-2.0
#   Copyright 2023 John "Preston" Mille <john@ews-network.net>


"""Manages SNS notifications to report error and status"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster
    from kafka_overwatch.specs.config import SnsTopicChannel

from os import environ, path

from boto3.session import Session
from botocore.exceptions import ClientError
from compose_x_common.aws import get_assume_role_session
from importlib_resources import files as pkg_files
from jinja2 import BaseLoader, Environment

from kafka_overwatch.config.logging import KAFKA_LOG


class SnsChannel:
    def __init__(self, name: str, definition: SnsTopicChannel):
        self._definition = definition
        self.name = name

        self._usage_report_templates_definitions: dict = {
            "default": pkg_files("kafka_overwatch").joinpath(
                "notifications/aws_sns/usage_report/default.j2"
            ),
            "email": pkg_files("kafka_overwatch").joinpath(
                "notifications/aws_sns/usage_report/email.j2"
            ),
        }
        self.ignore_errors = self.definition.ignore_errors
        self._messages_templates: dict = {}
        self.import_usage_report_jinja2_templates()

    def __repr__(self):
        return f"sns.{self.name}"

    @property
    def usage_report_messages_templates(self) -> dict:
        """Messages templates"""
        return self._messages_templates

    @property
    def definition(self) -> SnsTopicChannel:
        """Initial definition"""
        return self._definition

    @property
    def session(self) -> Session:
        if self.definition.role_arn:
            return get_assume_role_session(
                Session(),
                self.definition.role_arn,
                "KafkaOverwatch",
            )
        else:
            return Session()

    def import_usage_report_jinja2_templates(self) -> None:
        if self.definition.template and self.definition.template.email:
            self._usage_report_templates_definitions["email"] = (
                self.definition.template.email
            )
        for (
            message_type,
            template_path,
        ) in self._usage_report_templates_definitions.items():
            if not path.exists(template_path):
                raise FileNotFoundError(f"Template file not found: {template_path}")
            with open(path.abspath(template_path)) as template_file:
                self._messages_templates[message_type] = template_file.read()

    def publish(self, subject: str, message: str | dict) -> None:
        """Publish message to SNS"""
        if not isinstance(message, (str, dict)):
            raise TypeError(f"message must be str or dict, not {type(message)}")
        client = self.session.client("sns")
        try:
            if isinstance(message, str):
                client.publish(
                    TopicArn=self.definition.topic_arn, Subject=subject, Message=message
                )
            else:
                client.publish(
                    TopicArn=self.definition.topic_arn,
                    Subject=subject,
                    Message=json.dumps(message),
                    MessageStructure="json",
                )

        except (client.exceptions, ClientError) as error:
            KAFKA_LOG.exception(error)
            KAFKA_LOG.error(
                f"{self.name} - Failed to send notification to {self.definition.topic_arn}"
            )

    @staticmethod
    def render_usage_report_message_template(
        template: str, cluster_id: str, s3_url: str, s3_uri: str, s3_signed_url: str
    ) -> str:
        jinja_env = Environment(
            loader=BaseLoader(),
            autoescape=True,
            auto_reload=False,
        ).from_string(template)

        content = jinja_env.render(
            env=environ,
            USAGE_REPORT_S3_URL=s3_url,
            USAGE_REPORT_S3_URI=s3_uri,
            USAGE_REPORT_S3_SIGNED_URL=s3_signed_url,
            KAFKA_CLUSTER_ID=cluster_id,
        )
        return content

    def send_usage_report_notification(
        self,
        cluster: KafkaCluster,
        subject: str,
        s3_uri: str = None,
        s3_url: str = None,
        s3_signed_url: str = None,
    ):
        """Send error notification"""
        messages: dict = {}
        for sns_message_type in self.usage_report_messages_templates:
            try:
                content = self.render_usage_report_message_template(
                    self.usage_report_messages_templates[sns_message_type],
                    cluster.name,
                    s3_url,
                    s3_uri,
                    s3_signed_url,
                )
                messages[sns_message_type] = content
            except Exception as error:
                KAFKA_LOG.exception(error)
                KAFKA_LOG.error(
                    f"Failed to render the Jinja2 template for {sns_message_type}"
                )
                if not self.ignore_errors:
                    raise
        self.publish(subject, messages)
