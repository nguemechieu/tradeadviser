# Deployment Guide

This guide covers deploying TradeAdviser to production environments.

## Table of Contents

- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Environment Configuration](#environment-configuration)
- [SSL/TLS Setup](#ssltls-setup)
- [Database Migration](#database-migration)
- [Monitoring & Logging](#monitoring--logging)
- [Backup & Recovery](#backup--recovery)
- [Scaling](#scaling)

## Pre-Deployment Checklist

Before deploying to production:

- [ ] All tests passing (`pytest`, `npm test`)
- [ ] Security review completed
- [ ] Database backups configured
- [ ] SSL certificates obtained
- [ ] Environment variables documented
- [ ] Monitoring tools configured
- [ ] Disaster recovery plan tested
- [ ] Load testing completed
- [ ] API rate limiting configured
- [ ] CORS policies reviewed

## Docker Deployment

### Production Docker Compose

```yaml
# server/docker-compose.yml (production version)
version: '3.8'

services:
  backend:
    image: tradeadviser-backend:latest
    container_name: tradeadviser-backend-prod
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://user:password@db:5432/tradeadviser
      API_HOST: 0.0.0.0
      API_PORT: 8000
      ENVIRONMENT: production
    depends_on:
      - db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - tradeadviser-network
    volumes:
      - ./frontend/dist:/app/frontend/dist:ro
      - ./logs:/app/logs
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"

  db:
    image: postgres:15
    container_name: tradeadviser-db-prod
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: tradeadviser
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - tradeadviser-network
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"

  nginx:
    image: nginx:latest
    container_name: tradeadviser-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./frontend/dist:/usr/share/nginx/html:ro
    depends_on:
      - backend
    restart: unless-stopped
    networks:
      - tradeadviser-network

volumes:
  postgres-data:
    driver: local

networks:
  tradeadviser-network:
    driver: bridge
```

### Build and Deploy

```bash
# Build production image
docker build -f docker/Dockerfile.backend \
  -t tradeadviser-backend:latest \
  -t tradeadviser-backend:v1.0.0 \
  .

# Tag for registry
docker tag tradeadviser-backend:latest your-registry/tradeadviser-backend:latest

# Push to registry
docker push your-registry/tradeadviser-backend:latest

# Deploy
cd server
docker-compose -f docker-compose.prod.yml up -d

# Verify deployment
docker-compose ps
docker-compose logs -f backend
```

## Kubernetes Deployment

### Namespace & Secrets

```bash
# Create namespace
kubectl create namespace tradeadviser

# Create secrets
kubectl create secret generic tradeadviser-secrets \
  --from-literal=db-user=tradeuser \
  --from-literal=db-password=your-secure-password \
  -n tradeadviser

kubectl create secret tls tradeadviser-tls \
  --cert=path/to/cert.pem \
  --key=path/to/key.pem \
  -n tradeadviser
```

### Kubernetes Deployment Manifests

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tradeadviser-backend
  namespace: tradeadviser
spec:
  replicas: 3
  selector:
    matchLabels:
      app: tradeadviser-backend
  template:
    metadata:
      labels:
        app: tradeadviser-backend
    spec:
      containers:
      - name: backend
        image: your-registry/tradeadviser-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: tradeadviser-secrets
              key: database-url
        - name: ENVIRONMENT
          value: "production"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: tradeadviser-service
  namespace: tradeadviser
spec:
  selector:
    app: tradeadviser-backend
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: tradeadviser-hpa
  namespace: tradeadviser
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: tradeadviser-backend
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Deploy to Kubernetes

```bash
# Apply manifests
kubectl apply -f k8s/

# Verify deployment
kubectl get pods -n tradeadviser
kubectl logs -n tradeadviser -l app=tradeadviser-backend

# Access service
kubectl port-forward -n tradeadviser svc/tradeadviser-service 8000:80
```

## Environment Configuration

### Production Environment Variables

```bash
# .env.production
ENVIRONMENT=production

# Database
DATABASE_URL=postgresql+asyncpg://tradeuser:${DB_PASSWORD}@db-hostname:5432/tradeadviser
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Security
SECRET_KEY=your-secret-key-here  # Generate with: openssl rand -hex 32
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Logging
LOG_LEVEL=INFO
LOG_FILE=/app/logs/api.log

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=1000
RATE_LIMIT_PERIOD=3600

# Broker Configuration
BROKER_TIMEOUT=30
BROKER_RETRY_ATTEMPTS=3
```

### Secrets Management

```bash
# Using environment files
export DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id tradeadviser-db-password --query SecretString --output text)

# Using environment variable injection
docker run -e DB_PASSWORD=$DB_PASSWORD tradeadviser-backend

# Using Kubernetes secrets
kubectl create secret generic db-credentials \
  --from-literal=password=$DB_PASSWORD
```

## SSL/TLS Setup

### Nginx Configuration with SSL

```nginx
# nginx.conf
upstream backend {
    server backend:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL Certificate
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    
    # Proxy settings
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Frontend
    location / {
        root /usr/share/nginx/html;
        try_files $uri /index.html;
    }
    
    # Backend API
    location /api {
        proxy_pass http://backend;
    }
    
    # WebSocket
    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Let's Encrypt SSL Certificate

```bash
# Using Certbot
docker run --rm -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/lib/letsencrypt:/var/lib/letsencrypt \
  -p 80:80 -p 443:443 \
  certbot/certbot certonly --standalone \
  -d yourdomain.com -d www.yourdomain.com
```

## Database Migration

### Production Migration Strategy

```bash
# 1. Backup current database
pg_dump postgresql://user:password@host/tradeadviser > backup.sql

# 2. Test migration on staging
# ... deploy to staging, run migrations, test thoroughly

# 3. Perform migration during maintenance window
docker-compose exec -T db psql -U tradeuser -d tradeadviser < migrations.sql

# 4. Verify migration
docker-compose exec db psql -U tradeuser -d tradeadviser -c "SELECT version();"

# 5. If needed, rollback
psql postgresql://user:password@host/tradeadviser < backup.sql
```

## Monitoring & Logging

### Application Monitoring

```bash
# Health endpoint for monitoring
curl https://yourdomain.com/health

# Prometheus metrics (if configured)
curl https://yourdomain.com/metrics

# Application logs
docker-compose logs --tail=100 -f backend
```

### Log Aggregation

```yaml
# Docker logging driver configuration
logging:
  driver: "splunk"
  options:
    splunk-token: "${SPLUNK_TOKEN}"
    splunk-url: "https://your-splunk-instance:8088"
    tag: "tradeadviser-backend"
```

### Alerting

Set up alerts for:
- API response time > 1000ms
- Error rate > 1%
- Database connection errors
- Disk space < 10%
- Memory usage > 85%

## Backup & Recovery

### Database Backup

```bash
# Scheduled backup (cron)
0 2 * * * pg_dump postgresql://user:pass@host/db | gzip > /backups/db-$(date +\%Y\%m\%d).sql.gz

# Backup to S3
0 2 * * * pg_dump postgresql://user:pass@host/db | \
  aws s3 cp - s3://your-bucket/backups/db-$(date +\%Y\%m\%d).sql.gz

# Restore from backup
gunzip -c /backups/db-20260420.sql.gz | psql postgresql://user:pass@host/db
```

### Application Data Backup

```bash
# Backup configuration and data
docker run --rm -v tradeadviser-data:/data \
  -v /backups:/backup \
  alpine tar czf /backup/data-$(date +%Y%m%d).tar.gz -C /data .
```

## Scaling

### Horizontal Scaling

```bash
# Docker Swarm
docker service create --replicas 3 \
  -p 8000:8000 \
  --name tradeadviser-backend \
  your-registry/tradeadviser-backend:latest

# Kubernetes autoscaling (already configured in HPA)
# Min replicas: 3, Max: 10, Target CPU: 70%
```

### Load Balancing

Use Nginx or HAProxy for load balancing:

```nginx
upstream backend_pool {
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
    
    # Health check
    check interval=3000 rise=2 fall=5 timeout=1000 type=http;
    check_http_send "GET /health HTTP/1.0\r\n\r\n";
    check_http_expect_alive http_2xx;
}

server {
    location /api {
        proxy_pass http://backend_pool;
        proxy_connect_timeout 5s;
    }
}
```

### Database Connection Pooling

```python
# backend/config.py
SQLALCHEMY_POOL_SIZE = 20
SQLALCHEMY_MAX_OVERFLOW = 10
SQLALCHEMY_POOL_RECYCLE = 3600
SQLALCHEMY_POOL_PRE_PING = True
```

## Deployment Checklist

After deployment:

- [ ] Health endpoint responds (200 OK)
- [ ] API documentation accessible
- [ ] Frontend loads successfully
- [ ] Database connections working
- [ ] SSL certificate valid
- [ ] CORS policies configured
- [ ] Rate limiting functional
- [ ] Logging operational
- [ ] Monitoring alerts active
- [ ] Backup scheduled
- [ ] Disaster recovery tested

---

**Last Updated**: April 2026
