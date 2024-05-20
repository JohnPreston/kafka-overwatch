
.. meta::
    :description: Kafka Overwatch
    :keywords: kafka, observability, cost-savings

.. _input_config:

=======================
Input Configuration
=======================

The input configuration is validated against JSON schema to perform early validation of the input configuration.

JSON Schema
=============

Model
---------------

.. jsonschema:: ../kafka_overwatch/specs/config.json


Definition
-----------

.. literalinclude:: ../kafka_overwatch/specs/config.json


Examples
=========

Secrets from AWS
------------------

.. code-block:: yaml

    ---
    # Local testing Kafka configuration

    schema_registries:
      local:
        config:
          schema_registry_url: https://localhost:8083
        schema_registry_scan_interval: 30
        backup_config:
          enabled: true
          backup_strategy:
            as_archive: true
          S3:
            bucket_name: registry-backup-bucket
            prefix_key: schema-registry-backup

    clusters:
      nasa:
        cluster_config:
          schema_registry: local
          kafka:
            bootstrap.servers: kafka.gcn.nasa.gov:9092
            security.protocol: sasl_ssl
            sasl.mechanism: OAUTHBEARER
            sasl.oauthbearer.method: oidc
            sasl.oauthbearer.client.id: "{{resolve:secretsmanager:/kafka/nasa/oidc:SecretString:sasl.oauthbearer.client.id}}"
            sasl.oauthbearer.client.secret: "{{resolve:secretsmanager:/kafka/nasa/oidc:SecretString:sasl.oauthbearer.client.secret}}"
            sasl.oauthbearer.token.endpoint.url: https://auth.gcn.nasa.gov/oauth2/token
            sasl.oauthbearer.scope: gcn.nasa.gov/kafka-public-consumer
            client.id: kafka-overwatch-dev
            acks: all
            socket.keepalive.enable: true
        #        debug: admin,consumer
        reporting_config:
          notification_channels:
            sns:
              - name: default-topic
          exports:
            local: ./nasa_generated_reports
          output_formats:
            pandas_dataframe:
              - csv
              - json
          evaluation_period_in_seconds: 300

    notification_channels:
      sns:
        default-topic:
          topic_arn: arn:aws:sns:eu-west-1:373709687836:kafka-usage-report
