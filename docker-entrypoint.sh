#!/bin/sh
set -e
if [ "$1" = "api" ]; then
    shift
    exec uvicorn community_ai_audit.api.server:app "$@"
fi
exec community-ai-audit "$@"
