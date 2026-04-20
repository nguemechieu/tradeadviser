# CI/CD Pipeline Documentation

TradeAdviser uses GitHub Actions for comprehensive continuous integration, continuous deployment, and quality assurance.

## Workflow Overview

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| **Test** | test.yml | Push/PR | Run tests, security scans, coverage |
| **Build** | build.yml | Push/Tag | Build Docker images, push to registry |
| **Code Quality** | code-quality.yml | Push/PR | Code analysis, linting, SAST |
| **Deploy** | deploy.yml | Push/Tag | Deploy to staging and production |
| **Deploy K8s** | deploy-kubernetes.yml | Manual | Deploy to Kubernetes clusters |
| **Release** | release.yml | Tag/Manual | Create releases, generate changelogs |
| **Scheduled Security** | scheduled-security.yml | Weekly | Comprehensive security scanning |
| **Dependency Updates** | dependency-updates.yml | Weekly | Update and audit dependencies |
| **Scheduled Performance** | scheduled-performance.yml | Daily | Performance tests and DB checks |
| **Scheduled Maintenance** | scheduled-maintenance.yml | Daily | Backups, cleanup, reports |

## Workflows

### 1. Test Workflow (`.github/workflows/test.yml`)

**Triggers**: 
- Push to `main` or `develop` branches
- Pull requests to `main` branch

**Jobs**:

#### Backend Tests
- **Python Version**: 3.11
- **Database**: PostgreSQL 15 (service container)
- **Tests**: 
  - `pytest` with coverage reporting
  - `flake8` linting
  - `mypy` type checking
- **Output**: Coverage reports to Codecov

#### Frontend Tests
- **Node Version**: 18
- **Tests**:
  - `npm test` (Jest/React Testing Library)
  - `eslint` linting
  - `prettier` format checking
  - Build verification
- **Output**: Build artifacts validation

#### Security Scanning
- **Trivy**: Filesystem vulnerability scanning
- **Bandit**: Python security issue detection
- **Output**: SARIF format for GitHub Security tab

#### Code Coverage
- **Backend**: pytest-cov generates XML, HTML, and JSON reports
- **Frontend**: Jest coverage reporting
- **Codecov**: Automated upload and reporting to codecov.io
- **Badges**: Coverage badge in README links to Codecov dashboard

#### Test Status Aggregation
- Ensures all tests pass before workflow completion
- Blocks merge on test failure

**Required Secrets**: None

**Access Control**: Public workflows, no authentication needed

---

### 2. Build Workflow (`.github/workflows/build.yml`)

**Triggers**:
- Push to `main` or `develop` branches
- Tag creation (`v*` pattern)
- Manual trigger on pull requests (build only, no push)

**Jobs**:

#### Build Backend Image
- **Dockerfile**: `docker/Dockerfile.backend`
- **Python**: 3.11-slim
- **Registry**: GitHub Container Registry (ghcr.io)
- **Tags**:
  - Branch name (e.g., `main`, `develop`)
  - Semantic version (e.g., `v1.0.0`, `1.0`)
  - Git SHA (short commit hash)
- **Cache**: Uses buildx cache for faster builds

#### Build Frontend Image
- **Dockerfile**: `docker/Dockerfile.frontend`
- **Node**: 18-alpine (multi-stage build)
- **Registry**: GitHub Container Registry (ghcr.io)
- **Tags**: Same as backend
- **Cache**: Uses buildx cache

#### Scan Images
- Runs only on push (not PRs)
- Scans backend image with Trivy
- Uploads results to GitHub Security tab

**Environment Variables**:
```
REGISTRY: ghcr.io
BACKEND_IMAGE: ${{ github.repository }}/backend
FRONTEND_IMAGE: ${{ github.repository }}/frontend
```

**Required Secrets**: 
- `GITHUB_TOKEN` (automatic)

**Image Naming**:
```
ghcr.io/your-org/tradeadviser/backend:tag
ghcr.io/your-org/tradeadviser/frontend:tag
```

