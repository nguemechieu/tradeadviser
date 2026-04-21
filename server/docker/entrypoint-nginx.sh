<<<<<<< HEAD
#!/bin/sh
=======
﻿#!/bin/sh
>>>>>>> 4bef926f634c72a86f231ee2b5ab2e56b52111ef
set -e

# Remove default nginx config that conflicts with our custom configuration
rm -f /etc/nginx/conf.d/default.conf
mkdir -p /etc/nginx/conf.d

# Start nginx in foreground mode
exec nginx -g "daemon off;"
