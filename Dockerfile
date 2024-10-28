# syntax=docker/dockerfile:1
FROM python:3.11-bookworm

ARG DEBIAN_FRONTEND=noninteractive

ARG APP_HOME_DIR=/opt/yag/jukeboxsvc

RUN apt update \
    && apt install -y --no-install-recommends \
        gettext-base \
    && rm -rf /var/lib/apt/lists/*

COPY dist/*.whl /tmp/

RUN pip install --upgrade pip \
    && pip install /tmp/*.whl \
    && opentelemetry-bootstrap -a install \
    && rm -rf /tmp/*.whl

# secrets must be in sync with infra/ansible/roles/appstor/files/secrets
COPY runtime/secrets/.ssh ${APP_HOME_DIR}/.ssh

# bin folder contains:
#     cmd.sh: runs gunicorn
#     start.sh: handles graceful shutdown (wraps cmd.sh)
COPY runtime/bin ${APP_HOME_DIR}/bin

# conf folder contains:
#     gunicorn.config.py: needed for OTEL post-fork tracing purposes
COPY runtime/conf ${APP_HOME_DIR}/conf

# TODO: drop after merge: https://github.com/docker/docker-py/pull/3270
COPY patch_docker_services.diff /tmp
RUN patch /usr/local/lib/python3.11/site-packages/docker/types/services.py /tmp/patch_docker_services.diff

ENV APP_HOME_DIR=${APP_HOME_DIR}

CMD $APP_HOME_DIR/bin/start.sh