---

### 3. Deploy Workflow (`.github/workflows/deploy.yml`)

**Triggers**:
- Push to `develop` (deploys to staging)
- Tag creation (deploys to production)

**Jobs**:

#### Deploy to Staging
- **Trigger**: Push to `develop` branch
- **Environment**: Staging
- **URL**: https://staging-tradeadviser.org
- **Steps**:
  1. SSH connection to staging server
  2. Pull latest code
  3. Pull latest Docker images
  4. Run `docker-compose up -d`
  5. Run database migrations (`alembic upgrade head`)
  6. Health check (30 attempts, 10-second intervals)
  7. Slack notification

#### Deploy to Production
- **Trigger**: Tag creation (v-prefixed)
- **Environment**: Production
- **URL**: https://tradeadviser.org
- **Steps**:
  1. SSH connection to production server
  2. Checkout tag
  3. Pull latest Docker images
  4. Run `docker-compose up -d`
  5. Run database migrations
  6. Health check
  7. Create GitHub Release
  8. Slack notification

#### Automatic Rollback
- **Trigger**: Production deployment failure
- **Steps**:
  1. Checkout previous commit
  2. Restart services
  3. Slack notification

**Required Secrets**:
```
STAGING_DEPLOY_KEY        # SSH private key for staging
STAGING_HOST              # Staging server IP/hostname
STAGING_USER              # SSH user for staging
PRODUCTION_DEPLOY_KEY     # SSH private key for production
PRODUCTION_HOST           # Production server IP/hostname
PRODUCTION_USER           # SSH user for production
SLACK_WEBHOOK             # Slack webhook URL for notifications
```

**Health Check**:
- Polls `/health` endpoint
- 30 attempts with 10-second interval (5 minutes total)
- Fails if endpoint not responding

**Notifications**:
- Success: ✅ Staging/Production deployment successful
- Failure: ⚠️ Production rollback performed

---

### 4. Code Quality Workflow (`.github/workflows/code-quality.yml`)

**Triggers**:
- Push to `main` or `develop`
- Pull requests to `main` or `develop`

**Jobs**:

#### Code Quality Checks
- **Backend**:
  - `black` - Code formatting check
  - `isort` - Import sorting
  - `pylint` - Code quality analysis
  - `flake8` - Style and error detection
- **Frontend**:
  - `prettier` - Code formatting check
  - `eslint` - Code quality and standards
- **SAST**:
  - `SonarCloud` - Code analysis and coverage
  - `Semgrep` - Static analysis (OWASP Top 10)

#### Dependency Check
- **Python**:
  - `pip-audit` - Dependency vulnerabilities
  - `safety` - Python package vulnerabilities
- **Node**:
  - `npm audit` - NPM package vulnerabilities
  - `npm outdated` - Outdated packages

#### License Check
- Validates license headers in source files
- Checks documentation presence

#### Architecture Compliance
- Ensures backend doesn't import from frontend
- Ensures frontend doesn't directly import backend
- Prevents architectural violations

#### Documentation Check
- Validates README.md exists
- Validates ARCHITECTURE.md exists
- Validates Markdown syntax

**Required Secrets**:
```
SONAR_TOKEN    # SonarCloud authentication token
```

**Failure Behavior**:
- Code formatting issues: ❌ Fail (use `black .` and `prettier --write` locally)
- Linting errors: ❌ Fail (fix warnings and errors)
- Vulnerability scan: ⚠️ Report (can continue)
- Dependency outdated: ⚠️ Report (can continue)

---

### 5. Kubernetes Deployment Workflow (`.github/workflows/deploy-kubernetes.yml`)

**Triggers**:
- Manual workflow dispatch with environment and cluster selection

**Jobs**:

