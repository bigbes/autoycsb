#!/usr/bin/env python

import ansible
import logging

# Logging setup
log = logging.getLogger('main')
log.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s|%(levelname)-5s> %(message)s')

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
log.addHandler(console_handler)

file_handler = logging.FileHandler('all.log')
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

ansible.callbacks.display = ansible_display

def ansible_display(msg, color=None, stderr=False, screen_only=False,
                    log_only=False, runner=None):
    (log.error if stderr else log.info)(msg)

def parse_config(cfg_path, name):
    log.debug('cfg: %s parsing', name)
    with open(cfg_path, 'r') as cfgfile:
        cfg = yaml.load(cfgfile)[0]
    log.debug('cfg: done')

def run_workload(wl, output):
    result_dir = os.path.join(output, wl['internal'])
    client_dir = os.path.join('roles', 'client', 'files')
    os.mkdir(result_dir)

    fh = logging.FileHandler(os.path.join(result_dir, "benchmark.log"))
    fh.setFormatter(formatter)
    log.addHandler(fh)

    inv   = ansible.inventory.Inventory('hosts')
    stats = ansible.callbacks.AggregateStats()
    pb_cb = ansible.callbacks.PlaybookCallbacks(verbose=ansible.utils.VERBOSITY)
    rn_cb = ansible.callbacks.PlaybookRunnerCallbacks(stats, verbose=ansible.utils.VERBOSITY)


    pass

def main():
    bench = parse_config('benchmark.yml', 'bench config')

    workloads = bench.get('workloads', [])
    timeout   = bench.get('ansible', {}).get('ansible_timeout', 60)
    output    = bench.get('ansible', {}).get('output', 'output')

    os.mkdir(output)
    for wl in workloads:
        run_workload(wl, output)

    return 0

exit(main())
