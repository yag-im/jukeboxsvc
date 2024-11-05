#!/usr/bin/env bash

mkdir -p /workspaces/jukeboxsvc/.vscode
cp /workspaces/jukeboxsvc/.devcontainer/vscode/* /workspaces/jukeboxsvc/.vscode

make bootstrap

# TODO: drop after merge: https://github.com/docker/docker-py/pull/3270
patch /workspaces/jukeboxsvc/.venv/lib/python3.11/site-packages/docker/types/services.py /workspaces/jukeboxsvc/patch_docker_services.diff
