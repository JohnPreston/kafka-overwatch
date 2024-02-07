# generated by datamodel-codegen:
#   filename:  config.json

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


@dataclass
class AwsEmf:
    namespace: str
    high_resolution_metrics: bool | None = False
    """
    https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/publishingMetrics.html#high-resolution-metrics
    """
    dimensions: dict[str, str] | None = None
    """
    Dimension name and value to set in a key/value format.
    """
    enabled: bool | None = None


@dataclass
class Template:
    """
    Allows to set specific templates for email and sms
    """

    email: str | None = None
    """
    Optional - Path to a template for SNS Email messages
    """
    sms: str | None = None
    """
    Optional - Path to a template for SNS SMS messages
    """


@dataclass
class SnsTopicChannel:
    topic_arn: str
    """
    ARN of the SNS topic.
    """
    role_arn: str | None = None
    """
    Optional - Use IAM role to publish messages using another IAM role
    """
    ignore_errors: bool | None = None
    """
    Prevents exception if true when an exception occurs.
    """
    template: Template | None = None
    """
    Allows to set specific templates for email and sms
    """


@dataclass
class Prometheus:
    enabled: bool | None = None


@dataclass
class ClusterMetrics:
    prometheus: Prometheus | None = None
    aws_emf: AwsEmf | None = None


Regexes = list[str]


@dataclass
class OutputFormats:
    """
    The different types of outputs to produce.
    """

    pandas_dataframe: list[str] | None = None


class BackupStyle(Enum):
    cfn_kafka_admin = "cfn-kafka-admin"
    kafka_topics_sh = "kafka-topics.sh"


@dataclass
class AssumeRole:
    RoleArn: str
    """
    Optional - IAM Role ARN to assume
    """
    RoleSessionName: str | None = "kafka-overwatch@aws"
    """
    Optional - Name of the session to use
    """
    ExternalId: str | None = None
    """
    Optional - External ID to use when assuming a role
    """


@dataclass
class IamOverride1:
    """
    Optional - IAM profile/settings override to use. Defaults to SDK settings.
    """

    ProfileName: str
    """
    Optional - Use IAM profile to publish messages using another IAM profile
    """
    AssumeRole: AssumeRole | None = None


@dataclass
class IamOverride2:
    """
    Optional - IAM profile/settings override to use. Defaults to SDK settings.
    """

    AssumeRole: AssumeRole
    ProfileName: str | None = None
    """
    Optional - Use IAM profile to publish messages using another IAM profile
    """


IamOverride = Union[IamOverride1, IamOverride2]


ClusterScanIntervalInSeconds = int


@dataclass
class MskProvider:
    iam_override: IamOverride | None = None
    """
    Override default session to perform the clusters discovery
    """
    exclude_regions: list[str] | None = None
    """
    List of regions not to look for MSK clusters
    """


@dataclass
class ConfluentCloudAuth:
    api_key: str | None = None
    """
    The API key to use to perform API calls to Confluent Cloud
    """
    api_secret: str | None = None
    """
    The API Secret to perform API calls to Confluent Cloud
    """


@dataclass
class SaaSProviderAwsSecretsManager:
    secret_id: str | None = None
    """
    Name or ARN of secret to use to store the key. If ARN is detected, existing secret content will be updated. If name is provided but not found, creates new secret.
    """
    iam_override: IamOverride | None = None


@dataclass
class TopicNamingConvention:
    """
    Evaluates topic name against one or more regex and reports non-compliant topics
    """

    regexes: list[str]
    ignore_regexes: list[str] | None = None
    """
    List/Array of regular expression of topic names to ignore for review. Use to ignore internal or stream topics
    """


@dataclass
class GovernanceReportingConfig:
    """
    Configuration for governance cluster analysis
    """

    topic_naming_convention: TopicNamingConvention | None = None
    """
    Evaluates topic name against one or more regex and reports non-compliant topics
    """


ProfileName = str


@dataclass
class Global:
    """
    Global settings. Defines global default values that can be overriden for each cluster.
    """

    cluster_scan_interval_in_seconds: ClusterScanIntervalInSeconds
    """
    Default topics & consumer groups scan interval
    """


@dataclass
class AwsEmfModel:
    log_group_name: str | None = "kafka/cluster/overwatch/metrics"
    """
    override log group name to publish metrics to. Importance: High
    """
    service_name: str | None = None
    """
    override value for EMF Service name. Importance: Low
    """
    watcher_config: AwsEmf | None = None


@dataclass
class NotificationChannels:
    """
    Channels to send notifications to when reports have been generated.
    """

    sns: dict[str, SnsTopicChannel] | None = None


@dataclass
class S3Output:
    bucket_name: str | None = None
    """
    Name of the S3 bucket
    """
    prefix_key: str | None = ""
    """
    Path in the bucket.
    """
    iam_override: IamOverride | None = None


