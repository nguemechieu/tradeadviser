# Kubernetes Deployment Guide

TradeAdviser can be deployed to Kubernetes clusters (AKS, EKS, GKE, self-hosted) for production-grade scalability and reliability.

## Quick Start

### Prerequisites

- Kubernetes 1.24+
- kubectl CLI configured with cluster access
- Helm 3.x (optional, for Helm deployment)
- Docker images pushed to registry (ghcr.io, Docker Hub, or private registry)

### Deploy with kubectl

```bash
# 1. Create namespace and secrets
kubectl create namespace tradeadviser
kubectl create secret generic tradeadviser-secrets \
  --from-literal=DATABASE_URL=postgresql://user:pass@postgres:5432/tradeadviser \
  --from-literal=SECRET_KEY=your-secret-key \
  --from-literal=JWT_SECRET=your-jwt-secret \
  -n tradeadviser

# 2. Deploy PostgreSQL
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/postgres.yaml

# 3. Deploy backend and frontend
kubectl apply -f k8s/backend.yaml
kubectl apply -f k8s/frontend.yaml

# 4. Apply ingress
kubectl apply -f k8s/ingress.yaml

# 5. Verify deployment
kubectl get deployments -n tradeadviser
kubectl get pods -n tradeadviser
kubectl get services -n tradeadviser
```

### Deploy with Helm

```bash
# 1. Create namespace
kubectl create namespace tradeadviser

# 2. Deploy with Helm
helm install tradeadviser ./helm/tradeadviser \
  --namespace tradeadviser \
  --values helm/tradeadviser/values.yaml \
  --set image.registry=ghcr.io \
  --set image.tag=latest \
  --set secrets.databaseUrl="postgresql://user:pass@postgres:5432/tradeadviser" \
  --set secrets.secretKey="your-secret-key" \
  --set secrets.jwtSecret="your-jwt-secret"

# 3. Verify deployment
helm status tradeadviser -n tradeadviser
kubectl get all -n tradeadviser
```

## Architecture

### Kubernetes Resources

```
Namespace: tradeadviser
├── ConfigMap: tradeadviser-config
├── Secret: tradeadviser-secrets
├── 
├── StatefulSet: postgres
│   └── Service: postgres (ClusterIP)
│
├── Deployment: tradeadviser-backend
│   ├── Service: tradeadviser-backend (ClusterIP)
│   ├── HorizontalPodAutoscaler
│   └── PodDisruptionBudget
│
├── Deployment: tradeadviser-frontend
│   ├── Service: tradeadviser-frontend (ClusterIP)
│   ├── HorizontalPodAutoscaler
│   └── PodDisruptionBudget
│
└── Ingress: tradeadviser
    └── TLS (cert-manager)
```

### Components

#### PostgreSQL
- **Type**: StatefulSet with PersistentVolume
- **Replicas**: 1 (can be scaled for HA)
- **Storage**: 10Gi (configurable)
- **Resource Requests**: 256Mi memory, 250m CPU
- **Probes**: Liveness and readiness checks

#### Backend (FastAPI)
- **Type**: Deployment (stateless)
- **Replicas**: 2 (default), auto-scales 2-10
- **Scaling**: Based on CPU (70%) and Memory (80%)
- **Resource Requests**: 512Mi memory, 500m CPU
- **Limits**: 1Gi memory, 1000m CPU
- **Probes**: HTTP /health endpoint
- **Security**: Non-root user, read-only root filesystem
- **Anti-affinity**: Spreads pods across nodes

#### Frontend (React/Nginx)
- **Type**: Deployment (stateless)
- **Replicas**: 2 (default), auto-scales 2-5
- **Scaling**: Based on CPU (80%)
- **Resource Requests**: 128Mi memory, 100m CPU
- **Limits**: 256Mi memory, 500m CPU
- **Probes**: HTTP / endpoint
- **Security**: Non-root user, read-only root filesystem
- **Anti-affinity**: Spreads pods across nodes

#### Ingress
- **Controller**: NGINX Ingress Controller
- **TLS**: Let's Encrypt certificates (cert-manager)
- **SSL Redirect**: Automatic HTTPS redirect
- **Rate Limiting**: 100 requests per 10 minutes
- **Hostname**: tradeadviser.org, www.tradeadviser.org
- **Routing**:
  - `/api*` → Backend
  - `/docs` → Backend (Swagger UI)
  - `/` → Frontend

## Configuration

### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tradeadviser
```

**Create namespace**:
```bash
kubectl apply -f k8s/namespace.yaml
```

### ConfigMap

Application configuration:
```yaml
LOG_LEVEL: "INFO"
DEBUG: "false"
ENVIRONMENT: "production"
```

**Update configuration**:
```bash
kubectl set env deployment/tradeadviser-backend LOG_LEVEL=DEBUG -n tradeadviser
kubectl rollout restart deployment/tradeadviser-backend -n tradeadviser
```

### Secrets

Sensitive data stored as Kubernetes Secrets:
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: FastAPI secret key
- `JWT_SECRET`: JWT signing key

**Create secrets**:
```bash
kubectl create secret generic tradeadviser-secrets \
  --from-literal=DATABASE_URL=... \
  --from-literal=SECRET_KEY=... \
  --from-literal=JWT_SECRET=... \
  -n tradeadviser
