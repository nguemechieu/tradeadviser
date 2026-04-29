FROM node:22-alpine AS builder

WORKDIR /app/frontend

ENV NODE_ENV=production \
    DISABLE_TELEMETRY=1 \
    NEXT_TELEMETRY_DISABLED=1

COPY server/app/frontend/package*.json ./

RUN npm install --no-optional --legacy-peer-deps && npm install --force --legacy-peer-deps

COPY server/app/frontend/ ./

RUN npm run build


FROM nginx:alpine

COPY server/docker/nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/frontend/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
