# aisomm-dev-server

A deployment automation server for managing and deploying multiple frontend and backend services. This project provides a set of Python scripts that automate the build, deployment, and restart process for Java backend services and Node.js frontend applications.

## Project Structure

```
aisomm-dev-server/
├── start.py              # Master deployment orchestrator
├── auto-deploy-fe.py     # Frontend deployment script
├── auto-deploy-be.py     # Backend deployment script
├── config/               # Configuration files
│   ├── lachaine-be.conf
│   ├── lachaine-fe.conf
│   └── lachaine-admin-fe.conf
└── index/
    └── index.html        # Deployment status overview page
```

## Scripts Overview

### start.py - Master Deployment Script

The main orchestrator that deploys all services in sequence. It pulls the latest scripts from git and manages the complete deployment workflow.

**Usage:**

```bash
python3 start.py
```

**Features:**

- Pulls latest scripts from the `release` branch
- Deploys services in order: LaChaine FE → LaChaine Admin FE → LaChaine BE
- Logs all operations to `/tmp/deploy-logs/`
- Provides colorized terminal output
- Generates deployment summary report
- Supports cron job scheduling

**Deployment Order:**

1. LaChaine Frontend
2. LaChaine Admin Frontend
3. LaChaine Backend

---

### auto-deploy-fe.py - Frontend Deployment Script

Automates the build and deployment of frontend applications (Vue, React, etc.) served by nginx.

**Usage:**

```bash
python3 auto-deploy-fe.py --conf <config-file> [--skip]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `--conf` | Path to configuration file (required) |
| `--skip` | Skip Git commit comparison and force rebuild |

**Features:**

- Git-based change detection (only builds if new commits exist)
- Automatic npm dependency installation
- Build artifact deployment to nginx web directory
- Automatic nginx restart after deployment
- User resource directory preservation (e.g., uploaded files)
- Optional remote server deployment via SCP
- Comprehensive logging

---

### auto-deploy-be.py - Backend Deployment Script

Automates the build and deployment of Java backend services using Maven.

**Usage:**

```bash
python3 auto-deploy-be.py --conf <config-file> [--skip]
```

**Arguments:**
| Argument | Description |
|----------|-------------|
| `--conf` | Path to configuration file (required) |
| `--skip` | Skip Git commit comparison and force rebuild |

**Features:**

- Git-based change detection (only builds if new commits exist)
- Maven build with optional test skipping
- JAR file deployment to target directory
- Service restart via stop/start scripts
- Process verification after startup
- Optional remote server deployment via SCP/SSH
- Comprehensive logging

---

## Configuration Files

Configuration files use a simple `KEY="value"` format:

### Backend Configuration (`config/lachaine-be.conf`)

```bash
# Required variables
PROJECT_NAME="LaChaine Backend"           # Display name for logging
PROJECT_DIR="/path/to/project"             # Git repository path
BRANCH="release"                           # Git branch to deploy
JAR_NAME="hk.com.lachaine.process.jar"     # Maven output JAR filename
DEPLOY_DIR="/project"                      # Deployment directory
STOP_SCRIPT="stop-lachaine-jar.sh"        # Service stop script
START_SCRIPT="start-lachaine-jar.sh"       # Service start script

# Optional variables
SKIP_TESTS="true"                          # Skip unit tests (default: true)
MVN_PATH="/usr/bin/mvn"                    # Maven executable path
REMOTE_ENABLED="false"                     # Enable remote deployment
REMOTE_HOST="www.example.com"              # Remote server hostname
REMOTE_USER="root"                         # Remote SSH user
REMOTE_DEPLOY_DIR="/project"               # Remote deployment path
LOG_FILE="/tmp/custom-deploy-be.log"       # Custom log file path
```

### Frontend Configuration (`config/lachaine-fe.conf`)

```bash
# Required variables
PROJECT_NAME="LaChaine Frontend"           # Display name for logging
PROJECT_DIR="/path/to/project"             # Git repository path
BRANCH="release"                           # Git branch to deploy
NPM_PATH="/usr/bin/npm"                    # npm executable path
BUILD_CMD="build:prd:nomap"                # npm build script name
SOURCE_DIR="dist"                          # Build output directory
DEPLOY_DIR="/var/www/html"                 # nginx web root
DEPLOY_DIR_NAME="dist-lachaine"            # Build artifact directory name
WEB_NAME="lachaine"                        # nginx served directory name

