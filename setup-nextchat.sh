#!/bin/bash

# Script to set up NextChat with custom modifications
# This script will:
# 1. Clone the original NextChat repository
# 2. Apply our custom modifications
# 3. Install dependencies

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NEXTCHAT_DIR="$SCRIPT_DIR/nextchat"
CUSTOM_FILES_DIR="$SCRIPT_DIR/custom-nextchat-files"

# Check if nextchat directory already exists
if [ -d "$NEXTCHAT_DIR" ]; then
  echo "NextChat directory already exists. Do you want to remove it and reinstall? (y/n)"
  read -r answer
  if [ "$answer" != "y" ]; then
    echo "Aborting setup."
    exit 0
  fi
  rm -rf "$NEXTCHAT_DIR"
fi

echo "Cloning NextChat repository..."
git clone https://github.com/ChatGPTNextWeb/NextChat.git "$NEXTCHAT_DIR"

echo "Checking out specific commit that our modifications are based on..."
cd "$NEXTCHAT_DIR"
git checkout 3fdbf01098dd86aec5f5644532de222e87ba7e50
cd "$SCRIPT_DIR"

echo "Applying custom modifications..."
# Create directories if they don't exist
mkdir -p "$NEXTCHAT_DIR/app/api/generate-tailwind-css"
mkdir -p "$NEXTCHAT_DIR/app/components"
mkdir -p "$NEXTCHAT_DIR/app/store"
mkdir -p "$NEXTCHAT_DIR/app/mcp"

# Copy custom files
cp "$CUSTOM_FILES_DIR/app/api/generate-tailwind-css/route.ts" "$NEXTCHAT_DIR/app/api/generate-tailwind-css/"
cp "$CUSTOM_FILES_DIR/app/components/chat.tsx" "$NEXTCHAT_DIR/app/components/"
cp "$CUSTOM_FILES_DIR/app/store/chat.ts" "$NEXTCHAT_DIR/app/store/"
cp "$CUSTOM_FILES_DIR/app/mcp/mcp_config.json" "$NEXTCHAT_DIR/app/mcp/"

echo "Setting up .env.local file..."
cat > "$NEXTCHAT_DIR/.env.local" << EOL
ENABLE_MCP=true
# Add your OpenAI API key below
# OPENAI_API_KEY=your-api-key-here
EOL

echo "NextChat setup complete!"
echo "To install dependencies and start NextChat:"
echo "  cd nextchat"
echo "  yarn install"
echo "  yarn dev"
echo ""
echo "Don't forget to add your OpenAI API key to nextchat/.env.local"
