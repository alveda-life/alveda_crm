#!/bin/bash
echo "Building frontend (takes ~60s)..."
/usr/local/bin/docker compose build frontend && \
/usr/local/bin/docker compose up -d frontend && \
echo "Done! http://localhost:9000"
