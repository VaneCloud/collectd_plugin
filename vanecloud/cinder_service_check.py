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

# Technically maas_common isn't third-party but our own thing but hacking
# consideres it third-party
from maas_common import get_auth_ref
from maas_common import get_keystone_client
from maas_common import metric_bool
from maas_common import status_err
from maas_common import status_ok
import requests
from requests import exceptions as exc

# NOTE(mancdaz): until https://review.openstack.org/#/c/111051/
# lands, there is no way to pass a custom (local) endpoint to
# cinderclient. Only way to test local is direct http. :sadface:


import collectd

CONFIGS = {}
PLUGIN = 'cinder_service_check'


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
            collectd.warning('cinder_service_check: Unknown config key: {}'
                             .format(key))
            continue

    auth_ref = get_auth_ref()
    CONFIGS['ip'] = ip
    CONFIGS['host'] = host
    CONFIGS['auth_ref'] = auth_ref
    CONFIGS['interval'] = interval
    CONFIGS['graphite_host'] = graphite_host
    CONFIGS['graphite_port'] = graphite_port


def check():
    try:
        keystone = get_keystone_client(CONFIGS['auth_ref'])
        auth_token = keystone.auth_token

        VOLUME_ENDPOINT = (
            'http://{hostname}:8776/v1/{tenant}'
            .format(hostname=CONFIGS['ip'], tenant=keystone.tenant_id)
        )

        s = requests.Session()

        s.headers.update(
            {'Content-type': 'application/json',
             'x-auth-token': auth_token})

        try:
            # We cannot do /os-services?host=X as cinder returns a hostname of
            # X@lvm for cinder-volume binary
            r = s.get('%s/os-services' % VOLUME_ENDPOINT,
                      verify=False, timeout=10)
        except (exc.ConnectionError,
                exc.HTTPError,
                exc.Timeout) as e:
            status_err(str(e))

        if not r.ok:
            status_err('Could not get response from Cinder API')

        services = r.json()['services']

        # We need to match against a host of X and X@lvm (or whatever backend)
        if CONFIGS['host']:
            backend = ''.join((CONFIGS['host'], '@'))
            services = [service for service in services
                        if (service['host'].startswith(backend) or
                            service['host'] == CONFIGS['host'])]

        if len(services) == 0:
            status_err('No host(s) found in the service list')

        status_ok()

        if CONFIGS['host']:
            all_services_are_up = True

            for service in services:
                service_is_up = True

                if service['status'] == 'enabled' and service['state'] != 'up':
                    service_is_up = False
                    all_services_are_up = False

                if '@' in service['host']:
                    [host, backend] = service['host'].split('@')
                    name = '%s.%s_status' % (service['binary'], backend)
                    metric_bool(PLUGIN, name, service_is_up,
                                graphite_host=CONFIGS['graphite_host'],
                                graphite_port=CONFIGS['graphite_port'])

            name = '%s_status' % service['binary']
            metric_bool(PLUGIN, name, all_services_are_up,
                        graphite_host=CONFIGS['graphite_host'],
                        graphite_port=CONFIGS['graphite_port'])
        else:
            for service in services:
                service_is_up = True
                if service['status'] == 'enabled' and service['state'] != 'up':
                    service_is_up = False

                name = '%s.%s' % (service['binary'], service['host'])
                metric_bool(PLUGIN, name.replace('@', '_'), service_is_up,
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
