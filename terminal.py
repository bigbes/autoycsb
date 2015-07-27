#!/usr/bin/env python

import os
import re
import json
import yaml
import math
import os.path
import logging
import operator
import requests
import functools

from pprint import pprint
from collections import defaultdict
from terminaltables import AsciiTable

from lib.database import DBClient, DBClientException
from lib.workload import Workload

# Logging setup
log = logging.getLogger('main')
log.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s|%(levelname)-5s> %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
log.addHandler(console_handler)

file_handler = logging.FileHandler('terminal.log')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

def parse_config(cfg_path, name):
    log.info('cfg: %s parsing', name)
    with open(cfg_path, 'r') as cfgfile:
        cfg = yaml.load(cfgfile)
    log.info('cfg: done')
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
                parsed_data[k + 1][u'measurement'].find(u'Return') == -1 and \
                runtime != 0:
            n = retval['series ' + row[u'metric']] = {}
            for m in xrange(1, runtime + 1):
                if (k + m == len(parsed_data) or
                        parsed_data[k + m][u'metric'] != row[u'metric']):
                    break
                n[parsed_data[k + m][u'measurement']] = parsed_data[k + m][u'value']
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
    # version = get_version(log_dir)
    # log.info('Parsing output of %s: %s' % (db.name, repr(version)))
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
            for fl in fls:
                for k, v in fl.iteritems():
                    pos = k.find('AvLatency')
                    if pos != -1:
                        cl['AvLatency'][k[:pos - 1]].append(v)
                        continue
                    if k.find('Throughput') != -1:
                        cl['Throughput'].append(v)
                        continue
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
#    return [db.name, db.dbtype, version, result]
    return result

def process_output(cfg, wl, dbs):
    output  = cfg.get('ansible', {}).get('output', 'output')
    log_dir = os.path.join(output, wl.internal)

    db_list = {}
    for db in dbs:
        result = process_output_db(cfg, wl, db, log_dir)
        thread_list = {}
        for thread, v1 in result.iteritems():
            out = {}
            val = {}
            for k, v in v1['AvLatency'].iteritems():
                if k == 'CLEANUP':
                    continue
                val[k.lower()] = v
            out['latency'] = val
            out['throughput'] = v1['Throughput']
            thread_list[thread] = out
        db_list[db.name] = thread_list
    return db_list

def print_tables(cfg, output_list):
    threads = cfg.get('runs', {}).get('threads', [])
    dbs     = cfg.get('databases', {}).get('list', [])
    dbs     = [db['name'] for db in dbs]
    for wl, m in output_list.iteritems():
        log.info('Workload %s', repr(wl))
        log.info('Latency (In usec, less is better)')
        lat_list = m[dbs[0]][threads[0]]['latency'].keys()
        header = ['DB-Clients\\OP']
        header.extend(lat_list)
        table = [header]
        for thread in threads:
            for db in dbs:
                v = [str(m[db][thread]['latency'][k]) for k in lat_list]
                v.insert(0, '%s-%d' % (db, thread))
                table.append(v)
        log.info('\n' + AsciiTable(table).table)

        log.info('RPS (More is better)')
        header = ['DB\\Threads']
        header.extend([str(thread) for thread in threads])
        table = [header]
        for db in dbs:
            v = [db]
            v.extend([str(int(m[db][thread]['throughput'])) for thread in threads])
            table.append(v)
        log.info('\n' + AsciiTable(table).table)

def main():
    cfg = parse_config('benchmark.yml', 'bench config')

    timeout   = cfg.get('ansible', {}).get('ansible_timeout', 60)
    output    = cfg.get('ansible', {}).get('output', 'output')

    dbs = [DBClient(v, cfg['databases']['host'], timeout)
           for v in cfg['databases']['list']]

    wls = [Workload(k, v, cfg, timeout, output)
           for k, v in cfg['workloads']['list'].iteritems()]

    outlist = {}
    for wl in wls:
        outlist[wl.internal] = process_output(cfg, wl, dbs)

    print_tables(cfg, outlist)

    return 0

if __name__ == '__main__':
    exit(main())
