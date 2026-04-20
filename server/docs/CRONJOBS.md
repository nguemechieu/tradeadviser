# Cron Jobs and Scheduled Tasks

TradeAdviser uses scheduled tasks for automated maintenance, backups, monitoring, and security checks.

## Kubernetes CronJobs

Kubernetes CronJobs run automated tasks on a schedule within the cluster.

### Prerequisites

```bash
# Deploy CronJobs
kubectl apply -f k8s/cronjobs.yaml

# View CronJobs
kubectl get cronjobs -n tradeadviser

# View job history
kubectl get jobs -n tradeadviser
```

### Available CronJobs

#### 1. PostgreSQL Backup (`postgres-backup`)

**Schedule**: Daily at 2:00 AM UTC  
**Frequency**: `0 2 * * *`  
**Purpose**: Automated database backups

**What it does**:
- Creates custom format PostgreSQL dump
- Stores backup in persistent volume
- Retains last 7 days of backups
- Logs backup status

**Storage**:
- Location: `/backups` in persistent volume
- Size: 50Gi PVC
- Cleanup: Auto-deletes backups older than 7 days

**Manual backup**:
```bash
# Manually trigger backup
kubectl create job --from=cronjob/postgres-backup manual-backup-$(date +%s) -n tradeadviser

# View backup status
kubectl describe job manual-backup-<id> -n tradeadviser

# List backups
kubectl exec postgres-0 -n tradeadviser -- ls -lah /backups/
```

**Restore from backup**:
```bash
# List available backups
kubectl exec postgres-0 -n tradeadviser -- ls /backups/

# Restore backup
kubectl exec postgres-0 -n tradeadviser -- \
  pg_restore -d tradeadviser -U postgres /backups/tradeadviser-backup-20260419-020000.sql
```

---

#### 2. Database Cleanup (`database-cleanup`)

**Schedule**: Daily at 3:00 AM UTC  
**Frequency**: `0 3 * * *`  
**Purpose**: Maintenance and optimization

**What it does**:
- Deletes old sessions (> 30 days)
- Deletes old audit logs (> 90 days)
- Analyzes table statistics
- Vacuums database to reclaim space

**Impact**:
- Recovers 5-10% of database space
- Improves query performance
- Maintains data retention policies
- Runs vacuum analyze for optimization

**Monitor cleanup**:
```bash
# View cleanup logs
kubectl logs -l job-name=database-cleanup-<id> -n tradeadviser

# Check storage before/after
kubectl exec postgres-0 -n tradeadviser -- \
  psql -U postgres -c "SELECT pg_database.datname, pg_size_pretty(pg_database_size(pg_database.datname)) FROM pg_database;"
```

---

#### 3. Health Check (`health-check`)

**Schedule**: Every 5 minutes  
**Frequency**: `*/5 * * * *`  
**Purpose**: Continuous service monitoring

**What it checks**:
- Backend API `/health` endpoint
- Frontend HTTP response
- Overall service availability

**Behavior**:
- Runs every 5 minutes
- Alerts on failure
- Keeps only recent job history

**View health check results**:
```bash
# Get last health check status
kubectl get jobs -l cronjob-name=health-check -n tradeadviser -o wide

# View health check logs
kubectl logs -l cronjob-name=health-check -n tradeadviser --tail=20
```

---

#### 4. Pod Resource Cleanup (`pod-resource-cleanup`)

**Schedule**: Daily at 4:00 AM UTC  
**Frequency**: `0 4 * * *`  
**Purpose**: Clean up failed and completed pods

**What it does**:
- Deletes evicted pods
- Deletes succeeded pods older than 1 day
- Reclaims resource storage

**RBAC Required**:
- ServiceAccount: `tradeadviser-cleanup`
- ClusterRole: `pod-cleanup` (pod get, list, delete)

**Manual cleanup**:
```bash
# Manually trigger cleanup
kubectl create job --from=cronjob/pod-resource-cleanup manual-cleanup -n tradeadviser

# View cleanup logs
kubectl logs -l job-name=manual-cleanup -n tradeadviser
```

---

## GitHub Actions Scheduled Workflows

Automated workflows run on GitHub Actions schedule for security, dependency updates, and testing.

### Available Scheduled Workflows

#### 1. Scheduled Security Scan (`.github/workflows/scheduled-security.yml`)

**Schedule**: Every Sunday at 2:00 AM UTC  
**Frequency**: `0 2 * * 0`  
**Purpose**: Comprehensive security scanning

