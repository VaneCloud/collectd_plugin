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

from maas_common import get_neutron_client
from maas_common import metric_bool
from maas_common import status_err
from maas_common import status_ok

import collectd

CONFIGS = {}
PLUGIN = 'neutron_service_check'


def configure_callback(conf):
    """Receive configuration block"""
    ip = None
    host = None
    interval = 10

    for node in conf.children:
        key = node.key
        val = node.values[0]

        if key == 'ip':  # Cinder API hostname or IP address
            ip = val
        elif key == 'interval':
            interval = val
        elif key == 'host':  # Only return metrics for specified host
            host == host
        else:
            collectd.warning('neutron_service_check: Unknown config key: {}'
                             .format(key))
            continue

    CONFIGS['ip'] = ip
    CONFIGS['host'] = host
    CONFIGS['interval'] = interval


def check():
    try:
        NETWORK_ENDPOINT = 'http://{hostname}:9696'\
                           .format(hostname=CONFIGS['ip'])
        try:
            neutron = get_neutron_client(endpoint_url=NETWORK_ENDPOINT)

        # not gathering api status metric here so catch any exception
        except Exception as e:
            status_err(str(e))

        # gather nova service states
        if CONFIGS['host']:
            agents = neutron.list_agents(host=CONFIGS['host'])['agents']
        else:
            agents = neutron.list_agents()['agents']

        if len(agents) == 0:
            status_err("No host(s) found in the agents list")

        # return all the things
        status_ok()
        for agent in agents:
            agent_is_up = True
            if agent['admin_state_up'] and not agent['alive']:
                agent_is_up = False

            if CONFIGS['host']:
                name = '%s_status' % agent['binary']
            else:
                name = '%s_%s_on_host_%s' % (agent['binary'],
                                             agent['id'],
                                             agent['host'])

            metric_bool(PLUGIN, name, agent_is_up)
        metric_bool(PLUGIN, "{}_status".format(PLUGIN), True)
    except:
        metric_bool(PLUGIN, "{}_status".format(PLUGIN), False)
        raise


# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(check)
