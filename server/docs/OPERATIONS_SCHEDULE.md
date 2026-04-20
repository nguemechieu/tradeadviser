# Operations Schedule

Complete schedule of all automated operations for TradeAdviser.

## Daily Schedule (UTC)

### 2:00 AM UTC
**Database Backup**
- **Type**: Kubernetes CronJob
- **File**: `k8s/cronjobs.yaml`
- **Task**: PostgreSQL backup (pg_dump)
- **Storage**: 50Gi persistent volume
- **Retention**: 7 days
- **ServiceAccount**: `tradeadviser-backup`
- **Resources**: 256Mi memory, 250m CPU
- **Success Rate Target**: 100%

### 3:00 AM UTC
**Database Cleanup**
- **Type**: Kubernetes CronJob
- **File**: `k8s/cronjobs.yaml`
- **Tasks**:
  - Delete sessions > 30 days
  - Delete audit logs > 90 days
  - Delete failed trades > 7 days
  - ANALYZE and VACUUM
- **ServiceAccount**: `tradeadviser-maintenance`
- **Resources**: 256Mi memory, 250m CPU
- **Expected Duration**: 5-15 minutes
- **Expected Space Freed**: 5-10%

### 4:00 AM UTC
**Pod Resource Cleanup**
- **Type**: Kubernetes CronJob
- **File**: `k8s/cronjobs.yaml`
- **Tasks**:
  - Delete evicted pods
  - Delete failed pods
  - Delete succeeded pods > 1 day
- **ServiceAccount**: `tradeadviser-cleanup`
- **Resources**: 64Mi memory, 50m CPU
- **RBAC**: Pod get, list, delete permissions

### 8:00 AM UTC (Monday only)
**Weekly Maintenance Report**
- **Type**: GitHub Actions Workflow
- **File**: `.github/workflows/scheduled-maintenance.yml`
- **Tasks**:
  - Generate maintenance summary
  - List completed tasks
  - Highlight upcoming maintenance
  - Report any issues
- **Output**: GitHub Actions artifact + Slack notification

### 9:00 AM UTC (Monday only)
**Dependency Updates**
- **Type**: GitHub Actions Workflow
- **File**: `.github/workflows/dependency-updates.yml`
- **Tasks**:
  - Python: `pip-compile --upgrade`
  - Node.js: `npm update`
  - Fix vulnerabilities: `npm audit fix`
  - Run full test suite
  - Create PR if updates detected
- **Duration**: 20-30 minutes
- **Output**: PR + vulnerability report + Slack notification
- **Artifacts**:
  - `dependency-updates.md` - Summary
  - `vulnerability-report.json` - Details

### 11:00 PM UTC (Daily)
**Performance Tests**
- **Type**: GitHub Actions Workflow
- **File**: `.github/workflows/scheduled-performance.yml`
- **Tasks**:
  - Backend: pytest-benchmark
  - Frontend: build size analysis
  - Database: integrity checks
  - Load test configuration validation
- **Duration**: 15-25 minutes
- **Output**: Benchmark data + performance report + Slack notification
- **Artifacts**:
  - `benchmark.json` - Performance metrics
  - `performance-report.md` - Summary
  - `integrity-report.md` - Database health

### 2:00 AM UTC (Sunday only)
**Security Scan**
- **Type**: GitHub Actions Workflow
- **File**: `.github/workflows/scheduled-security.yml`
- **Tasks**:
  - Trivy: Full filesystem scan
  - Bandit: Python security checks
  - SonarCloud: Code analysis
  - Semgrep: OWASP Top 10 checks
- **Duration**: 10-20 minutes
- **Output**: SARIF + security report + Slack notification
- **Severity**: Reports CRITICAL and HIGH issues
- **Artifacts**:
  - `security-report.sarif` - GitHub Security tab upload
  - `vulnerability-summary.json` - Summary

---

## Weekly Schedule

### Sunday - 2:00 AM UTC
**Security Scan** (see Daily Schedule)

### Monday - 8:00 AM UTC
**Weekly Maintenance Report** (see Daily Schedule)

