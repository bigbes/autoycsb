import time
import errno
import logging

import ansible
from ansible.playbook import PlayBook
from ansible.inventory import Inventory

from pprint import pprint

import socket
import redis
import pylibmc

log = logging.getLogger('main')

def ansible_run(pb):
    results = pb.run()
    time.sleep(1)
    failed = False
    for host, info in results.iteritems():
        if info['failures'] != 0:
            log.error("host %s failed", host)
            failed = True
    if failed:
        log.error("failed to continue benchmark")
        return False
    return True

class DBClientException(Exception):
    pass

def check_redis(db):
    while True:
        try:
            r = redis.Redis(host=db.host, port=db.port)
            if r.info()['loading'] == 0:
                return True
        except redis.ConnectionError:
            pass
        sleep(0.1)
    return False

def check_tarantool(db):
    while True:
        try:
            temp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp.connect((db.host, db.port))
            return True
        except socket.error as e:
            if e.errno == errno.ECONNREFUSED:
                time.sleep(0.1)
                continue
            raise

def check_memcached(db):
    while True:
        try:
            memc  = pylibmc.Client(["%s:%s" % (db.host, db.port)])
            stats = memc.get_stats()
            break
        except socket.error as e:
            if e.errno == errno.ECONNREFUSED:
                time.sleep(0.1)
                continue
            raise
        except pylibmc.SomeErrors as e:
            #pprint(repr(e))
            if repr(e).find('Connection refused') != -1:
                time.sleep(0.1)
                continue
            raise

class DBClient(object):
    params = {
        'tarantool': {
            'pb': '10_tarantool_%s.yml',
            'props': '-p tarantool.host=%s -p tarantool.port=%s',
            'tfunc': check_tarantool
        },
        'redis': {
            'pb': '10_redis_%s.yml',
            'props': '-p redis.host=%s -p redis.port=%s',
            'tfunc': check_redis
        },
        'memcached': {
            'pb': '10_memcached_%s.yml',
            'props': "-p memcached.hosts='%s:%s'",
            'tfunc': check_memcached
        },
##### NYI #####
#        'mongodb': {
#            'pb': '10_mongodb.yml'
#        }
###############
    }

    def __init__(self, db, db_host, timeout):
        self.init = False
        self.name = db['name']
        self.host = db_host['host']
        self.port = db['opts']['port']
        self.opts = db.get('opts', {})
        self.opts['name'] = self.name
        self.timeout = timeout

        self.props = None
        for k in self.params:
            if self.name.find(k) != -1:
                self.dbtype = k
                self.props = self.params[k]
        if self.props is None:
            raise DBClientException('can\'t find DB with name %s' % self.name)

    def base_playbook(self, cmd, custom = None):
        binv  = ansible.inventory.Inventory('genhosts')
        stats = ansible.callbacks.AggregateStats()
        pb_cb = ansible.callbacks.PlaybookCallbacks(verbose=ansible.utils.VERBOSITY)
        rn_cb = ansible.callbacks.PlaybookRunnerCallbacks(stats,
                verbose=ansible.utils.VERBOSITY)

        if custom is None:
            custom = {}
        opts = self.opts.copy()
        opts.update(custom)

        #pprint(opts)

        pb = PlayBook(
            playbook = self.props['pb'] % cmd, inventory = binv,
            forks = len(binv.get_hosts('dbservers')) + 5,
            callbacks = pb_cb, runner_callbacks = rn_cb, stats = stats,
            timeout = self.timeout, any_errors_fatal = True,
            extra_vars = opts
        )
        return ansible_run(pb)

    def deploy(self):
        self.init = True
        return self.base_playbook('deploy')

    def start(self):
        if not self.init:
            return False
        stat = self.base_playbook('start')
        self.props['tfunc'](self)
        return stat

    def stop(self):
        if not self.init:
            return False
        return self.base_playbook('stop')

    def cleanup(self):
        if not self.init:
            return False
        return self.base_playbook('cleanup')

    def destroy(self):
        if not self.init:
            return False
        self.init = False
        return self.base_playbook('destroy')

    def fetch_logs(self, custom):
        if not self.init:
            return False
        return self.base_playbook('fetch_logs', custom)

    def __del__(self):
        self.stop()

    def get_ycsb_props(self):
        return self.props['props'] % (self.host, self.port)

