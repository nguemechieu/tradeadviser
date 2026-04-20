#!/bin/bash
# CI/CD Setup Checklist for TradeAdviser
# This script provides a quick checklist for setting up CI/CD

cat << 'EOF'
╔════════════════════════════════════════════════════════════╗
║       TradeAdviser CI/CD Pipeline Setup Checklist         ║
╚════════════════════════════════════════════════════════════╝

✅ GitHub Actions Workflows Created:
   ✓ .github/workflows/test.yml           - Testing & Security
   ✓ .github/workflows/build.yml          - Docker Build & Push
   ✓ .github/workflows/deploy.yml         - Deploy to Staging/Prod
   ✓ .github/workflows/code-quality.yml   - Code Analysis
   ✓ .github/workflows/release.yml        - Release Management

📚 Documentation Created:
   ✓ docs/CI_CD.md                        - Complete CI/CD guide
   ✓ README.md updated                    - CI/CD badges & section

════════════════════════════════════════════════════════════

NEXT STEPS TO ACTIVATE CI/CD:

1. GitHub Repository Setup
   ☐ Push these changes to main/develop branch
   ☐ Go to: Settings > Actions > General
   ☐ Enable Actions workflows

2. Configure GitHub Secrets (Settings > Secrets and variables > Actions)
   
   REQUIRED - Deployment:
   ☐ STAGING_DEPLOY_KEY    - SSH private key for staging server
   ☐ STAGING_HOST          - staging.example.com
   ☐ STAGING_USER          - deploy user (e.g., 'deploy')
   ☐ PRODUCTION_DEPLOY_KEY - SSH private key for prod server
   ☐ PRODUCTION_HOST       - prod.example.com
   ☐ PRODUCTION_USER       - deploy user
   ☐ SLACK_WEBHOOK         - https://hooks.slack.com/services/...

   OPTIONAL - Code Quality:
   ☐ SONAR_TOKEN           - From https://sonarcloud.io

   OPTIONAL - Publishing:
   ☐ PYPI_API_TOKEN        - From https://pypi.org
   ☐ NPM_TOKEN             - From https://npmjs.com

3. Server Setup (Staging & Production)
   ☐ Install Docker & Docker Compose
   ☐ Create 'deploy' user with Docker permissions
   ☐ Generate SSH keys for GitHub deployment
   ☐ Add GitHub public key to ~/.ssh/authorized_keys
   ☐ Create /app/tradeadviser directory
   ☐ Verify SSH connection works

4. Nginx/Load Balancer Setup
   ☐ Configure reverse proxy (nginx.conf provided)
   ☐ Set up SSL certificates
   ☐ Configure health check endpoint (/health)
   ☐ Test health check: curl https://staging-tradeadviser.org/health

5. Database Setup
   ☐ PostgreSQL 15+ installed on servers
   ☐ Database created: 'tradeadviser'
   ☐ Alembic migrations configured
   ☐ Run migrations before first deployment

6. Environment Files
   ☐ Copy .env.example to servers as .env
   ☐ Update secrets in .env (API keys, DB credentials, etc.)
   ☐ Verify all required variables are set

════════════════════════════════════════════════════════════

WORKFLOW ACTIVATION ORDER:

Phase 1 - Testing (Automatic on first push)
  └─ Test workflow runs on every push/PR
     ├─ Backend tests (pytest)
     ├─ Frontend tests (npm test)
     ├─ Security scans (Trivy, Bandit)
     └─ Code quality (flake8, eslint)

Phase 2 - Building (Requires Phase 1 to pass)
  └─ Build workflow creates Docker images
     ├─ Backend image built
     ├─ Frontend image built
     ├─ Images pushed to ghcr.io
     └─ Vulnerability scan on images

Phase 3 - Staging Deployment (Automatic on develop branch)
  └─ Deploy workflow deploys to staging
     ├─ Pull latest code
     ├─ Pull Docker images
     ├─ Run database migrations
     ├─ Health check
     └─ Slack notification

