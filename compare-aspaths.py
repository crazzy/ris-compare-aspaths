#!/usr/bin/env python

import argparse
import numpy
import os
import sys
from apiclient import APIClient
from bisect import bisect
from datetime import date, datetime, timedelta
from dateutil.rrule import rrule, HOURLY
from ipaddress import IPv4Network, IPv6Network


# RIPE RIS updates dumps every 8th hour
# And whatever timestamp is sent in, gets BGP state
# relative to the latest dump
RIPE_RIS_INTERVAL = 8

# Default number of dumps back in time to compare with
RIPE_RIS_DEFAULT_N_DUMPS_BACK = 3

# Self-explanatory, is a constant just for the purpose of
# not having a magic number in the middle of the code
HOURS_PER_DAY = 24

# Base URL for the RIPEStat API
RIPE_STAT_BASE_URL = 'https://stat.ripe.net/data/'


# Small class implementing the RIPEStat API
# Probably not in full, but enough for this use-case
class RIPEstat(APIClient):
    VALID_RESP_CODE = [200]
    sourceapp = None
    BASEURL = ""

    def __init__(self, baseurl=None):
        if baseurl:
            self.BASEURL = baseurl
        self.sourceapp = os.path.basename(__file__)
        super().__init__()

    def __querystring(self, method, params):
        params_str = "sourceapp={}".format(self.sourceapp)
        if method != 'get':
            return params_str
        if params:
            for k, v in params.items():
                params_str += "&{}={}".format(k, v)
        return params_str

    def __url(self, datacall, qs):
        return "{}{}/data.json?{}".format(self.BASEURL, datacall, qs)

    def __response(self, res):
        if res.status_code in self.VALID_RESP_CODE:
            return res.json()
        else:
            return None

    def get(self, datacall, params=None):
        url = self.__url(datacall, self.__querystring('get', params))
        res = super().get(url)
        return self.__response(res)


# Function definitions
def ris_get_dump_times():
    n_dumps_per_day = HOURS_PER_DAY / RIPE_RIS_INTERVAL
    return list(rrule(
        HOURLY,
        interval=RIPE_RIS_INTERVAL,
        dtstart=date.today(),
        count=n_dumps_per_day * args[0].n)
    )


def ris_get_last_dump_datetime():
    times = ris_get_dump_times()
    dt = datetime.now() - timedelta(hours=RIPE_RIS_INTERVAL * args[0].n)
    return times[bisect(times, dt)]


def ris_format_timestamp(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


def ris_get_bgp_state(resource, timestamp):
    r = RIPEstat(baseurl=RIPE_STAT_BASE_URL)
    kwargs = {
        'resource': resource,
        'timestamp': timestamp
    }
    return r.get('bgp-state', kwargs)


def ris_compare_aspaths(then, now):
    then_paths = {}
    now_paths = {}
    for bgp_state in then['data']['bgp_state']:
        then_paths[bgp_state['source_id']] = bgp_state['path']
    for bgp_state in now['data']['bgp_state']:
        now_paths[bgp_state['source_id']] = bgp_state['path']
    for source_id, path in then_paths.items():
        if source_id not in now_paths.keys():
            continue
        if not lists_equal(path, now_paths[source_id]):
            print("{: >35} --> {: >35}".format(
                " ".join(map(str, path)),
                " ".join(map(str, now_paths[source_id]))
            ))


# Using numpy here in the interest of speed
# A pure python implementation would be super slow
def lists_equal(a, b):
    if len(a) != len(b):
        return False
    return numpy.all(numpy.asarray(a) == numpy.asarray(b))


def validate_target(target):
    if '/' not in target:  # Not a prefix
        return False
    if ':' in target:  # We assume IPv6 here and IPv4 otherwise
        try:
            IPv6Network(target)
        except ValueError:
            return False
    else:
        try:
            IPv4Network(target)
        except ValueError:
            return False
    return True


# We begin by parsing the arguments
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Compare the AS-paths to a chosen <target> between a certain timepoint backwards in time and now, display those that differs.', formatter_class=argparse.RawDescriptionHelpFormatter, epilog='''
Note that <target> is a BGP prefix, so using k-root (193.0.14.129) as an example, one would set the target as 193.0.14.0/24 which is the BGP prefix covering that IP address.

If you are unsure what the BGP prefix covering an IP you're interested in you can generally just do a whois on the IP and get the route object which will tell you what *should* be in the BGP table. But you can also search here: https://stat.ripe.net/app/launchpad which will tell you exactly what's in the BGP table.

Examples:

# Compare as-paths between 1 RIS-dump back in time and now for k-root :
%(prog)s -n 1 193.0.14.0/24

# Compare as-paths between 5 RIS-dumps back in time and now for k-root :
%(prog)s -n 5 193.0.14.0/24

# The default is is set to 3 RIS-dumps back in time, so same example using the default :
%(prog)s 193.0.14.0/24
''')
    parser.add_argument(
        '-n',
        help='The number of RIS dumps back in time to compare with.',
        type=int,
        default=RIPE_RIS_DEFAULT_N_DUMPS_BACK
    )
    parser.add_argument(
        'target',
        help='The target BGP prefix to compare AS-paths for.'
    )
    parser.format_help()
    args = parser.parse_known_args()
    if not validate_target(args[0].target):
        parser.print_help(sys.stderr)
        sys.exit(1)

    # Argument parsing done, now getting timestamps
    now = ris_format_timestamp(datetime.now())
    then = ris_format_timestamp(ris_get_last_dump_datetime())

    # Fetching the data from RIPE RIS
    then_res = ris_get_bgp_state(args[0].target, then)
    now_res = ris_get_bgp_state(args[0].target, now)

    # Doing the comparison
    ris_compare_aspaths(then_res, now_res)
    sys.exit(0)