@dataclass
class Exports:
    """
    Reporting export locations
    """

    S3: S3Output | None = None
    local: str | None = "/tmp/kafka-overwatch-reports/"
    """
    Local directory to store the reports to.
    """
    kafka: dict[str, Any] | None = None
    """
    Configuration to persist reports into Kafka. Not yet implemented.
    """


@dataclass
class ReportingConfig:
    """
    Configure reporting output. Applies to all clusters.
    """

    evaluation_period_in_seconds: int | None = 60
    """
    Interval between reports.
    """
    output_formats: OutputFormats | None = None
    """
    The different types of outputs to produce.
    """
    exports: Exports | None = None
    """
    Reporting export locations
    """


@dataclass
class ClusterConfigAuth:
    """
    Allows to set override configuration for secret values interpolation
    """

    iam_override: IamOverride | None = None


@dataclass
class ClusterConfig:
    kafka: dict[str, Any] | None = None
    """
    Configuration as documented in https://github.com/confluentinc/librdkafka/blob/master/CONFIGURATION.md
    """
    cluster_config_auth: ClusterConfigAuth | None = None
    """
    Allows to set override configuration for secret values interpolation
    """


@dataclass
class Iam:
    ProfileName: ProfileName | None = None
    AssumeRole: AssumeRole | None = None


@dataclass
class MskClusterConfig:
    cluster_arn: str | None = None
    """
    The ARN of the MSK Cluster. This will be used to get the cluster details, including bootstrap details.
    """
    iam: Iam | None = None


@dataclass
class GatewayConfiguration:
    gateway_config: dict[str, Any] | None = None
    reporting_config: ReportingConfig | None = None
    topic_include_regexes: Regexes | None = None
    topic_exclude_regexes: Regexes | None = None
    metrics: ClusterMetrics | None = None
    """
    Configure metrics export for the cluster
    """


@dataclass
class ClusterTopicBackupConfig:
    enabled: bool | None = False
    """
    Enable/disable backup of the topics configuration
    """
    S3: S3Output | None = None
    """
    Enables exports to be sent to S3.
    """
    BackupStyles: list[BackupStyle] | None = field(
        default_factory=lambda: [BackupStyle.kafka_topics_sh]
    )
    """
    List the types of backups you want to generate.
    """


@dataclass
class SaveCredentials:
    """
    Optional - If set, will save the generated credentials for the cluster
    """

    aws_secrets_manager: SaaSProviderAwsSecretsManager | None = None


@dataclass
class KafkaServiceAccount:
    name: str | None = "kafka-overwatch"
    """
    Name of the Confluent service account to create
    """
    description: str | None = "kafka-overwatch"
    """
    Service account description
    """
    allow_create: bool | None = True
    """
    If the service account with the ServiceAccountName is not found, creates one. If false and cannot find service account, provider will be failed.
    """
    save_credentials: SaveCredentials | None = None
    """
    Optional - If set, will save the generated credentials for the cluster
    """


@dataclass
class ConfluentProvider:
    """
    Confluent Cloud settings to use to perform the discovery
    """

    confluent_cloud_auth: ConfluentCloudAuth | None = None
    kafka_service_account: KafkaServiceAccount | None = None


@dataclass
class Providers:
    """
    Allows to define a Kafka SaaS provider and perform discovery of existing clusters to scan. (Not yet implemented)
    """

    aiven: Any | None = None
    aws_msk: MskProvider | None = None
    """
    AWS MSK Clusters discovery
    """
    confluent_cloud: ConfluentProvider | None = None
    """
    Confluent Cloud environments & clusters discovery.
    """
    conduktor_gateway: dict[str, GatewayConfiguration] | None = None
    """
    Gateways to monitor and import the vClusters from the partitions usage
    """


@dataclass
class ClusterConfiguration:
    cluster_config: ClusterConfig | MskClusterConfig
    reporting_config: ReportingConfig
    cluster_scan_interval_in_seconds: ClusterScanIntervalInSeconds | None = 60
    """
    Overrides the global setting
    """
    governance_reporting: GovernanceReportingConfig | None = None
    topics_backup_config: ClusterTopicBackupConfig | None = None
    topic_include_regexes: Regexes | None = None
    topic_exclude_regexes: Regexes | None = None
    metrics: ClusterMetrics | None = None
    """
    Configure metrics export for the cluster
    """


@dataclass
class KafkaOverwatchInputConfiguration:
    """
    Specification for Kafka topics/partitions hunter service
    """

    global_: Global | None = None
    """
    Global settings. Defines global default values that can be overriden for each cluster.
    """
    clusters: dict[str, ClusterConfiguration] | None = None
    """
    Kafka clusters to monitor and report on the partitions usage
    """
    providers: Providers | None = None
    """
    Allows to define a Kafka SaaS provider and perform discovery of existing clusters to scan. (Not yet implemented)
    """
    prometheus: Any | None = None
    notification_channels: NotificationChannels | None = None
    """
    Allows to define notification channels for reporting (not yet implemented).
    """
    aws_emf: AwsEmfModel | None = None
