local log = require('log')
log.info("Preloading")

box.cfg {
   listen            = '3310',
   slab_alloc_arena  = 8,
   log_level         = 5,
   logger_nonblock   = true,
   wal_mode          = "none",
}

log.info("Creating space")
box.once("space-prepare", function()
	local spc = box.schema.space.create("ycsb", { id = 1024 })
	spc:create_index('primary', { type = 'hash', parts = {1, 'STR'} } )
	box.schema.user.grant('guest', 'read,write,execute', 'universe')
end)
log.info("Done")

require('console').listen('var/tarantool-hash.control')
