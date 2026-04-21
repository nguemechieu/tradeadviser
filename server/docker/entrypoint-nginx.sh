#!/bin/sh
set -e

# Remove default nginx config that conflicts with our custom configuration
rm -f /etc/nginx/conf.d/default.conf
mkdir -p /etc/nginx/conf.d

# Start nginx in foreground mode
exec nginx -g "daemon off;"
