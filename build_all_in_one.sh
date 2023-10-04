#!/bin/bash
# Build the docker image
docker build -t aios .
docker tag aios:latest paios/aios:latest
docker push paios/aios:latest
