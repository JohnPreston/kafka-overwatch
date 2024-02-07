.. meta::
    :description: Kafka Overwatch
    :keywords: kafka, monitoring, observability

============
Installation
============

Stable release
==============

Using docker
-------------

.. code-block:: console

    docker run --rm -v ~/.aws:/root/.aws public.ecr.aws/johnpreston/kafka-overwatch:latest

.. hint::

    Head to https://gallery.ecr.aws/johnpreston/kafka-overwatch to select a particular version if need be.

From Pip
---------

.. warning::

    You must use pip>=21 to have all functionalities work. Simply run

    .. code-block::

        pip install pip -U

To install Kafka Overwatch, run this command in your terminal:

.. code-block:: console

    pip install --user kafka-overwatch

.. hint::

    Highly recommend to create a new python virtualenv in order not to spread on all your machine

    .. code-block:: console

        python -m venv venv
        source venv/bin/activate
        pip install pip -U
        pip install kafka-overwatch

This is the preferred method to install Kafka Overwatch python package, as it will always install the most recent stable release.

If you don't have `pip`_ installed, this `Python installation guide`_ can guides
you through the process.


From sources
============

The sources for Kafka Overwatch can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    $ git clone git://github.com/johnpreston/kafka-overwatch

Or download the `tarball`_:

.. code-block:: console

    $ curl -OJL https://github.com/johnpreston/kafka-overwatch/tarball/main

Once you have a copy of the source, you can install it


Using pip
-----------

.. code-block:: console

    # After git clone
    cd kafka-overwatch
    python -m venv venv
    source venv/bin/activate
    pip install pip -U
    pip install .

Using poetry (recommended for development purposes)
------------------------------------------------------------

.. code-block:: console

    # After git clone
    cd kafka-overwatch
    python -m venv venv
    source venv/bin/activate
    pip install pip -U
    pip install poetry
    poetry install

.. hint::

    Using poetry will also install all the dev dependencies for local dev.

.. _Github repo: https://github.com/johnpreston/kafka-overwatch
.. _tarball: https://github.com/johnpreston/kafka-overwatch/tarball/master
.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/
