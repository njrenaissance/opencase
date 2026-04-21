#!/bin/bash
# Collect environment information for bug reports
# Usage: ./collect-environment.sh

set -e

echo "⚠️  IMPORTANT: Review the output below carefully before posting in a bug report."
echo "   Redact any secrets, credentials, or sensitive environment variables."
echo ""
echo "# Gideon Environment Information"
echo ""
echo "## System"
echo "- **OS**: $(uname -s) $(uname -r)"
echo "- **Architecture**: $(uname -m)"
echo ""

echo "## Docker"
if command -v docker &> /dev/null; then
  echo "- **Docker version**: $(docker --version)"
else
  echo "- **Docker version**: Not installed"
fi

if command -v docker-compose &> /dev/null; then
  echo "- **Docker Compose version**: $(docker-compose --version)"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
  echo "- **Docker Compose version**: $(docker compose version)"
else
  echo "- **Docker Compose version**: Not installed"
fi
echo ""

echo "## Gideon"
if [ -f ".env" ]; then
  if grep -q "^DEPLOYMENT_MODE=" .env; then
    echo "- **Deployment mode**: $(grep '^DEPLOYMENT_MODE=' .env | cut -d'=' -f2 | tr -d '"')"
  fi
fi

if git rev-parse --git-dir > /dev/null 2>&1; then
  echo "- **Git commit**: $(git rev-parse --short HEAD)"
  echo "- **Git branch**: $(git rev-parse --abbrev-ref HEAD)"
fi
echo ""

echo "## Python (if running outside Docker)"
if command -v python3 &> /dev/null; then
  echo "- **Python version**: $(python3 --version)"
else
  echo "- **Python version**: Not installed"
fi

if command -v uv &> /dev/null; then
  echo "- **uv version**: $(uv --version)"
fi
echo ""

echo "## Docker Services Status"
if command -v docker &> /dev/null; then
  if docker ps -q &> /dev/null; then
    echo "Running services:"
    docker ps --format "table {{.Names}}\t{{.Status}}" | tail -n +2 | sed 's/^/  - /'
  else
    echo "No running Docker services (or Docker daemon not accessible)"
  fi
fi