### Monday - 9:00 AM UTC
**Dependency Updates** (see Daily Schedule)

---

## Every 5 Minutes (24/7)
**Health Check**
- **Type**: Kubernetes CronJob
- **File**: `k8s/cronjobs.yaml`
- **Tasks**:
  - Check backend `/health` endpoint
  - Check frontend HTTP response
  - Check database connectivity
- **Resources**: 64Mi memory, 50m CPU
- **Output**: CronJob events, logs
- **Timeout**: 30 seconds
- **Retries**: 3 attempts

---

## Timeline Visualization

### Daily Timeline

```
00:00 UTC ├─ Midnight
          │
02:00 UTC ├─ Database Backup
          │  └─ pg_dump (15-30 min)
          │
03:00 UTC ├─ Database Cleanup
          │  └─ Purge + VACUUM (10-15 min)
          │
04:00 UTC ├─ Pod Cleanup
          │  └─ Clean failed/succeeded pods (5-10 min)
          │
08:00 UTC ├─ Weekly Maintenance Report (Monday only)
          │  └─ Generate weekly summary (5-10 min)
          │
09:00 UTC ├─ Dependency Updates (Monday only)
          │  └─ Update deps + tests (20-30 min)
          │
12:00 UTC ├─ Noon
          │
23:00 UTC ├─ Performance Tests
          │  └─ Run benchmarks (15-25 min)
          │
...       └─ Every 5 minutes: Health Check
```

### Weekly Timeline

```
Monday     08:00 AM ├─ Maintenance Report
Monday     09:00 AM ├─ Dependency Updates
           ...      ├─ (Daily tasks throughout week)
Sunday     02:00 AM ├─ Security Scan
           ...      └─ (Health check every 5 min, daily tasks)
```

---

## Operational Considerations

### Backup Window

**Database Backup: 2:00 AM UTC**
- Non-peak trading hours recommended
- 15-30 minute operation
- No database locks (online backup)
- Stored in persistent volume with 7-day retention

### Maintenance Window

**Database Cleanup: 3:00 AM UTC**
- Follows backup to ensure clean state
- 10-15 minute operation
- May cause slight performance impact
- Reclaims 5-10% of database space

### Health Check Frequency

**Every 5 minutes, 24/7**
- Lightweight HTTP checks
- No database impact
- Enables early detection of failures
- Keeps job history for debugging

### Performance Testing

**11:00 PM UTC Daily**
- After trading hours
- Non-blocking operation
- Measures performance trends
- Identifies regressions

### Security Scanning

**Sunday 2:00 AM UTC**
- Weekly comprehensive scan
- Checks latest vulnerability databases
- Reports critical and high severity issues
- Alerts team on findings

### Dependency Updates

**Monday 9:00 AM UTC**
- Weekly automated updates
- Full test suite before PR
- Prioritizes security fixes
- Creates detailed PR for review

---

## Failure Handling

### CronJob Failures

**Automatic Retry**:
- Failed CronJobs retry 3 times
- 5-minute backoff between retries
- History: last 3 successes, last 1 failure

**Alerts**:
- Slack notification on failure
- GitHub Actions status check
- Email notification (if configured)

### Workflow Failures

**GitHub Actions**:
- Automatic email notification
- Slack notification if configured
- GitHub Actions dashboard shows status
- Artifacts available for debugging

**Manual Recovery**:
```bash
# Re-run failed workflow
gh run rerun <run-id>

# Manually trigger workflow
gh workflow run scheduled-security.yml
```

---

## Monitoring

### CronJob Monitoring

```bash
# View all CronJobs
kubectl get cronjobs -n tradeadviser

# Get CronJob details
kubectl describe cronjob postgres-backup -n tradeadviser

# View recent jobs
kubectl get jobs -n tradeadviser --sort-by=.metadata.creationTimestamp

# View job logs
kubectl logs -l cronjob-name=postgres-backup -n tradeadviser
```

### Workflow Monitoring

```bash
# List workflows
gh workflow list

# View recent runs
gh run list --workflow scheduled-security.yml

# Get run details
gh run view <run-id>
```

