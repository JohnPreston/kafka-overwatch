
.. meta::
    :description: Kafka Overwatch
    :keywords: kafka, observability, cost-savings

##############################
Examples and walk-through
##############################

.. toctree::
    :maxdepth: 1
    :titlesonly:
    :caption: Examples

NASA cluster configuration
============================

The NASA has a public cluster, which decided to use to run a lot of the testing.
See the `NASA Cluster instructions`_ to onboard it and get your credentials.

.. code-block:: yaml

    clusters:
      nasa:
        cluster_config:
          kafka:
            bootstrap.servers: kafka.gcn.nasa.gov:9092
            security.protocol: sasl_ssl
            sasl.mechanisms: OAUTHBEARER
            sasl.oauthbearer.method: oidc
            sasl.oauthbearer.client.id: <NASA OAuth Client ID>
            sasl.oauthbearer.client.secret: <NAS OAuth Client Secret>
            sasl.oauthbearer.token.endpoint.url: https://auth.gcn.nasa.gov/oauth2/token
            sasl.oauthbearer.scope: gcn.nasa.gov/kafka-public-consumer
            client.id: kafka-overwatch-dev
        reporting_config:
          exports:
            local: ./nasa_generated_reports
          output_formats:
            pandas_dataframe:
              - csv
              - json
          evaluation_period_in_seconds: 300


.. _NASA Cluster instructions: https://gcn.nasa.gov/docs/client
