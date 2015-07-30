box.cfg {
   custom_proc_title = 'tarantool-tree-ycsb',
   listen            = '3310',
   slab_alloc_arena  = 8,
   log_level         = 5,
   logger_nonblock   = true,
   wal_mode          = "none",
   pid_file          = 'tarantool.pid',
   logger            = 'tarantool.log',
   background        = true
}

local spc = box.schema.space.create("ycsb", { id = 1024 })
spc:create_index('primary', { type = 'tree', parts = {1, 'STR'} } )
box.schema.user.grant('guest', 'read,write,execute', 'universe')
