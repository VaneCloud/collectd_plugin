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
from maas_common import get_nova_client
from maas_common import metric_bool
from maas_common import status_err
from maas_common import status_ok
import collectd

CONFIGS = {}
PLUGIN = 'nova_service_check'


def configure_callback(conf):
    """Receive configuration block"""
    ip = None
    host = None
    interval = 10

    for node in conf.children:
        key = node.key
        val = node.values[0]

        if key == 'ip':  # Nova API hostname or IP address
            ip = val
        elif key == 'interval':
            interval = val
        elif key == 'host':  # Only return metrics for specified host
            host == host
        else:
            collectd.warning('nova_service_check: Unknown config key: {}'
                             .format(key))
            continue

    auth_ref = get_auth_ref()
    CONFIGS['ip'] = ip
    CONFIGS['host'] = host
    CONFIGS['auth_ref'] = auth_ref
    CONFIGS['interval'] = interval


def check():
    try:
        keystone = get_keystone_client(CONFIGS['auth_ref'])
        auth_token = keystone.auth_token
        tenant_id = keystone.tenant_id

        COMPUTE_ENDPOINT = (
            'http://{hostname}:8774/v2/{tenant_id}'
            .format(hostname=CONFIGS['ip'], tenant_id=tenant_id)
        )
        try:
            nova = get_nova_client(auth_token=auth_token,
                                   bypass_url=COMPUTE_ENDPOINT)

        # not gathering api status metric here so catch any exception
        except Exception as e:
            status_err(str(e))

        # gather nova service states
        if CONFIGS['host']:
            services = nova.services.list(host=CONFIGS['host'])
        else:
            services = nova.services.list()

        if len(services) == 0:
            status_err("No host(s) found in the service list")

        # return all the things
        status_ok()
        for service in services:
            service_is_up = True

            if service.status == 'enabled' and service.state == 'down':
                service_is_up = False

            if CONFIGS['host']:
                name = '%s_status' % service.binary
            else:
                name = '%s_on_host_%s_status' % (service.binary, service.host)

            metric_bool(PLUGIN, name, service_is_up)
        metric_bool(PLUGIN, 'nova_service_check_status', True)
    except:
        metric_bool(PLUGIN, 'nova_service_check_status', False)
        raise


# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(check, interval=2)
