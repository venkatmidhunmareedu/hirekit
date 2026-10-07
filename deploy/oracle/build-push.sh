#!/usr/bin/env bash
# Build the backend and web images on this machine and push them to GHCR.
# Usage: REGISTRY_NAMESPACE=<github user or org, lower case> [IMAGE_TAG=<tag>] ./build-push.sh
# Log in first: echo "$GHCR_TOKEN" | docker login ghcr.io -u <github user> --password-stdin
# (a token with write:packages). The images are linux/amd64 for the free AMD Micro VM; for the Ampere
# shape change platforms to linux/arm64 in docker-compose.build.yml.
set -euo pipefail
cd "$(dirname "$0")"
: "${REGISTRY_NAMESPACE:?set REGISTRY_NAMESPACE}"
export IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
# Compose requires run-time settings even to build; these dummies never reach an image.
export DATABASE_URL=unused OPENROUTER_API_KEY=unused SITE_ADDRESS=unused
docker compose -f docker-compose.yml -f docker-compose.build.yml build api web
docker compose -f docker-compose.yml -f docker-compose.build.yml push api web
echo "pushed tag $IMAGE_TAG; on the VM set IMAGE_TAG=$IMAGE_TAG in .env, then: docker compose pull && docker compose up -d"
