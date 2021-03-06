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
from maas_common import metric
from maas_common import metric_bool
from maas_common import status_err
from maas_common import status_ok
from collections import defaultdict as dict

import collectd

CONFIGS = {}
PLUGIN = 'neutron_service_check'


def configure_callback(conf):
    """Receive configuration block"""
    ip = None
    host = None
    interval = 10
    graphite_host = None
    graphite_port = None

    for node in conf.children:
        key = node.key
        val = node.values[0]

        if key == 'ip':  # Cinder API hostname or IP address
            ip = val
        elif key == 'interval':
            interval = val
        elif key == 'host':  # Only return metrics for specified host
            host == host
        elif key == 'graphite_host':
            graphite_host = val
        elif key == 'graphite_port':
            graphite_port = val
        else:
            collectd.warning('neutron_service_check: Unknown config key: {}'
                             .format(key))
            continue

    CONFIGS['ip'] = ip
    CONFIGS['host'] = host
    CONFIGS['interval'] = interval
    CONFIGS['graphite_host'] = graphite_host
    CONFIGS['graphite_port'] = graphite_port


def check():
    try:
        error_num = dict(int)
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
                name = '%s.%s_%s' % (agent['binary'],
                                     agent['host'],
                                     agent['id'])
                if agent['binary'] not in error_num:
                    error_num[agent['binary']] = 0
                if not agent_is_up:
                    error_num[agent['binary']] += 1
            metric_bool(PLUGIN, name, agent_is_up,
                        graphite_host=CONFIGS['graphite_host'],
                        graphite_port=CONFIGS['graphite_port'])
        for k, v in error_num.items():
            metric(PLUGIN, "{}_error_num".format(k), v,
                   graphite_host=CONFIGS['graphite_host'],
                   graphite_port=CONFIGS['graphite_port'])
        metric_bool(PLUGIN, "{}_status".format(PLUGIN), True,
                    graphite_host=CONFIGS['graphite_host'],
                    graphite_port=CONFIGS['graphite_port'])
    except:
        metric_bool(PLUGIN, "{}_status".format(PLUGIN), False,
                    graphite_host=CONFIGS['graphite_host'],
                    graphite_port=CONFIGS['graphite_port'])
        raise


# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(check)