```

**Update secrets**:
```bash
kubectl delete secret tradeadviser-secrets -n tradeadviser
kubectl create secret generic tradeadviser-secrets \
  --from-literal=DATABASE_URL=new-value \
  -n tradeadviser
kubectl rollout restart deployment/tradeadviser-backend -n tradeadviser
```

## Scaling

### Horizontal Scaling

Auto-scaling based on CPU and memory:

**Backend**:
```yaml
minReplicas: 2
maxReplicas: 10
targetCPUUtilization: 70%
targetMemoryUtilization: 80%
```

**Frontend**:
```yaml
minReplicas: 2
maxReplicas: 5
targetCPUUtilization: 80%
```

**Manual scaling**:
```bash
kubectl scale deployment tradeadviser-backend --replicas=5 -n tradeadviser
kubectl get hpa -n tradeadviser  # View autoscaler status
```

### Vertical Scaling

Adjust resource requests/limits in deployment YAML:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

Then update:
```bash
kubectl apply -f k8s/backend.yaml
kubectl rollout restart deployment/tradeadviser-backend -n tradeadviser
```

## High Availability

### Pod Disruption Budgets

Ensures availability during maintenance:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: tradeadviser-backend
spec:
  minAvailable: 1  # At least 1 pod must stay available
  selector:
    matchLabels:
      app: tradeadviser
      component: backend
```

### Pod Anti-Affinity

Spreads pods across different nodes:

```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        labelSelector:
          matchExpressions:
          - key: app
            operator: In
            values:
            - tradeadviser
        topologyKey: kubernetes.io/hostname
```

### Multiple Availability Zones

For production, deploy across multiple AZs:

```bash
# AKS with 3 zones
az aks create \
  --zones 1 2 3 \
  --node-vm-size Standard_D4s_v5 \
  --nodes 3
```

## Updates & Deployments

### Rolling Updates

Default strategy for zero-downtime updates:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1        # 1 extra pod during update
    maxUnavailable: 0  # 0 pods down during update
```

### Update Docker Images

```bash
# Update image
kubectl set image deployment/tradeadviser-backend \
  backend=ghcr.io/sopotek/tradeadviser/backend:v2.0.0 \
  -n tradeadviser

# Monitor rollout
kubectl rollout status deployment/tradeadviser-backend -n tradeadviser

# Rollback if needed
kubectl rollout undo deployment/tradeadviser-backend -n tradeadviser
```

### Update Configuration

```bash
# Recreate ConfigMap
kubectl create configmap tradeadviser-config \
  --from-literal=LOG_LEVEL=DEBUG \
  --dry-run=client -o yaml | kubectl apply -f - -n tradeadviser

# Restart pods to load new config
kubectl rollout restart deployment/tradeadviser-backend -n tradeadviser
```

## Monitoring

### View Logs

```bash
# Backend logs
kubectl logs deployment/tradeadviser-backend -n tradeadviser -f

# Frontend logs
kubectl logs deployment/tradeadviser-frontend -n tradeadviser -f

# View logs from multiple pods
kubectl logs -l app=tradeadviser -n tradeadviser -f
```

### Check Pod Status

```bash
# Get pods
kubectl get pods -n tradeadviser

# Get pod details
kubectl describe pod <pod-name> -n tradeadviser

# Get pod events
kubectl get events -n tradeadviser --sort-by='.lastTimestamp'
```

### Monitor Resource Usage

```bash
# Install metrics-server (if not installed)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# View resource usage
kubectl top nodes
kubectl top pods -n tradeadviser

# View HPA metrics
kubectl get hpa -n tradeadviser -w
```

### Port Forwarding

```bash
# Forward backend port
kubectl port-forward svc/tradeadviser-backend 8000:8000 -n tradeadviser
# Access at: http://localhost:8000/docs

# Forward frontend port
kubectl port-forward svc/tradeadviser-frontend 3000:80 -n tradeadviser
# Access at: http://localhost:3000
```

## Troubleshooting

### Pod Won't Start

```bash
# Check pod status
kubectl describe pod <pod-name> -n tradeadviser

# Common issues:
# - Image not found: Check image registry and credentials
# - CrashLoopBackOff: Check logs with kubectl logs
# - Pending: Check node resources with kubectl describe nodes
```

### Liveness/Readiness Probe Failures

```bash
# Check probes in deployment YAML
kubectl get deployment tradeadviser-backend -n tradeadviser -o yaml | grep -A 10 livenessProbe

# Test health endpoint manually
kubectl exec -it <pod-name> -n tradeadviser -- curl http://localhost:8000/health

# View probe events
kubectl describe pod <pod-name> -n tradeadviser | grep -A 5 "Liveness probe"
```

### Services Not Accessible

```bash
# Check service endpoints
kubectl get endpoints -n tradeadviser

