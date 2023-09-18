#!/usr/bin/bash

pipreqs ./src --force
# Build the docker image
docker build -t aios .
