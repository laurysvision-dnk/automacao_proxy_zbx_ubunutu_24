#!/usr/bin/env bash
set -Eeuo pipefail
repo='' ref='' install_args=()
fail() { printf 'Erro: %s\n' "$*" >&2; exit 1; }
while (($#)); do
  case "$1" in
    --repo|--ref)
      (($# >= 2)) || fail "Falta valor para $1"
      if [[ $1 == --repo ]]; then repo=$2; else ref=$2; fi
      shift 2;;
    *) install_args+=("$1"); shift;;
  esac
done
[[ $repo =~ ^https://[A-Za-z0-9_.:-]+/[A-Za-z0-9_./-]+$ || $repo =~ ^git@[A-Za-z0-9_.-]+:[A-Za-z0-9_./-]+$ ]] || fail 'Informe --repo HTTPS sem credencial embutida ou git@servidor:repositorio.'
[[ $ref =~ ^[A-Za-z0-9][A-Za-z0-9_./-]*$ && $ref != *..* ]] || fail 'Informe --ref com uma tag, branch ou commit explícito.'
if ! command -v git >/dev/null; then
  ((EUID == 0)) || fail 'Git ausente. Execute como root ou instale o Git.'
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq git ca-certificates
fi
work_dir=$(mktemp -d /tmp/observa-proxy-bootstrap.XXXXXX)
trap 'rm -rf -- "$work_dir"' EXIT
git clone --quiet --no-checkout -- "$repo" "$work_dir/repository"
git -C "$work_dir/repository" checkout --quiet --detach "$ref"
printf 'Versão obtida: %s\n' "$(git -C "$work_dir/repository" rev-parse HEAD)"
bash "$work_dir/repository/install.sh" "${install_args[@]}"
