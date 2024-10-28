#!/usr/bin/env bash

mkdir -p /workspaces/jukeboxsvc/.vscode
cp /workspaces/jukeboxsvc/.devcontainer/vscode/* /workspaces/jukeboxsvc/.vscode

make bootstrap

# this is required for executing remote commands on appstore nodes (e.g. clone_app)
sudo mkdir -p /opt/yag/jukeboxsvc/.ssh
sudo cp -r /workspaces/jukeboxsvc/runtime/secrets/.ssh /opt/yag/jukeboxsvc
sudo chown -R 1000:1000 /opt/yag/jukeboxsvc
sudo chmod 600 /opt/yag/jukeboxsvc/.ssh/*

# TODO: drop after merge: https://github.com/docker/docker-py/pull/3270
patch /workspaces/jukeboxsvc/.venv/lib/python3.11/site-packages/docker/types/services.py /workspaces/jukeboxsvc/patch_docker_services.diff
