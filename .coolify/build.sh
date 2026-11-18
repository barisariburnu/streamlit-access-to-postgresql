#!/bin/sh
set -eu
compose_file=./.coolify/compose.yaml
build_env=${1:-/artifacts/build-time.env}
# Read only the immutable source identifier; never source/eval build secrets.
revision=${SOURCE_COMMIT:-}
if [ -z "$revision" ] && [ -r "$build_env" ]; then
    revision=$(sed -n 's/^SOURCE_COMMIT=//p' "$build_env")
    case "$revision" in
        \"*\") revision=${revision#\"}; revision=${revision%\"} ;;
        \'*\') revision=${revision#\'}; revision=${revision%\'} ;;
    esac
fi
if [ -z "$revision" ]; then
    revision=$(git rev-parse --verify HEAD 2>/dev/null) || revision=''
fi
case "$revision" in
    ''|*[!0-9a-f]*) printf '%s\n' source_revision_unavailable >&2; exit 35 ;;
esac
if [ "${#revision}" -ne 40 ]; then
    printf '%s\n' source_revision_unavailable >&2
    exit 35
fi
docker compose --project-directory . --env-file "$build_env" -f "$compose_file" build \
    --build-arg MONITORING_SOURCE_REVISION="$revision"