#### kubectl Deployment
- **Manual Trigger**: Select environment (staging/production) and cluster (AKS/EKS/GKE)
- **Steps**:
  1. Azure login (for AKS)
  2. Set cluster context
  3. Create namespace and secrets
  4. Deploy PostgreSQL
  5. Deploy backend and frontend
  6. Apply ingress configuration
  7. Health checks
  8. Slack notification

#### Helm Deployment (Production)
- **Optional**: Deploy using Helm charts
- **Steps**:
  1. Set up Helm
  2. Add Helm repositories
  3. Deploy with Helm upgrade/install
  4. Verify deployment status

**Cluster Support**:
- Azure Kubernetes Service (AKS)
- Amazon Elastic Kubernetes Service (EKS)
- Google Kubernetes Engine (GKE)
- Self-hosted Kubernetes

**Required Secrets**:
```
AZURE_CREDENTIALS        # For AKS
AKS_RESOURCE_GROUP       # AKS resource group
AKS_CLUSTER_NAME         # AKS cluster name
DATABASE_URL             # PostgreSQL connection
SECRET_KEY               # FastAPI secret
JWT_SECRET               # JWT signing key
REGISTRY                 # Container registry URL
SLACK_WEBHOOK            # For notifications
```

---

### 6. Release Workflow (`.github/workflows/release.yml`)

**Triggers**:
- Tag creation (v-prefixed, e.g., `v1.0.0`)
- Manual workflow trigger with version input

**Jobs**:

#### Create Release
- **Version Format**: Semantic versioning (v1.0.0)
- **Steps**:
  1. Extract version from tag or input
  2. Update version in files (on manual trigger)
  3. Generate changelog from git history
  4. Create GitHub Release with notes
  5. Push tag (on manual trigger)
  6. Slack notification

#### Release Content
- Release notes with changelog
- Docker image pull commands
- Links to documentation
- Installation instructions

#### Publish Packages
- Ready for PyPI (backend) - currently disabled
- Ready for NPM (frontend) - currently disabled
- Can enable by setting `if: true` in steps

**Required Secrets**:
```
SLACK_WEBHOOK         # Slack notification
PYPI_API_TOKEN        # For PyPI publishing (optional)
NPM_TOKEN             # For NPM publishing (optional)
```

**Manual Release**:
```bash
# Via GitHub Actions UI:
# 1. Go to Actions > Release
# 2. Click "Run workflow"
# 3. Enter version (e.g., 1.0.0)
```

**Automatic Release**:
```bash
# Push a version tag:
git tag v1.0.0
git push origin v1.0.0
```

---

## Coverage Reporting

Code coverage is automatically collected and reported during CI/CD pipeline execution.

### Coverage Tools

- **Backend**: pytest-cov with XML and JSON output
- **Frontend**: Jest with LCOV format
- **Reporting**: Codecov.io integration with GitHub PR comments

### Coverage Targets

```yaml
Project Coverage: 70% minimum
Patch Coverage: 80% minimum  
Branches: main and develop
```

### Viewing Coverage

- **Codecov Dashboard**: https://codecov.io/gh/sopotek/tradeadviser
- **GitHub PR Comments**: Automatic coverage status on pull requests
- **Local Reports**: `backend/htmlcov/` and `frontend/coverage/`

### Configuration

Coverage settings in `codecov.yml`:
- Target thresholds for project and patch
- Flags for backend and frontend
- Ignore patterns for tests and build artifacts
- Carryforward settings for coverage tracking

**Full Coverage Guide**: See [COVERAGE.md](COVERAGE.md)

---

Add these to your README.md:

```markdown
![Test](https://github.com/your-org/tradeadviser/workflows/Test/badge.svg)
![Build](https://github.com/your-org/tradeadviser/workflows/Build%20Docker%20Images/badge.svg)
![Deploy](https://github.com/your-org/tradeadviser/workflows/Deploy%20to%20Environments/badge.svg)
![Code Quality](https://github.com/your-org/tradeadviser/workflows/Code%20Quality/badge.svg)
```

---

## GitHub Secrets Setup

### Required Secrets

