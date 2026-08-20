#!/usr/bin/env bash
# Build a local llama.cpp CUDA image from PR #27342 (DFlash 2).
# The stock ghcr.io/ggml-org/llama.cpp:full-cuda image only understands DFlash 1
# GGUFs (81 tensors). DFlash 2 GGUFs have 58 tensors and need this PR.
#
# Usage: ./ops/build-dflash2-image.sh
set -euo pipefail
SRC=${LLAMA_SRC:-$HOME/src/llama.cpp-dflash2}
TAG=${LLAMA_DFLASH2_IMAGE:-local/llama.cpp:dflash2-cuda}
ARCH=${CUDA_DOCKER_ARCH:-120}

mkdir -p "$(dirname "$SRC")"
if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$SRC"
fi
cd "$SRC"
git fetch --depth 1 origin pull/27342/head:pr-27342
git checkout pr-27342
git log -1 --oneline

echo "building $TAG  CUDA_DOCKER_ARCH=$ARCH"
docker build \
  --build-arg CUDA_DOCKER_ARCH="$ARCH" \
  --target full \
  -t "$TAG" \
  -f .devops/cuda.Dockerfile \
  .
echo "built $TAG"
docker images "$TAG"
