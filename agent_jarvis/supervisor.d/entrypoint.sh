#!/bin/bash

set -eux

mkdir /var/core -p
mkdir /root/jarvis/supervisor_log -p

exec supervisord -c /etc/supervisord.conf -n