# Test service connectivity from another pod
kubectl run debug --image=busybox --rm -it --restart=Never -- \
  wget -O- http://tradeadviser-backend:8000/health

# Check DNS
kubectl run debug --image=busybox --rm -it --restart=Never -- \
  nslookup tradeadviser-backend.tradeadviser.svc.cluster.local
```

### Database Connection Issues

```bash
# Check PostgreSQL pod
kubectl get pod -l app=postgres -n tradeadviser

# Check PostgreSQL logs
kubectl logs -l app=postgres -n tradeadviser

# Test database connectivity
kubectl exec -it <backend-pod> -n tradeadviser -- \
  psql postgresql://user:pass@postgres:5432/tradeadviser -c "SELECT 1"

# Check PVC status
kubectl get pvc -n tradeadviser
kubectl describe pvc postgres-pvc -n tradeadviser
```

## Azure Kubernetes Service (AKS) Specific

### Create AKS Cluster

```bash
# Create resource group
az group create \
  --name tradeadviser-rg \
  --location eastus

# Create AKS cluster (recommended: Automatic SKU)
az aks create \
  --name tradeadviser-aks \
  --resource-group tradeadviser-rg \
  --tier standard \
  --node-vm-size Standard_D4s_v5 \
  --nodes 3 \
  --zones 1 2 3 \
  --network-plugin azure \
  --network-plugin-mode overlay \
  --enable-managed-identity \
  --enable-addons monitoring \
  --enable-managed-identities \
  --generate-ssh-keys

# Get credentials
az aks get-credentials \
  --resource-group tradeadviser-rg \
  --name tradeadviser-aks
```

### Install Required Add-ons

```bash
# NGINX Ingress Controller
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install nginx-ingress ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace

# cert-manager for SSL/TLS
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer for Let's Encrypt
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: info@sopotek.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

### Enable Monitoring

```bash
# Enable Container Insights
az aks enable-addons \
  --addons monitoring \
  --name tradeadviser-aks \
  --resource-group tradeadviser-rg

# View logs in Log Analytics
az monitor log-analytics workspace list

# Query logs
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query "ContainerLog | where TimeGenerated > ago(1h)"
```

## Production Checklist

- ☐ Cluster deployed across multiple availability zones
- ☐ Ingress controller installed and configured
- ☐ SSL/TLS certificates configured (cert-manager)
- ☐ Secrets stored securely (not in manifests)
- ☐ Pod disruption budgets configured
- ☐ Resource requests and limits set
- ☐ Health checks (liveness, readiness) configured
- ☐ Logging and monitoring enabled
- ☐ RBAC policies enforced
- ☐ Network policies configured
- ☐ Backup strategy for persistent volumes
- ☐ Auto-scaling configured
- ☐ Load testing completed
- ☐ Disaster recovery plan documented

## Helm Chart

### Chart Structure

```
helm/tradeadviser/
├── Chart.yaml              # Chart metadata
├── values.yaml             # Default values
├── values-prod.yaml        # Production overrides
├── values-staging.yaml     # Staging overrides
└── templates/
    ├── namespace.yaml
    ├── configmap.yaml
    ├── secrets.yaml
    ├── postgres.yaml
    ├── backend.yaml
    ├── frontend.yaml
    └── ingress.yaml
```

### Helm Commands

```bash
# Validate chart
helm lint ./helm/tradeadviser

# Dry-run
helm install tradeadviser ./helm/tradeadviser \
  --namespace tradeadviser --dry-run --debug

# Install
helm install tradeadviser ./helm/tradeadviser \
  --namespace tradeadviser --values values-prod.yaml

# Upgrade
helm upgrade tradeadviser ./helm/tradeadviser \
  --namespace tradeadviser --values values-prod.yaml

# Rollback
helm rollback tradeadviser -n tradeadviser

# Uninstall
helm uninstall tradeadviser -n tradeadviser
```

## Backup & Disaster Recovery

### Backup Strategy

```bash
# Backup PostgreSQL
kubectl exec -it postgres-0 -n tradeadviser -- \
  pg_dump -U postgres tradeadviser > backup.sql

# Backup Kubernetes manifests
kubectl get all -n tradeadviser -o yaml > backup-k8s.yaml

# Backup PersistentVolumes
# Use cloud provider's backup service or Velero
```

### Restore Strategy

```bash
# Restore PostgreSQL
kubectl exec -it postgres-0 -n tradeadviser -- \
  psql -U postgres tradeadviser < backup.sql

# Restore Kubernetes manifests
kubectl apply -f backup-k8s.yaml
```

## Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Azure Kubernetes Service](https://learn.microsoft.com/azure/aks/)
- [Helm Documentation](https://helm.sh/docs/)
- [NGINX Ingress Controller](https://kubernetes.github.io/ingress-nginx/)
- [cert-manager](https://cert-manager.io/)
- [Velero Backup](https://velero.io/)