Phase 4 - Production Deployment (On version tag)
  └─ Deploy to production
     ├─ Checkout tagged version
     ├─ Run migrations
     ├─ Health check
     ├─ Create GitHub Release
     ├─ Automatic rollback if fails
     └─ Slack notification

════════════════════════════════════════════════════════════

TESTING WORKFLOWS LOCALLY:

# Run backend tests locally
cd backend
pytest -v --cov=.

# Run frontend tests locally
cd frontend
npm test

# Check code quality
cd backend && black --check . && flake8 .
cd frontend && npx eslint src/

# Build Docker images locally
docker build -f docker/Dockerfile.backend -t tradeadviser-backend:test .
docker build -f docker/Dockerfile.frontend -t tradeadviser-frontend:test .

════════════════════════════════════════════════════════════

DEPLOYMENT WORKFLOW:

1. Feature Development
   $ git checkout -b feature/new-trading-signal

2. Local Testing
   $ cd backend && pytest
   $ cd frontend && npm test

3. Commit & Push
   $ git commit -m "feat: add new trading signal"
   $ git push origin feature/new-trading-signal

4. Create Pull Request
   ✓ GitHub Actions test workflow runs
   ✓ All tests pass (required for merge)
   ✓ Code quality checks pass

5. Merge to Develop
   $ git merge --squash feature/new-trading-signal

6. Automatic Staging Deployment
   ✓ Test workflow runs
   ✓ Build workflow creates images
   ✓ Deploy workflow deploys to staging
   ✓ Health check verifies deployment

7. Create Release Tag
   $ git tag v1.0.0
   $ git push origin v1.0.0

8. Automatic Production Deployment
   ✓ Test workflow runs
   ✓ Build workflow creates images
   ✓ Deploy workflow deploys to production
   ✓ GitHub Release created
   ✓ Rollback triggered if deployment fails

════════════════════════════════════════════════════════════

TROUBLESHOOTING:

Q: Build workflow fails with "docker push rate limited"
A: Configure Docker Hub credentials in GitHub Secrets
   or use GitHub Container Registry (recommended)

Q: Deployment fails with "SSH connection refused"
A: 1. Verify SSH key in GitHub Secrets
   2. Check server IP/hostname
   3. Verify deploy user has SSH access
   4. Test SSH manually: ssh -i key deploy@host

Q: Health check timeout on deployment
A: 1. Verify /health endpoint exists
   2. Check deployment logs: docker-compose logs backend
   3. Verify port 443/80 accessible
   4. Check Nginx configuration

Q: Test workflow fails inconsistently
A: 1. Check PostgreSQL service is running
   2. Verify test database is clean
   3. Check for race conditions in tests
   4. Run tests locally: pytest -v

════════════════════════════════════════════════════════════

MONITORING:

After deployment, monitor via:
  
1. GitHub Actions Dashboard
   https://github.com/sopotek/tradeadviser/actions

2. Workflow Logs
   https://github.com/sopotek/tradeadviser/actions/workflows/test.yml

3. Deployment Status
   https://github.com/sopotek/tradeadviser/deployments

4. Application Health
   https://staging-tradeadviser.org/health
   https://tradeadviser.org/health

5. Slack Notifications (if webhook configured)
   #deployments channel

════════════════════════════════════════════════════════════

DOCUMENTATION:

📖 Full CI/CD Documentation: docs/CI_CD.md
📖 Architecture Guide: docs/ARCHITECTURE.md
📖 Deployment Guide: docs/DEPLOYMENT.md
📖 Contributing Guide: docs/CONTRIBUTING.md

════════════════════════════════════════════════════════════

SUPPORT:

For issues:
1. Check workflow logs in GitHub Actions
2. Review docs/CI_CD.md troubleshooting section
3. Check application logs on servers
4. Open issue with workflow logs

════════════════════════════════════════════════════════════
EOF
