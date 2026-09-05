#!/usr/bin/env bash

mkdir -p /workspaces/jukeboxsvc/.vscode
cp /workspaces/jukeboxsvc/.devcontainer/vscode/* /workspaces/jukeboxsvc/.vscode

make bootstrap
