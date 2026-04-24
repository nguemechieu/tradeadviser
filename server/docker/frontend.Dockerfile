FROM node:22-alpine AS builder

WORKDIR /frontend

ENV NODE_ENV=production \
    DISABLE_TELEMETRY=1

COPY /package*.json ./

RUN npm ci --legacy-peer-deps

COPY . .

RUN npm run build


FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /build/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]