box.cfg {
   custom_proc_title = 'tarantool-hash-ycsb',
   listen            = '3310',
   slab_alloc_arena  = 8,
   log_level         = 5,
   logger_nonblock   = true,
   wal_mode          = "none",
   pid_file          = 'tarantool.pid',
   background        = true
}

local spc = box.schema.space.create("ycsb", { id = 1024 })
spc:create_index('primary', { type = 'hash', parts = {1, 'STR'} } )
box.schema.user.grant('guest', 'read,write,execute', 'universe')
