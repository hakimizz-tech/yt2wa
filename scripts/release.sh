#!/usr/bin/env bash
# Build the wheel and the Docker image for the current version.
set -euo pipefail

version="$(python -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')"
python -m pip install --quiet build
python -m build
docker build -t "yt2wa:${version}" .
echo "Built yt2wa ${version}"
