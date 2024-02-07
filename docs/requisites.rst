.. highlight:: shell

=============
Requirements
=============

You will need to deploy/execute the watcher from a network location that has access to the kafka cluster brokers
You will need to have valid credentials in order to connect to the Kafka brokers

Read-only to the cluster, topics & consumer groups is necessary.

Some features require ``DESCRIBE_CONFIG`` on ``Topics`` and ``ConsumerGroups``


.. attention::

    To date, this application does not read any messages. In the future, it might to do some messages metadata sampling,
    in order to provide better recommendations. These will be an opt-in feature.
