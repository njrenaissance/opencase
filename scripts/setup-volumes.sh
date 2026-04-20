#!/bin/bash
# Setup Docker volumes required for Gideon
# Creates external volumes if they don't exist, with graceful error handling

set -e

echo "Setting up Docker volumes..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
  echo "❌ Docker is not installed or not in PATH"
  exit 1
fi

# Create external volumes
create_volume() {
  local volume_name=$1
  if docker volume inspect "$volume_name" > /dev/null 2>&1; then
    echo "✓ Volume '$volume_name' already exists"
  else
    echo "Creating volume '$volume_name'..."
    if docker volume create "$volume_name" > /dev/null; then
      echo "✓ Volume '$volume_name' created successfully"
    else
      echo "❌ Failed to create volume '$volume_name'"
      return 1
    fi
  fi
}

create_volume "gideon-postgres-data" || exit 1
create_volume "gideon-qdrant-data" || exit 1
create_volume "gideon-ollama-models" || exit 1

echo ""
echo "✓ All volumes are ready. You can now run:"
echo "  docker compose -f infrastructure/docker-compose.yml --env-file .env up"