# Optional variables
RESOURCE_DIR="/var/www/html/lachaine/resources"  # User upload directory
REMOTE_ENABLED="false"                     # Enable remote deployment
REMOTE_HOST="www.example.com"              # Remote server hostname
REMOTE_USER="root"                         # Remote SSH user
DEPLOY_SCRIPT="deploy.sh"                  # Remote deploy trigger script
LOG_FILE="/tmp/custom-deploy-fe.log"       # Custom log file path
```

---

## Deployment Workflow

### Frontend Deployment Flow

```
1. Git Check → Compare local and remote commit hashes
2. Code Pull → git reset --hard origin/{branch}
3. Install  → npm install
4. Build    → npm run {BUILD_CMD}
5. Deploy   → Copy dist to nginx web directory
6. Nginx    → Restart nginx service
7. Remote   → (Optional) SCP to remote server
```

### Backend Deployment Flow

```
1. Git Check → Compare local and remote commit hashes
2. Code Pull → git reset --hard origin/{branch}
3. Build    → mvn clean install [-Dmaven.test.skip=true]
4. Copy     → Copy JAR to deploy directory
5. Stop     → Execute stop script
6. Start    → Execute start script (nohup)
7. Verify   → Check process is running
8. Remote   → (Optional) SCP JAR and restart remote service
```

---

## Log Files

All deployment logs are stored in `/tmp/deploy-logs/`:

| Log Type        | Filename Pattern                   |
| --------------- | ---------------------------------- |
| Main deploy log | `deploy-all-{timestamp}.log`       |
| Latest main log | `deploy-all-latest.log`            |
| Frontend log    | `fe-{config-name}-{timestamp}.log` |
| Backend log     | `be-{config-name}-{timestamp}.log` |
| Service log     | `{service-name}-latest.log`        |

---

## Cron Job Setup

To run deployments automatically on a schedule, add to crontab:

```bash
# Edit crontab
crontab -e

# Example: Run deployment daily at 2 AM
0 2 * * * /usr/bin/python3 /path/to/start.py >> /tmp/cron-deploy.log 2>&1

# Example: Run deployment every 6 hours
0 */6 * * * /usr/bin/python3 /path/to/start.py >> /tmp/cron-deploy.log 2>&1
```

---

## Prerequisites

### For Frontend Deployment

- Python 3.6+
- npm installed and accessible
- nginx installed and configured
- sudo privileges for nginx restart

### For Backend Deployment

- Python 3.6+
- Maven installed and accessible
- Java Runtime Environment
- Start/stop shell scripts in deploy directory

### General

- Git installed
- SSH access for remote deployments
- Write access to `/tmp/deploy-logs/`

---

## Troubleshooting

### Deployment Fails with "No change detected"

- Use `--skip` flag to force rebuild: `python3 auto-deploy-fe.py --conf config/lachaine-fe.conf --skip`

### nginx Restart Fails

- Ensure sudo privileges are available
- Check nginx configuration: `sudo nginx -t`

### Service Doesn't Start

- Check logs in deploy directory: `tail -f /path/to/deploy/auto.log`
- Verify JAR file exists: `ls -la /path/to/deploy/*.jar`
- Check start script permissions: `chmod +x start-*.sh`

### Remote Deployment Fails

- Verify SSH key authentication is configured
- Test connection: `ssh remote_user@remote_host`
- Check SCP permissions on remote server

---

## License

This project is for internal use by the aisomm development team.
