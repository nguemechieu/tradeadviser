FROM nginx:alpine

# Remove default nginx config that conflicts with our custom configuration
RUN rm -f /etc/nginx/conf.d/default.conf

# Copy custom nginx configuration
COPY server/docker/nginx.conf /etc/nginx/nginx.conf

# Copy custom entrypoint script
COPY server/docker/entrypoint-nginx.sh /entrypoint-nginx.sh
RUN chmod +x /entrypoint-nginx.sh

ENTRYPOINT ["/entrypoint-nginx.sh"]