**Tasks**:
- Full Trivy filesystem scan
- Bandit Python security check
- SonarCloud analysis
- OWASP Top 10 scanning
- Security report generation

**Results**:
- SARIF upload to GitHub Security tab
- JSON reports in artifacts
- Slack notifications on findings

**View results**:
```bash
# GitHub Security tab
https://github.com/sopotek/tradeadviser/security/code-scanning

# Artifacts
https://github.com/sopotek/tradeadviser/actions/runs/<run-id>
```

---

#### 2. Dependency Updates (`.github/workflows/dependency-updates.yml`)

**Schedule**: Every Monday at 9:00 AM UTC  
**Frequency**: `0 9 * * 1`  
**Purpose**: Keep dependencies current and secure

**Tasks**:
- Python package updates (`pip-compile --upgrade`)
- Node.js package updates (`npm update`)
- Security fixes (`npm audit fix`)
- Auto-run tests on updates
- Create PR if updates available

**Pull Request**:
- Title: "🔄 Automated Dependency Updates"
- Branch: `deps/automated-updates`
- Labels: `dependencies`, `automated`
- Tests: ✅ Passing required

**Manual update check**:
```bash
# Trigger workflow manually
gh workflow run dependency-updates.yml
```

**Vulnerability scanning**:
- `pip-audit` for Python
- `safety check` for Python
- `npm audit` for Node.js
- Creates vulnerability report
- Alerts on high-severity issues

---

#### 3. Scheduled Performance Tests (`.github/workflows/scheduled-performance.yml`)

**Schedule**: Daily at 11:00 PM UTC  
**Frequency**: `0 23 * * *`  
**Purpose**: Performance regression detection

**Tests**:
- Backend pytest-benchmark tests
- Frontend build analysis
- Load test configuration
- Database integrity checks
- Build size monitoring

**Reports**:
- Benchmark JSON results
- Build size analysis
- Performance trends
- Frontend lighthouse metrics

**Artifacts**:
- `performance-report.md` - Summary
- `benchmark-data` - Detailed metrics
- `integrity-report` - Database health

---

#### 4. Scheduled Maintenance (`.github/workflows/scheduled-maintenance.yml`)

**Multiple schedules**:
- **Database Backup**: Daily 2:00 AM UTC
- **Database Cleanup**: Daily 3:00 AM UTC  
- **Weekly Report**: Monday 8:00 AM UTC
- **Uptime Monitoring**: Always

**Tasks**:

**Database Backup**:
- Verifies cloud backup service (AWS RDS, Azure PostgreSQL, GCP Cloud SQL)
- Confirms backup location
- Documents retention policy

**Database Cleanup**:
- Documents cleanup tasks
- Generates cleanup plan
- Verifies retention policies

**Weekly Report**:
- Generates maintenance summary
- Lists completed tasks
- Documents upcoming maintenance
- Reports alerts/issues

**Uptime Monitoring**:
- Monitors application availability
- Tracks response times
- Reports SLA compliance
- Documents health metrics

---

## Schedule Reference

| Task | Schedule | Time (UTC) | Frequency |
|------|----------|-----------|-----------|
| Health Check | Every 5 min | Every 5 min | Continuous |
| Pod Cleanup | Daily | 4:00 AM | Daily |
| DB Cleanup | Daily | 3:00 AM | Daily |
| DB Backup | Daily | 2:00 AM | Daily |
| Dep Updates | Monday | 9:00 AM | Weekly |
| Security Scan | Sunday | 2:00 AM | Weekly |
| Perf Tests | Daily | 11:00 PM | Daily |
| Weekly Report | Monday | 8:00 AM | Weekly |

---

## Management

### View CronJob Status

```bash
# List all CronJobs
kubectl get cronjobs -n tradeadviser

# Get CronJob details
kubectl describe cronjob postgres-backup -n tradeadviser

# View recent job runs
kubectl get jobs -n tradeadviser --sort-by=.metadata.creationTimestamp

# Follow job logs
kubectl logs -f -l cronjob-name=postgres-backup -n tradeadviser
```

### Suspend/Resume CronJob

```bash
# Suspend CronJob
kubectl patch cronjob postgres-backup -n tradeadviser -p '{"spec" : {"suspend" : true }}'

# Resume CronJob
kubectl patch cronjob postgres-backup -n tradeadviser -p '{"spec" : {"suspend" : false }}'
```

