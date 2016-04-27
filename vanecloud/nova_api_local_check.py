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

import collections
import time

from maas_common import get_auth_ref
from maas_common import get_keystone_client
from maas_common import get_nova_client
from maas_common import metric
from maas_common import metric_bool
from maas_common import status_err
from maas_common import status_ok
from novaclient.client import exceptions as exc
import collectd

CONFIGS = {}
SERVER_STATUSES = ['ACTIVE', 'STOPPED', 'ERROR']
PLUGIN = 'nova_api_local_check'


def configure_callback(conf):
    """Receive configuration block"""
    ip = None
    interval = 10
    graphite_host = None
    graphite_port = None

    for node in conf.children:
        key = node.key
        val = node.values[0]

        if key == 'ip':
            ip = val
        elif key == 'interval':
            interval = val
        elif key == 'graphite_host':
            graphite_host = val
        elif key == 'graphite_port':
            graphite_port = val
        else:
            collectd.warning('nova_api_local_check: Unknown config key: {}'
                             .format(key))
            continue

    auth_ref = get_auth_ref()
    CONFIGS['ip'] = ip
    CONFIGS['auth_ref'] = auth_ref
    CONFIGS['interval'] = interval
    CONFIGS['graphite_host'] = graphite_host
    CONFIGS['graphite_port'] = graphite_port


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

            is_up = True
        except exc.ClientException:
            is_up = False
        # Any other exception presumably isn't an API error
        except Exception as e:
            status_err(str(e))
        else:
            # time something arbitrary
            start = time.time()
            nova.services.list()
            end = time.time()
            milliseconds = (end - start) * 1000

            servers = nova.servers.list(search_opts={'all_tenants': 1})
            # gather some metrics
            status_count = collections.Counter([s.status for s in servers])

        status_ok()
        metric_bool(PLUGIN, 'nova_api_local_status', is_up,
                    interval=CONFIGS['interval'],
                    graphite_host=CONFIGS['graphite_host'],
                    graphite_port=CONFIGS['graphite_port'])
        # only want to send other metrics if api is up
        if is_up:
            metric(PLUGIN,
                   'nova_api_local_response_time',
                   '%.3f' % milliseconds,
                   interval=CONFIGS['interval'],
                   graphite_host=CONFIGS['graphite_host'],
                   graphite_port=CONFIGS['graphite_port'])
            for status in SERVER_STATUSES:
                metric(PLUGIN, 'nova_instances_in_state_%s' % status,
                       status_count[status],
                       interval=CONFIGS['interval'],
                       graphite_host=CONFIGS['graphite_host'],
                       graphite_port=CONFIGS['graphite_port'])
    except:
        metric_bool(PLUGIN, 'nova_api_local_status', False,
                    interval=CONFIGS['interval'],
                    graphite_host=CONFIGS['graphite_host'],
                    graphite_port=CONFIGS['graphite_port'])
        raise


# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(check)
