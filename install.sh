#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then
  echo 'Bitte mit sudo bash install.sh starten.' >&2
  exit 1
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -f "$script_dir/installer/setup.py" ]]; then
  exec python3 "$script_dir/installer/setup.py" "$@"
fi
temp_dir=$(mktemp -d /tmp/pi-hotspot-install.XXXXXXXX)
trap 'rm -rf -- "$temp_dir"' EXIT
curl --fail --show-error --silent --location --proto '=https' --tlsv1.2 \
  https://github.com/leotrax3d/pi-hotspot/archive/refs/heads/main.tar.gz -o "$temp_dir/source.tar.gz"
tar -xzf "$temp_dir/source.tar.gz" -C "$temp_dir"
python3 "$temp_dir/pi-hotspot-main/installer/setup.py" "$@"
