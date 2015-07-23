#!/usr/bin/env python
import os
import time
import yaml
import logging

from lib.database import DBClient, DBClientException
from cStringIO import StringIO
log = logging.getLogger('main')
log.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s|%(levelname)-5s> %(message)s')

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

def main():
    cfg = parse_config('benchmark.yml', 'bench config')
    
    timeout   = cfg.get('ansible', {}).get('ansible_timeout', 60)
    output    = cfg.get('ansible', {}).get('output', 'output')

    with open('genhosts', 'w') as f1, open('genhostso', 'w') as f2:
        f1.write(generate_inventory(cfg))
        f2.write(generate_inventory(cfg, True))

    dbs = [DBClient(v, cfg['databases']['host'], timeout)
           for v in cfg['databases']['list']]

    custom = {
        'output': os.getcwd()
    }
    for db in dbs:
        db.deploy()
        db.start()
        db.stop()
        db.fetch_logs(custom)
#        time.sleep(100)

exit(main())