```bash
# Repository > Settings > Secrets and variables > Actions > New repository secret

# Deployment
STAGING_DEPLOY_KEY=<ssh-private-key>
STAGING_HOST=staging.example.com
STAGING_USER=deploy
PRODUCTION_DEPLOY_KEY=<ssh-private-key>
PRODUCTION_HOST=prod.example.com
PRODUCTION_USER=deploy

# Notifications
SLACK_WEBHOOK=https://hooks.slack.com/services/...

# Code Quality
SONAR_TOKEN=<sonarcloud-token>
```

### Optional Secrets

```bash
# Package Publishing
PYPI_API_TOKEN=<pypi-token>
NPM_TOKEN=<npm-token>
```

---

## Environment Configuration

### Staging Environment
- **URL**: https://staging-tradeadviser.org
- **Branch**: develop
- **Deployment**: Automatic on push
- **Health Check**: Required before marking success
- **Rollback**: Manual

### Production Environment
- **URL**: https://tradeadviser.org
- **Branch**: main (via tags)
- **Deployment**: On version tag
- **Health Check**: Required before marking success
- **Rollback**: Automatic on failure

---

## Workflow Sequence

```
┌─────────────────────────────────────────────┐
│ Developer pushes code or creates tag        │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
   ┌────▼────┐           ┌───▼───┐
   │ PUSH    │           │ TAG   │
   └────┬────┘           └───┬───┘
        │                    │
    ┌───▼───────────────┐   │
    │ Test Workflow     │   │
    │ - Backend tests   │   │
    │ - Frontend tests  │   │
    │ - Security scans  │   │
    └───┬───────────────┘   │
        │ (success)         │
        │                   │
    ┌───▼──────────────┐    │
    │ Build Workflow   │    │
    │ - Docker build   │    │
    │ - Push to ghcr   │    │
    │ - Image scan     │    │
    └───┬──────────────┘    │
        │                   │
   ┌────┴────────────┐      │
   │                 │      │
   (develop)    (main/tag)  │
   │                 │      │
┌──▼─────┐     ┌────▼─────┐
│ Staging │     │ Production
│ Deploy  │     │ Deploy
└─────────┘     │
                ├─ Migrations
                ├─ Health check
                ├─ Create Release
                └─ Rollback on fail
```

---

## Troubleshooting

### Test Workflow Fails

**Backend Tests**:
```bash
# Run locally:
cd backend
pytest -v --cov=.
```

**Frontend Tests**:
```bash
# Run locally:
cd frontend
npm test
```

### Build Workflow Fails

**Docker Build Issue**:
```bash
# Build locally:
docker build -f docker/Dockerfile.backend -t tradeadviser-backend:test .
docker build -f docker/Dockerfile.frontend -t tradeadviser-frontend:test .
```

### Deploy Workflow Fails

**SSH Connection Issue**:
- Verify SSH key in GitHub secrets
- Check server IP/hostname
- Verify deploy user permissions
- Check server firewall rules

**Health Check Timeout**:
- Verify `/health` endpoint exists
- Check logs on deployment server
- Verify port 443/80 accessible

### Code Quality Fails

**Format Issues**:
```bash
# Backend:
cd backend
black .
isort .

# Frontend:
cd frontend
npx prettier --write src/
```

---

## Best Practices

### Branch Strategy

```
main          - Production release branch (tags only)
develop       - Staging deployment branch
feature/*     - Feature branches (squash merge to develop)
bugfix/*      - Bug fix branches (squash merge to develop)
hotfix/*      - Production hotfixes (merge to both main and develop)
```

### Commit Messages

Use conventional commits:

```
feat: add new trading signal
fix: resolve portfolio calculation bug
docs: update API documentation
test: add unit tests for risk service
chore: update dependencies
```

### Version Tagging

```
v1.0.0     - Release version
v1.0.0-rc1 - Release candidate
v1.0.0-beta - Beta release
```

### Release Frequency

