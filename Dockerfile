ARG ARCH=
ARG PY_VERSION=3.10-slim
ARG BASE_IMAGE=public.ecr.aws/docker/library/python:$PY_VERSION
ARG LAMBDA_IMAGE=public.ecr.aws/lambda/python:latest

FROM $BASE_IMAGE as builder

WORKDIR /opt
RUN python -m pip install pip -U
RUN pip install poetry
COPY kafka_overwatch /opt/kafka_overwatch
COPY pyproject.toml poetry.lock README.rst LICENSE /opt/
RUN poetry build

FROM $BASE_IMAGE
COPY --from=builder /opt/dist/kafka_overwatch-*.whl /opt/kafka-overwatch/
WORKDIR /opt/kafka-overwatch/

RUN if ! [ -d  /etc/pki/tls/certs/ ]; \
    then mkdir -p /etc/pki/tls/certs/; ln -s /usr/lib/ssl/cert.pem /etc/pki/tls/certs/ca-bundle.crt ;\
    fi
RUN pip install pip -U --no-cache-dir && \
    pip install wheel --no-cache-dir && \
    pip install *.whl --no-cache-dir

RUN groupadd -r app -g 1350 && useradd -u 1350 -r -g app -m -d /app -s /sbin/nologin -c "App user" app

USER app
WORKDIR /tmp
ENTRYPOINT ["kafka-overwatch"]