### Manual Job Trigger

```bash
# Trigger PostgreSQL backup manually
kubectl create job --from=cronjob/postgres-backup backup-manual -n tradeadviser

# Trigger cleanup manually
kubectl create job --from=cronjob/database-cleanup cleanup-manual -n tradeadviser

# Trigger health check manually
kubectl create job --from=cronjob/health-check healthcheck-manual -n tradeadviser
```

### GitHub Actions Workflow Control

```bash
# List all workflows
gh workflow list

# Trigger workflow manually
gh workflow run scheduled-security.yml

# View workflow runs
gh run list --workflow scheduled-security.yml

# Cancel running workflow
gh run cancel <run-id>

# View workflow logs
gh run view <run-id> --log
```

---

## Monitoring & Alerts

### CronJob Monitoring

Set up alerts for:
- CronJob failures (restartPolicy: OnFailure)
- Job execution time exceeds threshold
- Database backup size anomalies
- Cleanup jobs not completing

**Example alert rule**:
```yaml
# Kubernetes event monitoring
- alert: CronJobFailed
  expr: increase(kubernetes_job_failures_total[1h]) > 0
  annotations:
    summary: "CronJob failed"
    description: "CronJob {{ $labels.job_name }} failed in namespace {{ $labels.namespace }}"
```

### GitHub Actions Monitoring

Monitor workflow status via:
- GitHub Actions dashboard
- Slack notifications (configured)
- Email notifications (optional)
- Status badges in README

---

## Best Practices

### CronJob Configuration

- ✅ Set `concurrencyPolicy: Forbid` to prevent overlapping runs
- ✅ Set `successfulJobsHistoryLimit` to keep history manageable
- ✅ Use `restartPolicy: OnFailure` for automatic retries
- ✅ Set resource requests and limits
- ✅ Use RBAC for security
- ✅ Monitor job execution time

### Scheduled Workflow Configuration

- ✅ Use UTC for schedule consistency
- ✅ Space out concurrent jobs to avoid resource exhaustion
- ✅ Add workflow dispatch for manual trigger
- ✅ Upload artifacts for audit trail
- ✅ Send notifications on critical events
- ✅ Set timeouts to prevent hanging jobs

### Retention Policies

- ✅ Database backups: 7 days daily, 4 weeks weekly
- ✅ Audit logs: 90 days retention
- ✅ Sessions: 30 days retention
- ✅ Failed trades: 7 days retention
- ✅ Job history: 3 successful, 1 failed per CronJob

---

## Troubleshooting

### CronJob Not Running

```bash
# Check CronJob schedule
kubectl get cronjob postgres-backup -n tradeadviser -o yaml | grep schedule

# Verify system clock (important for schedule matching)
kubectl get nodes -o wide

# Check CronJob suspension status
kubectl get cronjob postgres-backup -n tradeadviser -o yaml | grep suspend

# View next scheduled run
kubectl get cronjob postgres-backup -n tradeadviser -o yaml | grep nextScheduleTime
```

### Job Failures

```bash
# Get failed job
kubectl get jobs -n tradeadviser --field-selector=status.successful=0

# View failure reason
kubectl describe job <failed-job> -n tradeadviser

# View pod logs
kubectl logs <pod-name> -n tradeadviser

# Check events
kubectl get events -n tradeadviser --sort-by='.lastTimestamp'
```

### Workflow Not Triggering

```bash
# Check workflow file syntax
gh workflow view scheduled-security.yml

# Verify schedule format (cron syntax)
echo "0 2 * * 0" # Sunday 2:00 AM UTC

# Check workflow status
gh run list --workflow scheduled-security.yml
```

---

## Advanced Configuration

### Custom CronJob

Create custom CronJob for specific tasks:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: custom-task
  namespace: tradeadviser
spec:
  schedule: "0 0 * * *"  # Daily at midnight
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: task
            image: your-custom-image:latest
            command: ["python", "custom_task.py"]
          restartPolicy: OnFailure
```

### Monitoring CronJob Performance

```yaml
# Add Prometheus ServiceMonitor
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: cronjob-metrics
spec:
  selector:
    matchLabels:
      app: tradeadviser
```

---

## Resources

- [Kubernetes CronJobs](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [GitHub Actions Scheduling](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule)
- [Cron Syntax Reference](https://crontab.guru/)
- [RBAC in Kubernetes](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
