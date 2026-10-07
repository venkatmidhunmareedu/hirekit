#!/usr/bin/env bash
# Build the backend and web images on this machine and/or send them to Docker Hub.
# Usage: REGISTRY_NAMESPACE=<docker hub user> [IMAGE_TAG=<tag>] ./build-push.sh [build|push|all]
# Normally run through `make images`, `make images-build` or `make images-push`.
# Log in first: docker login -u <docker hub user> (a Docker Hub access token with write access).
# The images are linux/amd64 for the free AMD Micro VM; for the Ampere
# shape change platforms to linux/arm64 in docker-compose.build.yml.
set -euo pipefail
cd "$(dirname "$0")"
: "${REGISTRY_NAMESPACE:?set REGISTRY_NAMESPACE}"
export IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
# Compose requires run-time settings even to build; these dummies never reach an image.
export DATABASE_URL=unused OPENROUTER_API_KEY=unused SITE_ADDRESS=unused
step="${1:-all}"
compose=(docker compose -f docker-compose.yml -f docker-compose.build.yml)
if [[ $step == build || $step == all ]]; then "${compose[@]}" build api web; fi
if [[ $step == push || $step == all ]]; then "${compose[@]}" push api web; fi
echo "tag $IMAGE_TAG ($step); on the VM set IMAGE_TAG=$IMAGE_TAG in .env, then: docker compose pull && docker compose up -d"
