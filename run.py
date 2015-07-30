#!/usr/bin/env python

import os
import time
import logging
import os.path
import argparse
from cStringIO import StringIO

import yaml
import ansible
from ansible.playbook import PlayBook
from ansible.inventory import Inventory

from lib.database import DBClient, DBClientException
from lib.workload import Workload

# Logging setup
log = logging.getLogger('main')
log.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s|%(levelname)-5s> %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
log.addHandler(console_handler)

file_handler = logging.FileHandler('run.log')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

def ansible_display(msg, color=None, stderr=False, screen_only=False,
                    log_only=False, runner=None):
    (log.error if stderr else log.info)(msg)

ansible.callbacks.display = ansible_display

def parse_config(cfg_path, name):
    log.debug('cfg: %s parsing', name)
    with open(cfg_path, 'r') as cfgfile:
        cfg = yaml.load(cfgfile)
    log.debug('cfg: done')
    return cfg

def construct_host(cfg_entry):
    dbhost = cfg_entry
    host = dbhost['host']
    user = dbhost.get('user', None)
    port = dbhost.get('port', None)
    opts = dbhost.get('opts', {})
    if user is not None:
        host = '%s@%s' % (user, host)
    if port is not None:
        host = '%s:%s' % (host, port)
    opts = ['%s=%s' % (k, v) for k, v in opts.iteritems() if bool(v) == True]
    opts = ' '.join(opts)
    if opts:
        opts = ' ' + opts
    host = host + opts
    return host

def generate_inventory(cfg, once = False):
    inv = StringIO()
    if not once:
        inv.write('[dbservers]\n')
        inv.write(construct_host(cfg['databases']['host']))
        inv.write('\n\n')
    inv.write('[ycsbservers]\n')
    for v in cfg['workloads']['hosts']:
        inv.write(construct_host(v))
        inv.write('\n')
        if once:
            break
    return inv.getvalue()

def run_wl_db(cfg, wl, db, output):
    threads = cfg.get('runs', {}).get('threads', [8])
    retries = cfg.get('runs', {}).get('retries', 1)
    log_dir = os.path.join(output, db.name)

    db.start()
    wl.prepare(db, 64, os.path.join(log_dir, 'PREP'))

    for thread in threads:
        result_dir = os.path.join(log_dir, str(thread))
        try:
            os.makedirs(result_dir)
        except OSError:
            pass
        for attempt in xrange(1, retries + 1):
            wl.run(db, thread, attempt, result_dir)

    custom = {
        'output': log_dir
    }
    db.fetch_logs(custom)
    db.stop()
    db.cleanup()

def run_workload(cfg, wl, dbs):
    output  = cfg.get('ansible', {}).get('output', 'output')
    log_dir = os.path.join(output, wl.internal)
    try:
        os.makedirs(log_dir)
    except OSError:
        pass

    fh = logging.FileHandler(os.path.join(log_dir, "benchmark.log"))
    fh.setFormatter(formatter)
    log.addHandler(fh)

    for db in dbs:
        run_wl_db(cfg, wl, db, log_dir)

    log.removeHandler(fh)

def parse_args():
    parser = argparse.ArgumentParser(
            description = "YCSB Automation framework")
    parser.add_argument("tests",
                        metavar = "test",
                        nargs   = "*",
                        default = [],
                        help    = """List of tests to run to""")
    parser.add_argument("--hosts",
                        action  = "store_true",
                        default = False,
                        help    = """Generate only hosts file""")
    return parser.parse_args()

def main():
    cfg = parse_config('benchmark.yml', 'bench config')
    args = parse_args()
    print args

    timeout   = cfg.get('ansible', {}).get('ansible_timeout', 60)
    output    = cfg.get('ansible', {}).get('output', 'output')

    with open('hosts', 'w') as f1, open('hostso', 'w') as f2:
        f1.write(generate_inventory(cfg))
        f2.write(generate_inventory(cfg, True))

    log.info("hosts and hostso files are generated")

    if args.hosts:
        return 0

    dbs = [DBClient(v, cfg['databases']['host'], timeout)
           for v in cfg['databases']['list']]

    # for db in dbs:
    #     db.deploy()
    # for db in dbs:
    #     db.start()
    #     db.stop()

    wls = [Workload(k, v, cfg, timeout, output)
           for k, v in cfg['workloads']['list'].iteritems()
           if not args.tests or k in args.tests]
    wls = sorted(wls, key=(lambda x: x.internal))

    log.info('Running tests %s', ', '.join([wl.internal for wl in wls]))
    for wl in wls:
        run_workload(cfg, wl, dbs)

    return 0

exit(main())
