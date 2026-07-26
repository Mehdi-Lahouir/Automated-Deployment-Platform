FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

ARG KIND_VERSION=v0.30.0
ARG TARGETARCH=amd64

COPY requirements.txt requirements-dev.txt /tmp/task-manager/

RUN python -m pip install --no-cache-dir \
      -r /tmp/task-manager/requirements-dev.txt \
    && curl --fail --location --silent --show-error \
      --output /usr/local/bin/kind \
      "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-${TARGETARCH}" \
    && chmod +x /usr/local/bin/kind \
    && rm -rf /tmp/task-manager

WORKDIR /workspace
