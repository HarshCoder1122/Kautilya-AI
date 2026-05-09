#!/bin/bash
# Kautilya AI — Frontend Deployment Script (Koyeb)
# This script builds the React frontend and prepares it for deployment.

echo "🚀 Building Kautilya Frontend..."

# 1. Install dependencies
npm install

# 2. Build for production
# Set the REACT_APP_API_URL to your HuggingFace Space URL
# Example: export REACT_APP_API_URL=https://huggingface.co/spaces/user/space-name
if [ -z "$REACT_APP_API_URL" ]; then
    echo "⚠️ REACT_APP_API_URL is not set. Using localhost fallback."
fi

npm run build

echo "✅ Build complete. Contents of 'build/' directory are ready for Koyeb."
echo "💡 Tip: Deploy the 'build/' folder to Koyeb as a Static Site."
