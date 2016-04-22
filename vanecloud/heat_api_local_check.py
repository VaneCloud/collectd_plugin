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

import time

from heatclient import exc
from maas_common import get_auth_ref
from maas_common import get_heat_client
from maas_common import get_keystone_client
from maas_common import metric
from maas_common import metric_bool
from maas_common import status_err
from maas_common import status_ok
import collectd

CONFIGS = {}
PLUGIN = 'heat_api_local_check'


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
            collectd.warning('heat_api_local_check: Unknown config key: {}'
                             .format(key))
            continue

    auth_ref = get_auth_ref()
    CONFIGS['ip'] = ip
    CONFIGS['auth_ref'] = auth_ref
    CONFIGS['interval'] = interval


def check():
    keystone = get_keystone_client(CONFIGS['auth_ref'])
    tenant_id = keystone.tenant_id

    HEAT_ENDPOINT = ('http://{ip}:8004/v1/{tenant}'.format
                     (ip=CONFIGS['ip'], tenant=tenant_id))

    try:
        if CONFIGS['ip']:
            heat = get_heat_client(endpoint=HEAT_ENDPOINT)
        else:
            heat = get_heat_client()

        is_up = True
    except exc.HTTPException as e:
        is_up = False
    # Any other exception presumably isn't an API error
    except Exception as e:
        status_err(str(e))
    else:
        # time something arbitrary
        start = time.time()
        heat.build_info.build_info()
        end = time.time()
        milliseconds = (end - start) * 1000

    status_ok()
    metric_bool(PLUGIN, 'heat_api_local_status', is_up)
    if is_up:
        # only want to send other metrics if api is up
        metric(PLUGIN,
               'heat_api_local_response_time',
               '%.3f' % milliseconds,)

# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(check, interval=2)
