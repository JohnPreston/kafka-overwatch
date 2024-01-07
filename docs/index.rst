
.. meta::
    :description: Kafka Overwatch
    :keywords: kafka, observability, cost-savings

##########################################
Welcome to Kafka Overwatch documentation
##########################################

|PYPI_VERSION| |PYPI_LICENSE|

|CODE_STYLE| |TDD| |BDD|

|QUALITY|

TL;DR
======

This microservice monitors Kafka topics in intervals, examining offsets, consumer groups, and lag to identify active topics with new messages.
It exposes metrics for validation and generates a user-friendly report, helping users discern actively utilized topics from dormant ones.

It can be monitor multiple Kafka clusters in-parallel, using different configurations and settings.

Features
==========

* Generates a usage report on topics
* Exposes metrics via prometheus

    * Topics count
    * Partitions count
    * Number of new messages (measured with topic offsets)

* AWS Secret integration for client config values

Extras
--------

Here are some extra features that serve additional needs

* Generates commands script to re-create all the topics in case of DR (store local or to S3)



Input configuration
====================

Before running it, you need to define an input configuration file, with the different Kafka clusters you wish to scan.
Head to :ref:`input_config` to check the input specifications.

For example below, as-used in the ``docker-compose.override.yaml``

.. literalinclude:: ../config.local.yaml


Install | Deploy
=================

With docker
-------------

.. code-block::

    docker run --rf -v ${pwd}/config.yaml:/tmp/config/config.yaml public.ecr.aws/johnpreston/kafka-overwatch -c /tmp/config/config.yaml

With python
----------------

.. code-block:: bash

    # Inside a python virtual environment
    python3 -m venv venv
    source venv/bin/activate
    pip install pip -U
    pip install kafka-overwatch

    # For your user only, without virtualenv
    python3 -m pip install kafka-overwatch --user


.. |BUILD| image::


.. |PYPI_VERSION| image:: https://img.shields.io/pypi/v/kafka-overwatch.svg
        :target: https://pypi.python.org/pypi/kafka-overwatch

.. |PYPI_DL| image:: https://img.shields.io/pypi/dm/kafka-overwatch
    :alt: PyPI - Downloads
    :target: https://pypi.python.org/pypi/kafka-overwatch

.. |PYPI_LICENSE| image:: https://img.shields.io/pypi/l/kafka-overwatch
    :alt: PyPI - License
    :target: https://github.com/johnpreston/kafka-overwatch/blob/master/LICENSE

.. |PYPI_PYVERS| image:: https://img.shields.io/pypi/pyversions/kafka-overwatch
    :alt: PyPI - Python Version
    :target: https://pypi.python.org/pypi/kafka-overwatch

.. |PYPI_WHEEL| image:: https://img.shields.io/pypi/wheel/kafka-overwatch
    :alt: PyPI - Wheel
    :target: https://pypi.python.org/pypi/kafka-overwatch

.. |CODE_STYLE| image:: https://img.shields.io/badge/codestyle-black-black
    :alt: CodeStyle
    :target: https://pypi.org/project/black/

.. |TDD| image:: https://img.shields.io/badge/tdd-pytest-black
    :alt: TDD with pytest
    :target: https://docs.pytest.org/en/latest/contents.html

.. |BDD| image:: https://img.shields.io/badge/bdd-behave-black
    :alt: BDD with Behave
    :target: https://behave.readthedocs.io/en/latest/

.. |QUALITY| image:: https://sonarcloud.io/api/project_badges/measure?project=JohnPreston_kafka-overwatch&metric=alert_status
    :alt: Code scan with SonarCloud
    :target: https://sonarcloud.io/project/information?id=JohnPreston_kafka-overwatch

.. |PY_DLS| image:: https://img.shields.io/pypi/dm/kafka-overwatch
    :target: https://pypi.org/project/kafka-overwatch/


.. toctree::
    :maxdepth: 1

    requisites
    installation
    lexicon

.. toctree::
    :maxdepth: 1
    :caption: Configuration & Settings

    config


.. toctree::
    :maxdepth: 1
    :caption: Examples and Help

    examples


.. toctree::
    :titlesonly:
    :maxdepth: 1
    :caption: Modules and Source Code

    modules
    contributing

Indices and tables
==================
* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. meta::
    :description: Kafka Overwatch
    :keywords: kafka, monitoring, observability, cost-saving


.. _YAML Specifications: https://yaml.org/spec/
.. _Extensions fields:  https://docs.docker.com/compose/compose-file/#extension-fields
