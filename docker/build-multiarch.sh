#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

: "${IMAGE_NAME:=jingyi0605/familyclaw}"
: "${PLATFORMS:=linux/amd64,linux/arm64}"
: "${BUILDER_NAME:=familyclaw-builder}"
: "${PUSH:=1}"
: "${BUILD_CHANNEL:=stable}"
: "${RELEASE_URL_BASE:=}"
: "${EXTRA_TAGS:=}"

if [[ -z "${APP_VERSION:-}" ]]; then
  APP_VERSION="$(tr -d '[:space:]' < "${PROJECT_ROOT}/VERSION")"
fi

if [[ -z "${APP_VERSION}" ]]; then
  printf 'APP_VERSION is empty. Check %s/VERSION\n' "${PROJECT_ROOT}" >&2
  exit 1
fi

if [[ -z "${GIT_SHA:-}" ]]; then
  GIT_SHA="$(git -C "${PROJECT_ROOT}" rev-parse --short HEAD)"
fi

if [[ -z "${GIT_TAG:-}" ]]; then
  GIT_TAG="v${APP_VERSION}"
fi

if [[ -z "${BUILD_TIME:-}" ]]; then
  BUILD_TIME="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
fi

if [[ -z "${RELEASE_URL:-}" ]]; then
  if [[ -n "${RELEASE_URL_BASE}" ]]; then
    RELEASE_URL="${RELEASE_URL_BASE%/}/${GIT_TAG}"
  else
    RELEASE_URL=""
  fi
fi

if ! command -v docker >/dev/null 2>&1; then
  printf 'docker command not found\n' >&2
  exit 1
fi

if ! docker buildx version >/dev/null 2>&1; then
  printf 'docker buildx is required\n' >&2
  exit 1
fi

ensure_builder() {
  if docker buildx inspect "${BUILDER_NAME}" >/dev/null 2>&1; then
    docker buildx use "${BUILDER_NAME}"
  else
    docker buildx create --name "${BUILDER_NAME}" --use --driver docker-container
  fi

  docker buildx inspect --bootstrap >/dev/null
}

build_tags() {
  local tags=()

  tags+=(-t "${IMAGE_NAME}:${APP_VERSION}")

  if [[ "${BUILD_CHANNEL}" == "stable" ]]; then
    tags+=(-t "${IMAGE_NAME}:latest")
  elif [[ "${BUILD_CHANNEL}" == "preview" ]]; then
    tags+=(-t "${IMAGE_NAME}:preview")
  fi

  IFS=',' read -r -a extra_tags <<< "${EXTRA_TAGS}"
  for tag in "${extra_tags[@]}"; do
    tag="${tag//[[:space:]]/}"
    if [[ -n "${tag}" ]]; then
      tags+=(-t "${IMAGE_NAME}:${tag}")
    fi
  done

  printf '%s\0' "${tags[@]}"
}

main() {
  cd "${PROJECT_ROOT}"
  ensure_builder

  if [[ "${PUSH}" != "1" && "${PLATFORMS}" == *","* ]]; then
    printf 'PUSH=0 only supports a single platform because docker buildx --load cannot load a multi-arch image\n' >&2
    exit 1
  fi

  mapfile -d '' tag_args < <(build_tags)

  build_args=(
    --platform "${PLATFORMS}"
    "${tag_args[@]}"
    --build-arg "APP_VERSION=${APP_VERSION}"
    --build-arg "BUILD_CHANNEL=${BUILD_CHANNEL}"
    --build-arg "BUILD_TIME=${BUILD_TIME}"
    --build-arg "GIT_SHA=${GIT_SHA}"
    --build-arg "GIT_TAG=${GIT_TAG}"
    --build-arg "RELEASE_URL=${RELEASE_URL}"
    --build-arg "DOCKER_IMAGE=${IMAGE_NAME}:${APP_VERSION}"
  )

  if [[ "${PUSH}" == "1" ]]; then
    build_args+=(--push)
  else
    build_args+=(--load)
  fi

  printf 'Building %s\n' "${IMAGE_NAME}:${APP_VERSION}"
  printf 'Platforms: %s\n' "${PLATFORMS}"
  printf 'Channel: %s\n' "${BUILD_CHANNEL}"
  printf 'Push: %s\n' "${PUSH}"

  docker buildx build "${build_args[@]}" .
}

main "$@"