- **Hotfixes**: As needed
- **Staging**: Continuous (develop branch)
- **Production**: Weekly or bi-weekly (versioned releases)

---

## Advanced Configuration

### Add Slack Notifications

For detailed notifications per step:

```yaml
- name: Slack notification
  uses: slackapi/slack-github-action@v1.24.0
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK }}
```

### Add Docker Hub Support

Replace GitHub Container Registry with Docker Hub:

```yaml
env:
  REGISTRY: docker.io
  BACKEND_IMAGE: ${{ secrets.DOCKER_HUB_USERNAME }}/tradeadviser-backend
  FRONTEND_IMAGE: ${{ secrets.DOCKER_HUB_USERNAME }}/tradeadviser-frontend
```

### Add Cloud Deployments

For AWS, Azure, or GCP, replace SSH deployment with cloud CLI:

**AWS**:
```yaml
- name: Deploy to AWS
  run: |
    aws ecs update-service --cluster prod --service tradeadviser --force-new-deployment
```

**Azure**:
```yaml
- name: Deploy to Azure
  run: |
    az containerapp up --resource-group prod --name tradeadviser
```

---

## Scheduled Workflows

Automated workflows run on a regular schedule for maintenance, security, and testing.

### Scheduled Security Scan

**File**: `.github/workflows/scheduled-security.yml`  
**Schedule**: Every Sunday at 2:00 AM UTC (`0 2 * * 0`)  
**What it does**:
- Trivy container and filesystem scan
- Bandit Python security checks
- SonarCloud code analysis
- OWASP Top 10 scanning via Semgrep
- Generates security reports
- Alerts on vulnerabilities

**Results**:
- Security tab in GitHub
- GitHub Actions artifacts
- Slack notifications (if configured)

### Dependency Updates

**File**: `.github/workflows/dependency-updates.yml`  
**Schedule**: Every Monday at 9:00 AM UTC (`0 9 * * 1`)  
**What it does**:
- Updates Python packages (`pip-compile --upgrade`)
- Updates Node.js packages (`npm update`)
- Fixes security vulnerabilities
- Runs full test suite
- Creates PR with updates if changes detected
- Scans for vulnerability issues

**Results**:
- Dependency update PR
- Vulnerability report
- Test results
- Upgrade summary

### Scheduled Performance Tests

**File**: `.github/workflows/scheduled-performance.yml`  
**Schedule**: Daily at 11:00 PM UTC (`0 23 * * *`)  
**What it does**:
- Runs backend performance benchmarks
- Analyzes frontend build size
- Checks database integrity
- Generates performance reports

**Artifacts**:
- `performance-report.md` - Summary
- `benchmark-data` - Detailed metrics
- `integrity-report` - Database health

### Scheduled Maintenance

**File**: `.github/workflows/scheduled-maintenance.yml`  
**Multiple schedules**:
- Database backup: Daily 2:00 AM UTC
- Database cleanup: Daily 3:00 AM UTC
- Weekly report: Monday 8:00 AM UTC

**What it does**:
- Verifies database backups
- Documents cleanup tasks
- Generates weekly maintenance reports
- Monitors uptime and SLA compliance

### Kubernetes CronJobs

TradeAdviser uses Kubernetes CronJobs for in-cluster scheduled tasks:

| Task | Schedule | Purpose |
|------|----------|---------|
| PostgreSQL Backup | Daily 2:00 AM UTC | Database backups |
| Database Cleanup | Daily 3:00 AM UTC | Data maintenance |
| Health Check | Every 5 minutes | Service monitoring |
| Pod Resource Cleanup | Daily 4:00 AM UTC | Pod cleanup |

See [CRONJOBS.md](./CRONJOBS.md) for detailed documentation on Kubernetes CronJobs.

---

## Support

For issues with CI/CD workflows:

1. Check [GitHub Actions Logs](#) for detailed error messages
2. Review this documentation
3. Check backend and frontend test results locally
4. Open issue with workflow logs attached
