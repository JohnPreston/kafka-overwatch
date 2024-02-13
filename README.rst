========================================
kafka-overwatch
========================================

What started as a simple CLI/Service to evaluate Kafka cluster topics which have no activity,
ended up being a somewhat comprehensive way to monitor Kafka cluster activities.

Takes a configuration file as input, where you can list one or multiple cluster(s) you wish to monitor.

After a set period of time, it can produce a report (to local disk or AWS S3) with the list of topics that haven't seen any activity.
It also exposes metrics via a prometheus endpoint.

Usage
========

.. code-block::

    kafka-overwatch -c config.local.yaml

Features
==========

* Supports evaluating multiple Kafka clusters at once
* Generates a report on topic usage based on topic watermarks offsets (store local or to S3)
* Generates commands script to re-create all the topics in case of DR (store local or to S3)

* Exposes metrics via prometheus

    * Topics count
    * Partitions count
    * Number of new messages (measured with topic offsets)

* AWS Secret integration for client config values

Upcoming
----------

* Schema Registry integration
* Multi-nodes awareness (split the load with multiple nodes)
* `cfn-kafka-admin`_ output format
* topic messages meta-data analysis (i.e are messages compressed?)
* scripts to perform cleanup
* Recommendations generated from/based on models
* Conduktor Gateway vClusters auto-discovery


Configuration
===============

Whilst a much more comprehensive documentation is yet to be written, please look at ``kafka_overwatch/specs/config.json``
which is used with `jsonschema`_ to perform validation of the input.

Misc
=====

Thanks
-------

Thanks to the Apache Kafka OpenSource community for their continuous efforts in making the eco-system great.
Thanks to the `NASA`_ for having a public cluster to run tests with

Note
-----

Inspired by `kafka-idle-topics`_, yet completely re-written to be a continuous monitoring of the topics,
similar to `cruise-control`_.

.. _EMF: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Embedded_Metric_Format_Specification.html
.. _kafka-idle-topics: https://github.com/abraham-leal/kafka-idle-topics
.. _cfn-kafka-admin: https://github.com/compose-x/cfn-kafka-admin
.. _cruise-control: https://github.com/linkedin/cruise-control
.. _jsonschema: https://pypi.org/project/jsonschema/
.. _NASA: https://www.nasa.gov/


Status
=======

Images build status

|BUILD|

Docs build status

|DOCS_BUILD|


.. |BUILD| image:: https://codebuild.eu-west-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiU3RHQnZ2eFpnQTlOSmU2MUM3NDB5NW9uMDY2TS9DZXBWZ2hmejdoK2xJRStHK2Fhd3FkS1FoQjJOSTcvYjVBNkFTTW5kVDNZK0NqZEthU3gveFpOVEljPSIsIml2UGFyYW1ldGVyU3BlYyI6IjlUbE0vNmpPQU92U1o0SmkiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=main

.. |DOCS_BUILD| image:: https://codebuild.eu-west-1.amazonaws.com/badges?uuid=eyJlbmNyeXB0ZWREYXRhIjoiSVNBZkVSUkx1NHhtamlqSEJqempIdHd2aVNqV2RkTTFVYlphUzJ2ekprOVU4ODZ4cUNWcTNVSkRVM2ovcGFyak5NTTNJZ1Vra2ErSzVOdi84TkVLOUp3PSIsIml2UGFyYW1ldGVyU3BlYyI6IjAvK25MSmNPcjNScVpwdTQiLCJtYXRlcmlhbFNldFNlcmlhbCI6MX0%3D&branch=main
