import logging

import ansible
from ansible.playbook import PlayBook
from ansible.inventory import Inventory

from pprint import pprint

log = logging.getLogger('main')

def ansible_run(pb):
    results = pb.run()
    failed = False
    for host, info in results.iteritems():
        if info['failures'] != 0:
            log.error("host %s failed", host)
            failed = True
    if failed:
        log.error("failed to continue benchmark")
        return False
    return True

class Workload(object):

    playbook = '15_run_ycsb.yml'

    def __init__(self, name, wl, cfg, timeout, output):
        self.opts = {}
        self.timeout = timeout
        opts = cfg['workloads'].get('params', {})
        opts.update(wl.get('params', {}))
        self.paramify(opts)
        self.workloadfile = wl['workloadfile']
        self.internal = name
        self.opts['wl_internal'] = self.internal
        self.opts['wl_name']   = self.workloadfile

    def paramify(self, pms):
        opts = ' '.join(['-p %s=%s' % (k, v) for k, v in pms.iteritems()])
        if 'wl_props' in self.opts:
            opts = self.opts['wl_props'] + ' ' + opts
        self.opts['wl_props'] = opts

    def prepare(self, db, threads, output):
        opts = self.opts.copy()
        # database specific properties
        opts['threads']   = threads
        opts['db_name']   = db.dbtype
        opts['db_surname']= db.name
        opts['wl_props'] += ' ' + db.get_ycsb_props()
        opts['output']    = output

        opts['wl_type']   = 'load'
        opts['skip_copy'] = True
        opts['wl_internal'] += '_LOAD'

        binv  = ansible.inventory.Inventory('genhostso')
        stats = ansible.callbacks.AggregateStats()
        pb_cb = ansible.callbacks.PlaybookCallbacks(verbose=1)
        rn_cb = ansible.callbacks.PlaybookRunnerCallbacks(stats,
                verbose=ansible.utils.VERBOSITY)

        log.info('PREPARING')
        pb = PlayBook(
            playbook = self.playbook, inventory = binv, forks = 50,
            callbacks = pb_cb, runner_callbacks = rn_cb, stats = stats,
            timeout = self.timeout, any_errors_fatal = True,
            extra_vars = opts
        )
        return ansible_run(pb)

    def run(self, db, threads, attempt, output):
        opts = self.opts.copy()
        # database specific properties
        opts['threads']   = threads
        opts['db_name']   = db.dbtype
        opts['db_surname']= db.name
        opts['wl_props'] += ' ' + db.get_ycsb_props()
        opts['output']    = output

        opts['wl_type']   = 'run'
        opts['skip_copy'] = False
        opts['attempt']   = attempt

        binv  = ansible.inventory.Inventory('genhosts')
        stats = ansible.callbacks.AggregateStats()
        pb_cb = ansible.callbacks.PlaybookCallbacks(verbose=1)
        rn_cb = ansible.callbacks.PlaybookRunnerCallbacks(stats,
                verbose=ansible.utils.VERBOSITY)

        pprint(opts)
        log.info('RUNNING')
        pb = PlayBook(
            playbook = self.playbook, inventory = binv, forks = 50,
            callbacks = pb_cb, runner_callbacks = rn_cb, stats = stats,
            timeout = self.timeout, any_errors_fatal = True,
            extra_vars = opts
        )
        return ansible_run(pb)
