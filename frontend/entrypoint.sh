#!/bin/sh
set -e

cd /app

echo "Installing npm dependencies..."
npm install --prefer-offline

echo "Starting Quasar dev server..."
exec quasar dev --hostname 0.0.0.0
