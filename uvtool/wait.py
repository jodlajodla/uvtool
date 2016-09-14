# Copyright (C) 2013 Canonical Ltd.
# Author: Robie Basak <robie.basak@canonical.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function
from __future__ import unicode_literals

import argparse
import contextlib
import functools
import os
import socket
import sys
import time

import pyinotify

import uvtool.libvirt
from uvtool.libvirt import (
    LIBVIRT_DNSMASQ_LEASE_FILE,
    LIBVIRT_DNSMASQ_STATUS_FILE
)

SSH_PORT = 22


class ProcessEvent(pyinotify.ProcessEvent):
    def _uvtool_process_generic(self, event):
        if event.pathname in self._uvtool_watch_files:
            self._uvtool_modified = True

    process_IN_MODIFY = _uvtool_process_generic
    process_IN_MOVED_TO = _uvtool_process_generic


class LeaseModifyWaiter(object):
    def __init__(self, watch_files=None):
        if watch_files is None:
            self.watch_files = frozenset([
                LIBVIRT_DNSMASQ_LEASE_FILE,
                LIBVIRT_DNSMASQ_STATUS_FILE,
            ])
        else:
            self.watch_files = watch_files

        self.wm = pyinotify.WatchManager()
        self.process_event = ProcessEvent()
        # API-by-inheritence: must avoid namespace collision, and told
        # by upstream not to override __init__, so cannot provide parameters.
        # So we initialise here. What a hack. This is why I consider
        # API-by-inheritence in dynamic languages (where subclasses share the
        # same attribute namespace) harmful.
        self.process_event._uvtool_watch_files = self.watch_files
        self.process_event._uvtool_modified = False
        self.notifier = pyinotify.Notifier(self.wm, self.process_event)


    def start_watching(self):
        watched_dirs = set()
        for f in self.watch_files:
            if os.path.exists(f):
                self.wm.add_watch(f, pyinotify.IN_MODIFY)
            parent_path = os.path.dirname(f)
            if parent_path not in watched_dirs:
                self.wm.add_watch(parent_path, pyinotify.IN_MOVED_TO)
                watched_dirs.add(parent_path)

    def wait(self, timeout):
        # Should use CLOCK_MONOTONIC here, but it is only available since
        # Python 3.3.
        deadline = time.time() + timeout

        remaining_time = deadline - time.time()
        while remaining_time > 0:
            if self.notifier.check_events(timeout=(remaining_time*1000)):
                self.notifier.read_events()
                self.notifier.process_events()
                if self.process_event._uvtool_modified:
                    return True
            remaining_time = deadline - time.time()
        return False

    def close(self):
        self.wm.close()


def lease_has_mac(mac):
    return uvtool.libvirt.mac_to_ip(mac) is not None


def wait_for_libvirt_dnsmasq_lease(mac, timeout):
    # Shortcut check to save inotify setup
    if lease_has_mac(mac):
        return True

    timeout_time = time.time() + timeout
    waiter = LeaseModifyWaiter()
    with contextlib.closing(waiter):
        waiter.start_watching()
        # Check after we've set up a watch to avoid the race of something
        # happening between the last check and the watch starting
        if lease_has_mac(mac):
            return True
        current_time = time.time()
        while current_time < timeout_time:
            remaining_time_to_timeout = timeout_time - current_time
            waiter.wait(timeout=remaining_time_to_timeout)
            if lease_has_mac(mac):
                return True
            current_time = time.time()
        return False


def has_open_ssh_port(host, timeout=4):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    with contextlib.closing(s):
        s.settimeout(timeout)
        try:
            s.connect((host, SSH_PORT))
        except:
            return False
        else:
            return True


def poll_for_true(fn, interval, timeout):
    timeout_time = time.time() + timeout
    while time.time() < timeout_time:
        if fn():
            return True
        # This could do with a little more care to ensure that we never
        # sleep beyond timeout_time.
        time.sleep(interval)
    return False


def wait_for_open_ssh_port(host, interval, timeout):
    return poll_for_true(
        functools.partial(has_open_ssh_port, host),
        interval, timeout
    )


def main_libvirt_dnsmasq_lease(parser, args):
    if not wait_for_libvirt_dnsmasq_lease(mac=args.mac, timeout=args.timeout):
        print("cloud-wait: timed out", file=sys.stderr)
        sys.exit(1)


def main_ssh(parser, args):
    if not wait_for_open_ssh_port(args.host, args.interval, args.timeout):
        print("cloud-wait: timed out", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=float, default=120.0)
    subparsers = parser.add_subparsers()

    libvirt_dnsmasq_lease_parser = subparsers.add_parser(
        'libvirt-dnsmasq-lease')
    libvirt_dnsmasq_lease_parser.set_defaults(func=main_libvirt_dnsmasq_lease)
    libvirt_dnsmasq_lease_parser.add_argument('mac')

    ssh_parser = subparsers.add_parser('ssh')
    ssh_parser.set_defaults(func=main_ssh)
    ssh_parser.add_argument('--interval', type=float, default=8.0)
    ssh_parser.add_argument('host')

    args = parser.parse_args()
    args.func(parser, args)


if __name__ == '__main__':
    main()
