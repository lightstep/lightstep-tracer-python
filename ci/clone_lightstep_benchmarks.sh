#!/bin/bash

set -e

REPO_URL="https://github.com/lightstep/lightstep-benchmarks.git"
MAJOR_VERSION="0"
MINOR_VERSION="1"

# clone the repo
git clone ${REPO_URL}
cd lightstep-benchmarks

# checkout the newest commit whose tag matches the specified major / minor
# version
MATCHING_VERSIONS=`git tag --sort -version:refname --list "v${MAJOR_VERSION}.${MINOR_VERSION}.*"`
NEWEST_VERSION=`echo ${MATCHING_VERSIONS} | tr '\n' ',' | cut -d ',' -f 1`

git checkout ${NEWEST_VERSION}
