#!/bin/bash

set -e

REPO_URL="https://github.com/lightstep/lightstep-benchmarks.git"
MAJOR_VERSION="0"

# clone the repo
git clone ${REPO_URL}
cd lightstep-benchmarks

# copy the tags to the local repo (from all remotes)
git fetch --all --tags

# find most recent release whose tag matches the specified major / minor
# version
MATCHING_VERSIONS=`git tag --sort -version:refname --list "v${MAJOR_VERSION}.*.*"`
NEWEST_VERSION=`echo ${MATCHING_VERSIONS} | tr '\n' ',' | cut -d ',' -f 1`

# checkout the code corresponding to the newest tag
git checkout tags/${NEWEST_VERSION}

# so that we can confirm everything is a-okay
git branch
