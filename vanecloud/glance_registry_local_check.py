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

from maas_common import get_auth_ref
from maas_common import get_keystone_client
from maas_common import metric
from maas_common import metric_bool
from maas_common import status_err
from maas_common import status_ok
import requests
from requests import exceptions as exc
import collectd

CONFIGS = {}
PLUGIN = 'glance_registry_local_check'


def configure_callback(conf):
    """Receive configuration block"""
    ip = None
    interval = 10
    graphite_host = None
    graphite_port = None

    for node in conf.children:
        key = node.key
        val = node.values[0]

        if key == 'ip':  # Glance Registry IP address
            ip = val
        elif key == 'interval':
            interval = val
        elif key == 'graphite_host':
            graphite_host = val
        elif key == 'graphite_port':
            graphite_port = val
        else:
            collectd.warning('glance_registry_local_check: Unknown config key:\
                             {}'.format(key))
            continue

    auth_ref = get_auth_ref()
    CONFIGS['ip'] = ip
    CONFIGS['auth_ref'] = auth_ref
    CONFIGS['interval'] = interval
    CONFIGS['graphite_host'] = graphite_host
    CONFIGS['graphite_port'] = graphite_port


def check():
    try:
        # We call get_keystone_client here as there is some logic
        # within to get a new token if previous one is bad.
        keystone = get_keystone_client(CONFIGS['auth_ref'])
        auth_token = keystone.auth_token
        registry_endpoint = 'http://{ip}:9191'.format(ip=CONFIGS['ip'])

        s = requests.Session()

        s.headers.update(
            {'Content-type': 'application/json',
             'x-auth-token': auth_token})

        try:
            # /images returns a list of public, non-deleted images
            r = s.get('%s/images' % registry_endpoint, verify=False,
                      timeout=10)
            is_up = r.ok
        except (exc.ConnectionError, exc.HTTPError, exc.Timeout):
            is_up = False
        except Exception as e:
            status_err(str(e))

        status_ok()
        metric_bool(PLUGIN, 'glance_registry_local_status', is_up,
                    graphite_host=CONFIGS['graphite_host'],
                    graphite_port=CONFIGS['graphite_port'])
        # only want to send other metrics if api is up
        if is_up:
            milliseconds = r.elapsed.total_seconds() * 1000
            metric(PLUGIN, 'glance_registry_local_response_time',
                   '%.3f' % milliseconds,
                   graphite_host=CONFIGS['graphite_host'],
                   graphite_port=CONFIGS['graphite_port'])
    except:
        metric_bool(PLUGIN, 'glance_registry_local_status', False,
                    graphite_host=CONFIGS['graphite_host'],
                    graphite_port=CONFIGS['graphite_port'])
        raise


# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(check)