### Metrics to Track

- **Backup size**: Growth rate and retention
- **Cleanup duration**: Time to execute
- **Health check success rate**: Should be 99.9%+
- **Performance test results**: Trend analysis
- **Security scan findings**: Vulnerability count
- **Dependency update frequency**: PRs created
- **Job failure rate**: Should be 0%

---

## Resource Allocation

### Daily Operations Impact

| Operation | Memory | CPU | Duration | I/O Impact |
|-----------|--------|-----|----------|-----------|
| DB Backup | 256Mi | 250m | 20-30 min | High |
| DB Cleanup | 256Mi | 250m | 10-15 min | High |
| Pod Cleanup | 64Mi | 50m | 5-10 min | Low |
| Health Check | 64Mi | 50m | 1-2 sec | Low |
| Perf Tests | 2Gi | 1000m | 20 min | Medium |

**Total Daily**: ~4Gi memory, ~2600m CPU (peak)

### GitHub Actions Impact

- Dependency Updates: 1 runner, 30 min
- Security Scan: 1 runner, 20 min
- Performance Tests: 1 runner, 25 min
- Weekly Report: 1 runner, 10 min

**Total Weekly**: ~3-4 hours compute

---

## Maintenance Mode

### Disable All CronJobs

```bash
kubectl patch cronjob postgres-backup -n tradeadviser -p '{"spec" : {"suspend" : true }}'
kubectl patch cronjob database-cleanup -n tradeadviser -p '{"spec" : {"suspend" : true }}'
kubectl patch cronjob health-check -n tradeadviser -p '{"spec" : {"suspend" : true }}'
kubectl patch cronjob pod-resource-cleanup -n tradeadviser -p '{"spec" : {"suspend" : true }}'
```

### Re-enable All CronJobs

```bash
kubectl patch cronjob postgres-backup -n tradeadviser -p '{"spec" : {"suspend" : false }}'
kubectl patch cronjob database-cleanup -n tradeadviser -p '{"spec" : {"suspend" : false }}'
kubectl patch cronjob health-check -n tradeadviser -p '{"spec" : {"suspend" : false }}'
kubectl patch cronjob pod-resource-cleanup -n tradeadviser -p '{"spec" : {"suspend" : false }}'
```

### Disable GitHub Actions Workflows

Set environment variable:
```bash
DISABLE_SCHEDULED_WORKFLOWS=true
```

Or disable individual workflows:
```bash
gh workflow disable scheduled-security.yml
gh workflow disable dependency-updates.yml
```

---

## Customization

### Change Backup Time

Edit `k8s/cronjobs.yaml`:
```yaml
schedule: "0 2 * * *"  # Current: 2:00 AM UTC
schedule: "0 0 * * *"  # Change to: Midnight UTC
```

### Change Cleanup Time

Edit `k8s/cronjobs.yaml`:
```yaml
schedule: "0 3 * * *"  # Current: 3:00 AM UTC
schedule: "0 1 * * *"  # Change to: 1:00 AM UTC
```

### Change Workflow Schedules

Edit `.github/workflows/scheduled-*.yml`:
```yaml
schedule:
  - cron: '0 2 * * 0'  # Current: Sunday 2 AM UTC
  - cron: '0 2 * * 1'  # Change to: Monday 2 AM UTC
```

### Cron Schedule Syntax

- `*` any value
- `,` value list
- `-` range
- `/` step values

**Examples**:
- `0 2 * * *` - 2:00 AM every day
- `0 2 * * 0` - 2:00 AM every Sunday
- `0 2 * * 1` - 2:00 AM every Monday
- `*/5 * * * *` - Every 5 minutes
- `0 */6 * * *` - Every 6 hours

See [crontab.guru](https://crontab.guru/) for visualization.

---

## References

- [Kubernetes CronJobs Documentation](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/)
- [GitHub Actions Scheduling](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule)
- [Cron Syntax Guide](https://crontab.guru/)
- [TradeAdviser CRONJOBS.md](./CRONJOBS.md)
- [TradeAdviser CI_CD.md](./CI_CD.md)
