#!/bin/bash

# Frontend Build Script for Render
echo "🚀 Starting frontend build process..."

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Build the application
echo "🔨 Building application..."
npm run build

# Verify build output
echo "✅ Build completed!"
echo "📁 Build output directory: dist/"
ls -la dist/

echo "🎉 Frontend build process completed successfully!"
