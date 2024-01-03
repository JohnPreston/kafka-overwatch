# generated by datamodel-codegen:
#   filename:  report.json

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Metadata:
    timestamp: str
    """
    Time the report was generated at
    """


@dataclass
class ConsumerGroups:
    total: int
    """
    Total number of consumer groups
    """
    active: Optional[int] = None
    """
    Number of active consumer groups (lag = 0) & members > 0
    """
    inactive: Optional[int] = None
    """
    Number of inactive consumer groups (lag > 0) or groups without members
    """


@dataclass
class Statistics:
    topics: int
    """
    Total count of topics counted at the time of generating the report
    """
    partitions: Optional[int] = None
    """
    Sum of partitions for the topics
    """
    consumer_groups: Optional[ConsumerGroups] = None


@dataclass
class EstimatedWaste:
    topics: Optional[int] = None
    partitions: Optional[int] = None
    """
    Sum of partitions for the topics
    """


@dataclass
class NewMessagesObserved:
    count: int
    """
    Number of new messages observed, as per offset ends changed
    """
    elapsed_time: int
    """
    Amount of time in seconds passed for the evaluation
    """


@dataclass
class Consumption:
    active_consumer_groups_count: Optional[int] = None
    """
    Number of active consumer groups (lag = 0)
    """
    inactive_consumer_groups_count: Optional[int] = None
    """
    Number of inactive consumer groups (lag > 0) or groups without members
    """


@dataclass
class Recommendation:
    description: Optional[str] = None
    """
    Recommendation for the topic
    """
    suggested_actions: Optional[List[str]] = None
    """
    List of suggested actions
    """


@dataclass
class Topic:
    partitions_count: int
    """
    Number of partitions for the topic
    """
    new_messages_observed: NewMessagesObserved
    consumption: Optional[Consumption] = None
    recommendation: Optional[Recommendation] = None


@dataclass
class ClusterReport:
    cluster_name: str
    metadata: Metadata
    topics: Dict[str, Topic]
    statistics: Optional[Statistics] = None
    estimated_waste: Optional[EstimatedWaste] = None


@dataclass
class ClusterUsageReportStructure:
    """
    Defines the format of the cluster topics report
    """

    cluster: Optional[ClusterReport] = None
