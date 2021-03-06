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

from keystoneclient.openstack.common.apiclient import exceptions as exc
from maas_common import get_auth_details
from maas_common import get_keystone_client
from maas_common import metric
from maas_common import metric_bool
from maas_common import status_err
from maas_common import status_ok
import collectd

CONFIGS = {}
PLUGIN = 'keystone_api_local_check'


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
            collectd.warning('keystone_api_local_check: Unknown config key: {}'
                             .format(key))
            continue

    auth_details = get_auth_details()
    CONFIGS['ip'] = ip
    CONFIGS['auth_details'] = auth_details
    CONFIGS['interval'] = interval
    CONFIGS['graphite_host'] = graphite_host
    CONFIGS['graphite_port'] = graphite_port


def check():
    try:
        auth_details = CONFIGS['auth_details']
        if auth_details['OS_AUTH_VERSION'] == '2':
            IDENTITY_ENDPOINT = 'http://{ip}:35357/v2.0'\
                                .format(ip=CONFIGS['ip'])
        else:
            IDENTITY_ENDPOINT = 'http://{ip}:35357/v3'.format(ip=CONFIGS['ip'])

        try:
            if CONFIGS['ip']:
                keystone = get_keystone_client(endpoint=IDENTITY_ENDPOINT)
            else:
                keystone = get_keystone_client()

            is_up = True
        except (exc.HttpServerError, exc.ClientException):
            is_up = False
        # Any other exception presumably isn't an API error
        except Exception as e:
            status_err(str(e))
        else:
            # time something arbitrary
            start = time.time()
            keystone.services.list()
            end = time.time()
            milliseconds = (end - start) * 1000

            # gather some vaguely interesting metrics to return
            if auth_details['OS_AUTH_VERSION'] == '2':
                project_count = len(keystone.tenants.list())
                user_count = len(keystone.users.list())
            else:
                project_count = len(keystone.projects.list())
                user_count = len(keystone.users.list(domain='Default'))

        status_ok()
        metric_bool(PLUGIN, 'keystone_api_local_status', is_up,
                    graphite_host=CONFIGS['graphite_host'],
                    graphite_port=CONFIGS['graphite_port'])
        # only want to send other metrics if api is up
        if is_up:
            metric(PLUGIN,
                   'keystone_api_local_response_time',
                   '%.3f' % milliseconds,
                   graphite_host=CONFIGS['graphite_host'],
                   graphite_port=CONFIGS['graphite_port'])
            metric(PLUGIN, 'keystone_user_count', user_count,
                   graphite_host=CONFIGS['graphite_host'],
                   graphite_port=CONFIGS['graphite_port'])
            metric(PLUGIN, 'keystone_tenant_count', project_count,
                   graphite_host=CONFIGS['graphite_host'],
                   graphite_port=CONFIGS['graphite_port'])
    except:
        metric_bool(PLUGIN, 'keystone_api_local_status', False,
                    graphite_host=CONFIGS['graphite_host'],
                    graphite_port=CONFIGS['graphite_port'])
        raise


# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(check)
