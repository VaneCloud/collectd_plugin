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

from glanceclient import exc as exc
from maas_common import get_auth_ref
from maas_common import get_glance_client
from maas_common import metric
from maas_common import metric_bool
from maas_common import status_err
from maas_common import status_ok
import collectd

CONFIGS = {}
IMAGE_STATUSES = ['active', 'queued', 'killed']
PLUGIN = 'glance_api_local_check'


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
            collectd.warning('glance_api_local_check: Unknown config key: {}'
                             .format(key))
            continue

    auth_ref = get_auth_ref()
    CONFIGS['ip'] = ip
    CONFIGS['auth_ref'] = auth_ref
    CONFIGS['interval'] = interval


def check():
    try:
        GLANCE_ENDPOINT = (
            'http://{ip}:9292/v1'.format(ip=CONFIGS['ip'])
        )

        try:
            if CONFIGS['ip']:
                glance = get_glance_client(endpoint=GLANCE_ENDPOINT)
            else:
                glance = get_glance_client()

            is_up = True
        except exc.HTTPException:
            is_up = False
        # Any other exception presumably isn't an API error
        except Exception as e:
            status_err(str(e))
        else:
            # time something arbitrary
            start = time.time()
            glance.images.list(search_opts={'all_tenants': 1})
            end = time.time()
            milliseconds = (end - start) * 1000
            # gather some metrics
            images = glance.images.list(search_opts={'all_tenants': 1})
            status_count = collections.Counter([s.status for s in images])

        status_ok()
        metric_bool(PLUGIN, 'glance_api_local_status', is_up)

        # only want to send other metrics if api is up
        if is_up:
            metric(PLUGIN,
                   'glance_api_local_response_time',
                   '%.3f' % milliseconds,)
            for status in IMAGE_STATUSES:
                metric(PLUGIN,
                       'glance_%s_images' % status,
                       status_count[status],)
    except:
        metric_bool(PLUGIN, 'glance_api_local_status', False)
        raise


# register callbacks
collectd.register_config(configure_callback)
collectd.register_read(check)
