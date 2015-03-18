#!/bin/sh
set -e

# Wait for runlevel 2 (upstart) or 5 (systemd)
while :; do
	runlevel=`runlevel|awk '{print $2}'`
	[ "$runlevel" = 2 -o "$runlevel" = 5 ] && break
	sleep $UVTOOL_WAIT_INTERVAL
done

# Wait for cloud-init's signal
while [ ! -e /var/lib/cloud/instance/boot-finished ]; do sleep $UVTOOL_WAIT_INTERVAL; done
