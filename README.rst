-------------------------------------------------------------------------------
                                    Intro
-------------------------------------------------------------------------------

=====================================================================
                          Prepairing YCSB
=====================================================================

To prepare YCSB you must run:

.. code-block:: bash

	$ sudo add-apt-repository ppa:webupd8team/java
	$ echo oracle-java7-installer shared/accepted-oracle-license-v1-1 select true | sudo /usr/bin/debconf-set-selections
	$ sudo apt-get install maven oracle-java7-set-default # YCSB behaves better with oracle
	$ cd /tmp
	$ wget https://github.com/brianfrankcooper/YCSB/archive/0.3.0-RC3.tar.gz
	$ tar xzf 0.3.0-RC3.tar.gz
	$ cd /tmp/YCSB-0.3.0-RC3
	$ mvn package
	$ cp /tmp/YCSB-0.3.0-RC3/distribution/target/ycsb-0.3.0-RC3.tar.gz ../
	$ tar xzf ycsb-0.3.0-RC3.tar.gz

Now you'll get folder `/tmp/ycsb-0.3.0-RC3` with YCSB that will be used to run benchmarks.

=====================================================================
                              Running YCSB
=====================================================================

`./bin/ycsb` possible arguments:

* :samp:`-P {file}` - Specify workload file (mandatory)
* :samp:`-p {key}={value}` - Override workload property
* :samp:`-s` - Print status to stderr
* :samp:`-target {n}` - Target ops/sec (default: unthrottled)
* :samp:`-threads {n}` - Number of client threads (default: 1)

YCSB have two mods of working:

* `load` - loading of 'rows' into DB
* `run`  - run needed benchmark

and a lot of properties to work with (``-p prop=value``):

* `exporter` - one of:
  + *com.yahoo.ycsb.TestMeasurementsExporter* - human-readable format (default)
  + *com.yahoo.ycsb.JSONArrayMeasurementsExporter* - export as array of maps in json

* `measurementtype` - one of:
  + *histogram* - (default)
  + *timeseries*   - latency in timeseries
  + *hdrhistogram* - recommended

* `fieldcount`  - number of fields to put into 
* `fieldlength` - length of fields in the db
* `requestdistribution` - one of:
  + *uniform* - (default)
  + *zipfian*
  + *latest*
* `insertorder` - order of `row`'s keys to insert
  + *ordered*
  + *hashed*  - (default)
* `operationcount` - number of operations to perform (number)
* `recordcount`    - number of records to load into the database initially (number)
* `maxexecutiontime` - maximum execution time in seconds. The benchmark runs until
		       either the operation count has exhausted or the maximum specified
                       time has elapsed, whichever is earlier.

Database properties:

* `tarantool.host` - host of tarantool instance to bench
* `tarantool.port` - port of tarantool instance to bench
* `redis.host` - host of redis instance to bench
* `redis.port` - port of redis instance to bench
e.t.c.

Example (assuming we run everything from `/tmp/ycsb-0.3.0-RC3`):

.. code-block:: bash

	# load information into database
	$ ./bin/ycsb load -P workloads/workloada -p tarantool.host=localhost -p tarantool.port=3301\
	  -s -threads 8 -p measurementtype=hdrhistogram -p operationcount=300000 -p recordcount=900000
	# run workload
	$ ./bin/ycsb run -P workloads/workloada -p tarantool.host=localhost -p tarantool.port=3301\
	   -s -threads 8 -p measurementtype=hdrhistogram -p operationcount=300000 -p recordcount=900000

As you may see - we use the same arguments for load and run.

=====================================================================
                        Config for autoYCSB
=====================================================================

Configuration of every node in `database.host` and `workloads.host` consists of:

.. code-block:: yaml

	host: '192.168.33.10'
	user: 'username'
	port: 22
	opts:
	  # ansible_options for hosts file, e.g.
	  ansible_sudo_pass: 'vagrant'
	  ansible_ssh_private_key_file: '/home/user/.ssh/id_rse'

Configuration of every db to bench in `database.list` consists of:

.. code-block:: yaml

	name: 'redis-28'
	opts:
	  # options for ansible, e.g.
	  port: 6400

Configuration of every benchmark in `workloads.list` consists of:

.. code-block:: yaml

	# LOAD is internal name
	'LOAD': {
	  # file to use in workload
	  workloadfile: 'workloads/workloada'
	  # description for benchmark
	  description:  'Insert Only'
	  # parameters to use in YCSB
	  params: {
	    insertproportion: 1
	    # ...
	  }
	}

Also, for every benchmark YCSB uses options in `workloads.params`

For control of runs this framework uses:

* `runs.threads` as array of clients to run on every node.
* `runs.retries` as number of benchmark to run to get average number from.

All you need is to run 

.. code-block:: shell

	./run.py

=====================================================================
                          Processing output
=====================================================================

When bench is done, you need to process all files from benchmarks:

.. code-block:: shell

	./terminal.py

You'll see something like this:

:: 

	2015-07-28 18:23:32,686|INFO > cfg: bench config parsing
	2015-07-28 18:23:32,701|INFO > cfg: done
	2015-07-28 18:23:32,917|INFO > Workload 'C'
	2015-07-28 18:23:32,918|INFO > Latency (In usec, less is better)
	2015-07-28 18:23:32,919|INFO > 
	+------------------------+---------------+
	| DB-Clients\OP          | read          |
	+------------------------+---------------+
	| redis-28-32            | 577.036069193 |
	| redis-30-32            | 574.639275553 |
	| tarantool-tree-165-32  | 636.195281672 |
	| tarantool-hash-165-32  | 482.628086112 |
	| tarantool-tree-166-32  | 528.136132134 |
	| tarantool-hash-166-32  | 521.008217826 |
	| redis-28-48            | 832.743285669 |
	...
	...
	...
	| tarantool-tree-166-128 | 1760.11841857 |
	| tarantool-hash-166-128 | 1950.853866   |
	+------------------------+---------------+
	2015-07-28 18:23:32,919|INFO > RPS (More is better)
	2015-07-28 18:23:32,920|INFO > 
	+--------------------+--------+--------+--------+--------+--------+--------+--------+
	| DB\Threads         | 32     | 48     | 64     | 80     | 96     | 112    | 128    |
	+--------------------+--------+--------+--------+--------+--------+--------+--------+
	| redis-28           | 101063 | 104222 | 106992 | 115430 | 115461 | 120263 | 118237 |
	| redis-30           | 97195  | 102992 | 106248 | 114246 | 118863 | 127199 | 121225 |
	| tarantool-tree-165 | 85685  | 99749  | 99225  | 102771 | 100420 | 100050 | 100008 |
	| tarantool-hash-165 | 120401 | 115989 | 129872 | 124756 | 128006 | 133905 | 132940 |
	| tarantool-tree-166 | 106545 | 124006 | 123701 | 128561 | 134110 | 138065 | 139294 |
	| tarantool-hash-166 | 116923 | 117448 | 122471 | 124429 | 125680 | 128079 | 127153 |
	+--------------------+--------+--------+--------+--------+--------+--------+--------+
