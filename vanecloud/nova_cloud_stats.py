#!/usr/bin/env python

# Copyright 2015, Rackspace US, Inc.
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

import collections

from maas_common import get_auth_ref
from maas_common import get_keystone_client
from maas_common import get_nova_client
from maas_common import metric
from maas_common import metric_bool
from maas_common import status_err
from maas_common import status_ok

import collectd

CONFIGS = {}
PLUGIN = 'nova_cloud_stats'

# The actual stat names from novaclient are nasty, so this mapping is used to
# translate them to something more consistent and usable, as well as set the
# units for each metric
stats_mapping = {
    'hypervisor_count': {
        'stat_name': 'count', 'unit': 'hypervisors', 'type': 'uint32'
    },
    'total_disk_space': {
        'stat_name': 'local_gb', 'unit': 'Gigabytes', 'type': 'uint32'
    },
    'used_disk_space': {
        'stat_name': 'local_gb_used', 'unit': 'Gigabytes', 'type': 'uint32'
    },
    'free_disk_space': {
        'stat_name': 'free_disk_gb', 'unit': 'Gigabytes', 'type': 'uint32'
    },
    'total_memory': {
        'stat_name': 'memory_mb', 'unit': 'Megabytes', 'type': 'uint32'
    },
    'used_memory': {
        'stat_name': 'memory_mb_used', 'unit': 'Megabytes', 'type': 'uint32'
    },
    'free_memory': {
        'stat_name': 'free_ram_mb', 'unit': 'Megabytes', 'type': 'uint32'
    },
    'total_vcpus': {
        'stat_name': 'vcpus', 'unit': 'vcpu', 'type': 'uint32'
    },
    'used_vcpus': {
        'stat_name': 'vcpus_used', 'unit': 'vcpu', 'type': 'uint32'
    }
}


def configure_callback(conf):
    """Receive configuration block"""
    ip = None
    interval = 10

    for node in conf.children:
        key = node.key
        val = node.values[0]

        if key == 'ip':
            ip = val
        elif key == 'interval':
            interval = val
        else:
            collectd.warning('nova_cloud_stats: Unknown config key: {}'
                             .format(key))
            continue

    auth_ref = get_auth_ref()
    CONFIGS['ip'] = ip
    CONFIGS['auth_ref'] = auth_ref
    CONFIGS['interval'] = interval


def check():
    try:
        keystone = get_keystone_client(CONFIGS['auth_ref'])
        tenant_id = keystone.tenant_id

        COMPUTE_ENDPOINT = (
            'http://{ip}:8774/v2/{tenant_id}'.format(ip=CONFIGS['ip'],
                                                     tenant_id=tenant_id)
        )

        try:
            if CONFIGS['ip']:
                nova = get_nova_client(bypass_url=COMPUTE_ENDPOINT)
            else:
                nova = get_nova_client()

        except Exception as e:
            status_err(str(e))
        else:
            # get some cloud stats
            stats = nova.hypervisor_stats.statistics()
            cloud_stats = collections.defaultdict(dict)
            for metric_name, vals in stats_mapping.iteritems():
                cloud_stats[metric_name]['value'] = \
                    getattr(stats, vals['stat_name'])
                cloud_stats[metric_name]['unit'] = \
                    vals['unit']
                cloud_stats[metric_name]['type'] = \
                    vals['type']

        status_ok()
        for metric_name in cloud_stats.iterkeys():
            metric(PLUGIN,
                   'cloud_resource_%s' % metric_name,
                   cloud_stats[metric_name]['value'],
                   interval=CONFIGS['interval'])
    except:
        metric_bool(PLUGIN, 'nova_cloud_stats', False,
                    interval=CONFIGS['interval'])
        raise


# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(check, interval=2)
