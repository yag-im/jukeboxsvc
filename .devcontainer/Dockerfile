FROM mcr.microsoft.com/devcontainers/python:0-3.11

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
      iputils-ping
