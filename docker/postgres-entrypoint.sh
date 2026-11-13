#!/bin/sh
set -eu

password_file=/run/spoonfuls/postgres-password
if [ ! -s "$password_file" ]; then
  umask 077
  openssl rand -base64 32 > "$password_file"
fi
export POSTGRES_PASSWORD_FILE="$password_file"

exec /usr/local/bin/docker-entrypoint.sh "$@"
