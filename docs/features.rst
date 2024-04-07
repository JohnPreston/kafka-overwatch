.. meta::
    :description: Kafka Overwatch
    :keywords: kafka, observability, cost-savings

.. _features:

=============
Reporting
=============

All the different aspects of the report are put together into a single file.

.. hint::

    The report is generated to file by default, can be uploaded to AWS S3 too!


Usage report
=============

The usage report will provide with the total number of topics, number of partitions, then an estimation of the overall
partitions waste.

The report is broken down into categories:

* most used topics: all things relative, these are topics which have active consumer groups and new messages during the evaluation window.
* empty topics: topics (with the partition count) that received no messages, and have no consumer group
* empty topics with more than 1 partition, no active CG: the topics that you should really consider recreating down


Governance report
==================

Topic naming convention
-------------------------

You can define regular expressions to capture the topic names that comply to a naming convention.
The report will provide a percentage of topics that are compliant, and a list of all the topics that have not
matched the naming convention.

.. hint::

    You can also define exclude regexes, which will take out the topic from the evaluation rule. This can be useful
    for ``__kafka_internal`` topics and such.


Topics Config backup
=====================

Whilst the topics are scanned and configuration is retrieved, this generates a script that will allow you to recreate
all the existing topics in your cluster with the non-default configuration it has.

======================
Schema Registry (SR)
======================

.. note::

    2024-04 - Implemented for Confluent Schema Registry style only.

Purpose
==============

This feature will allow to define a series of Schema Registries to monitor. These schema registries are not bound to
any one cluster, therefore the features for them will work independently from the Kafka clusters.

Prometheus metrics will report statistics on the Schema Registries each.

If you link a SR to a Kafka cluster, this will then enable to generate Schema Registry usage report.
Specifically, we are trying to identify all the subjects that would not have a matching topic.

.. note::

    Please take this carefully as, this only works with the default Schema naming strategy, ``TopicNameStrategy``.
    If you have subject names which are used in topics with ``RecordNameStrategy`` or ``TopicRecordNameStrategy``,
    these subjects might be in-use.


.. seealso::

    `Schema Registry & Naming strategy`_

Mechanism
===========

You can define one or several schema registries depending on your need. Each schema registry will be independent from
others, allowing you to perform tasks independently.

Each schema registry is processed in its own python process, allowing for each of them to different timings and such.
This is useful if you have a schema registry with a lot of subjects & schemas and others, much smaller, which wouldn't
take as much time to process.

.. attention::

    Due to how processes work, being in different memory spaces, in order to have the evaluation rules work properly with
    the Kafka clusters, the schema registry object is pickled and stored to a `mmap`_ file on disk.

    Given that you have to provide, for some registries, basic authentication details, these details are encrypted with
    a runtime key which will deny someone to access the values stored in the mmap file.

    The mmap file is stored in a folder managed with `tempfile.TemporaryDirectory`_ which will delete
    all files in said directory when the process finishes.


.. _mmap: https://docs.python.org/3/library/mmap.html
.. _tempfile.TemporaryDirectory: https://docs.python.org/3/library/tempfile.html#tempfile.TemporaryDirectory
.. _Schema Registry & Naming strategy: https://docs.confluent.io/platform/current/schema-registry/fundamentals/serdes-develop/index.html#subject-name-strategy
