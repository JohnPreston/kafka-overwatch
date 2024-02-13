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
