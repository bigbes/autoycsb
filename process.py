#!/usr/bin/env python

import os
import re
import json
import os.path
import logging
import requests

from collections import defaultdict

from urllib import urlencode
from pprint import pprint

import yaml

from lib.database import DBClient, DBClientException
from lib.workload import Workload

import math
import operator
import functools

# Logging setup
log = logging.getLogger('main')
log.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s|%(levelname)-5s> %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
log.addHandler(console_handler)

file_handler = logging.FileHandler('process.log')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

def get_version(output):
    version = None
    files = [x for x in os.listdir(output) if x.find('.log') != -1]
    if not files:
        log.info('can\'t find log file')
        return None
    for line in open(os.path.join(output, files[0]), 'r'):
        pos = line.find('version')
        if pos != -1:
            version = line[pos + 8:-1]
    return version

def push(cfg, results):
    """
    Push results into benchmark server
    """
    cfg = cfg.get('export', None)
    if cfg is None:
        log.info('there is no export section in config.yml')
        return
    server, key = cfg.split(':')

    if not server:
        log.info('result server is not specified in config.yml')
    if not key:
        log.info('auth key is not specified in config.yml')
    if not server or not key:
        return

    for version, tab, bench_key, val, unit in results:
        url = 'http://%s/push?%s' % (server, urlencode(dict(
            key=key, name=bench_key, param=str(val),
            v=version, unit=unit, tab=tab
        )))

    pprint(results)

#        resp = requests.get(url)
#        if resp.status_code == 200:
    log.info('pushed %s to result server' % bench_key)
#        else:
#            log.info(
#                "can't push %s to result server: http %d",
#                resp.status_code
#            )

def parse_config(cfg_path, name):
    log.debug('cfg: %s parsing', name)
    with open(cfg_path, 'r') as cfgfile:
        cfg = yaml.load(cfgfile)
    log.debug('cfg: done')
    return cfg

def import_json(fname):
    try:
        parsed_data = json.loads(open(fname, 'r').read())
    except IOError:
        return None
    retval = {}
    runtime = 0
    for k, row in enumerate(parsed_data):
        if row[u'measurement'] == u'RunTime(ms)':
            runtime = int((int(row[u'value']) - 1) / 500) + 1
        if row[u'measurement'].find(u'Return') != -1 and \
                parsed_data[k+1][u'measurement'].find(u'Return') == -1 and \
                runtime != 0:
            n = retval['series ' + row[u'metric']] = {}
            for m in xrange(1, runtime + 1):
                if (k + m == len(parsed_data) or
                        parsed_data[k + m][u'metric'] != row[u'metric']):
                    break
                n[parsed_data[k+m][u'measurement']] = parsed_data[k + m][u'value']
        if row[u'measurement'] == "RunTime(ms)":
            retval[u'RunTime'] = row[u'value'] / 1000;
        if row[u'measurement'] == u'Throughput(ops/sec)':
            retval[row[u'metric'] + u' Throughput'] = row[u'value']
        if row[u'measurement'] == u'AverageLatency(us)':
            retval[row[u'metric'] + u' AvLatency'] = row[u'value']
    return retval

def geometric_mean(lst):
    return math.pow(functools.reduce(operator.mul, lst), float(1)/len(lst))

def process_output_db(cfg, wl, db, output):
    threads = cfg.get('runs', {}).get('threads', [8])
    retries = cfg.get('runs', {}).get('retries', 1)
    clients = None
    log_dir = os.path.join(output, db.name)
    version = get_version(log_dir)
    log.info('Parsing output of %s: %s' % (db.name, repr(version)))
    result = {}
    for thread in threads:
        cls = []
        result_dir = os.path.join(log_dir, str(thread))
        if clients is None:
            clients = set([re.match('(.*)-\d+.output', x).group(1)
                          for x in os.listdir(result_dir)
                          if x.find('.output') != -1])
        for client in clients:
            fls = []
            for attempt in xrange(1, retries + 1):
                fname = '%s-%s.output' % (client, attempt)
                fname = os.path.join(result_dir, fname)
                fl = import_json(fname)
                if fl is not None:
                    fls.append(fl)
            cl = {
                'Throughput': [],
                'AvLatency': defaultdict(list)
            }
            if not fls:
                continue
            pprint(fls)
            for fl in fls:
                for k, v in fl.iteritems():
                    pos = k.find('AvLatency')
                    if pos != -1:
                        cl['AvLatency'][k[:pos - 1]].append(v)
                        continue
                    if k.find('Throughput') != -1:
                        cl['Throughput'].append(v)
                        continue
            pprint(cl)
            for k, v in cl['AvLatency'].iteritems():
                cl['AvLatency'][k] = geometric_mean(v)
            cl['AvLatency'] = dict(cl['AvLatency'])
            cl['Throughput'] = geometric_mean(cl['Throughput'])
            cls.append(cl)
        if (len(cls) == 0):
            log.info('Can\'t find any client logs')
        cl = {
            'Throughput': [],
            'AvLatency': {}
        }
        for k in cls[0]['AvLatency']:
            cl['AvLatency'][k] = geometric_mean([clt['AvLatency'][k] for clt in cls])
        cl['Throughput'] = sum([clt['Throughput'] for clt in cls])
        result[thread] = cl
    return [db.name, db.dbtype, version, result]

def process_output(cfg, wl, dbs):
    output  = cfg.get('ansible', {}).get('output', 'output')
    log_dir = os.path.join(output, wl.internal)

    outlist = []
    for db in dbs:
        result = process_output_db(cfg, wl, db, log_dir)
        if db.dbtype != 'tarantool':
            continue
        db_name = db.name
        db_type = db.dbtype
        db_version = result[2]
        res = result[3]
        for thread, v1 in res.iteritems():
            for k, v in v1['AvLatency'].iteritems():
                outlist.append([db_version, 'ycsb-latency', '.'.join(['ycsb', db_name, str(thread), k.lower()]), v, 'usec'])
            outlist.append([db_version, 'ycsb', '.'.join(['ycsb', db_name, str(thread)]), v, 'rps'])
    pprint(outlist)
    return outlist

def main():
    cfg = parse_config('benchmark.yml', 'bench config')

    timeout   = cfg.get('ansible', {}).get('ansible_timeout', 60)
    output    = cfg.get('ansible', {}).get('output', 'output')

    dbs = [DBClient(v, cfg['databases']['host'], timeout)
           for v in cfg['databases']['list']]

    wls = [Workload(k, v, cfg, timeout, output)
           for k, v in cfg['workloads']['list'].iteritems()]

    outlist = []
    for wl in wls:
        outlist.extend(process_output(cfg, wl, dbs))

    push(cfg, outlist)

    return 0

exit(main())
