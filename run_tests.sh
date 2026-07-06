#!/bin/bash
set -e
docker build -f Dockerfile.test -t data-sources-test .
docker run --rm data-sources-test "$@"
