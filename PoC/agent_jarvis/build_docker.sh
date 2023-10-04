#!/usr/bin/env bash

ROOT=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd "${ROOT}"

imageName="jarvis"
docker build -f dockerfile  -t ${imageName} ..
