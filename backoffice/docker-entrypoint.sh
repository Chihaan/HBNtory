#!/usr/bin/env sh

set -eu

python bootstrap.py
exec "$@"
