#!/usr/bin/env python

# Copyright 2014, Rackspace US, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re

from maas_common import metric
from maas_common import metric_bool
from maas_common import status_err
from maas_common import status_ok
import memcache

import collectd

CONFIGS = {}
PLUGIN = 'memcached_status'

VERSION_RE = re.compile('STAT version (\d+\.\d+\.\d+)(?![-+0-9\\.])')
VERSIONS = ['1.4.14 (Ubuntu)', '1.4.15']
MEMCACHE_METRICS = {'total_items': 'items',
                    'get_hits': 'cache_hits',
                    'get_misses': 'cache_misses',
                    'total_connections': 'connections'}


def configure_callback(conf):
    """Receive configuration block"""
    ip = None
    port = 11211
    interval = 10

    for node in conf.children:
        key = node.key
        val = node.values[0]

        if key == 'ip':  # memcached IP address
            ip = val
        elif key == 'interval':
            interval = val
        elif key == 'port':  # memcached port.
            port == port
        else:
            collectd.warning('memcached_status: Unknown config key: {}'
                             .format(key))
            continue

    CONFIGS['ip'] = ip
    CONFIGS['port'] = port
    CONFIGS['interval'] = interval


def item_stats(host, port):
    """Check the stats for items and connection status."""

    stats = None
    try:
        mc = memcache.Client(['%s:%s' % (host, port)])
        stats = mc.get_stats()[0][1]
    except IndexError:
        raise
    finally:
        return stats


def main():
    try:
        bind_ip = str(CONFIGS['ip'])
        port = CONFIGS['port']
        is_up = True

        try:
            stats = item_stats(bind_ip, port)
            current_version = stats['version']
        except (TypeError, IndexError):
            is_up = False
        else:
            is_up = True
            if current_version not in VERSIONS:
                status_err('This plugin has only been tested with version %s '
                           'of memcached, and you are using version %s'
                           % (VERSIONS, current_version))

        status_ok()
        metric_bool(PLUGIN, 'memcache_api_local_status', is_up)
        if is_up:
            for m, u in MEMCACHE_METRICS.iteritems():
                metric(PLUGIN, 'memcache_%s' % m, stats[m])
    except:
        metric_bool(PLUGIN, 'memcache_api_local_status', False)
        raise


# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(main)
