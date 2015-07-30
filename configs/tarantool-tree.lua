box.cfg {
   listen            = '3310',
   slab_alloc_arena  = 0.2,
   log_level         = 5,
   logger_nonblock   = true,
   wal_mode          = "none",
}

local spc = box.schema.space.create("ycsb", { id = 1024 })
spc:create_index('primary', { type = 'tree', parts = {1, 'STR'} } )
box.schema.user.grant('guest', 'read,write,execute', 'universe')
