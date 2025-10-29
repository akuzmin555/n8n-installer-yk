#!/bin/bash
# Init script to remove default nginx config before starting RAGFlow

# Remove default nginx site
rm -f /etc/nginx/sites-enabled/default

# Execute original entrypoint
exec /ragflow/entrypoint.sh "$@"
