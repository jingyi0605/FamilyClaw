#!/usr/bin/env bash
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

: "${IMAGE_NAME:=jingyi0605/familyclaw}"
: "${BUILDER_NAME:=familyclaw-builder}"
: "${BUILD_CHANNEL:=stable}"
: "${RELEASE_URL_BASE:=}"
: "${EXTRA_TAGS:=}"

show_menu() {
  printf '\n'
  printf '========================================\n'
  printf '    FamilyClaw Docker Build Menu\n'
  printf '========================================\n'
  printf '\n'
  printf '1) 本地构建 x86 (linux/amd64)\n'
  printf '2) 本地构建 ARM64 (linux/arm64)\n'
  printf '3) 多平台构建并推送 (amd64 + arm64)\n'
  printf '4) 自定义构建\n'
  printf '5) 退出\n'
  printf '\n'
  printf '请选择 [1-5]: '
}

show_custom_menu() {
  printf '\n'
  printf '--- 自定义构建选项 ---\n'
  printf '\n'
  printf '请输入目标平台 (例如: linux/amd64 或 linux/amd64,linux/arm64): '
  read -r custom_platforms

  printf '是否推送到仓库? [y/N]: '
  read -r push_choice

  if [[ "${push_choice}" =~ ^[Yy]$ ]]; then
    custom_push=1
  else
    custom_push=0
  fi
}

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

do_build() {
  local platforms="${1}"
  local push="${2}"

  cd "${PROJECT_ROOT}"
  ensure_builder

  if [[ "${push}" != "1" && "${platforms}" == *","* ]]; then
    printf 'PUSH=0 only supports a single platform because docker buildx --load cannot load a multi-arch image\n' >&2
    exit 1
  fi

  mapfile -d '' tag_args < <(build_tags)

  build_args=(
    --platform "${platforms}"
    "${tag_args[@]}"
    --build-arg "APP_VERSION=${APP_VERSION}"
    --build-arg "BUILD_CHANNEL=${BUILD_CHANNEL}"
    --build-arg "BUILD_TIME=${BUILD_TIME}"
    --build-arg "GIT_SHA=${GIT_SHA}"
    --build-arg "GIT_TAG=${GIT_TAG}"
    --build-arg "RELEASE_URL=${RELEASE_URL}"
    --build-arg "DOCKER_IMAGE=${IMAGE_NAME}:${APP_VERSION}"
  )

  if [[ "${push}" == "1" ]]; then
    build_args+=(--push)
  else
    build_args+=(--load)
  fi

  printf '\n'
  printf 'Building %s\n' "${IMAGE_NAME}:${APP_VERSION}"
  printf 'Platforms: %s\n' "${platforms}"
  printf 'Channel: %s\n' "${BUILD_CHANNEL}"
  printf 'Push: %s\n' "${push}"
  printf '\n'

  docker buildx build "${build_args[@]}" .
}

main() {
  local choice platforms push

  # 如果通过环境变量传入参数，跳过菜单
  if [[ -n "${PLATFORMS:-}" ]]; then
    do_build "${PLATFORMS}" "${PUSH:-0}"
    return
  fi

  show_menu
  read -r choice

  case "${choice}" in
    1)
      do_build "linux/amd64" 0
      ;;
    2)
      do_build "linux/arm64" 0
      ;;
    3)
      do_build "linux/amd64,linux/arm64" 1
      ;;
    4)
      local custom_platforms custom_push
      show_custom_menu
      do_build "${custom_platforms}" "${custom_push}"
      ;;
    5)
      printf '已退出\n'
      exit 0
      ;;
    *)
      printf '无效选择，请重新运行脚本\n' >&2
      exit 1
      ;;
  esac
}

main "$@"
