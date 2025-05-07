# Custom NextChat Files

This directory contains custom modifications to the [NextChat](https://github.com/ChatGPTNextWeb/NextChat) project that have been made specifically for the slow-takeoff project.

## Purpose

Instead of storing the entire NextChat repository in our git, we only store the specific files we've modified. The `setup-nextchat.sh` script in the root directory will:

1. Clone the original NextChat repository
2. Check out the specific commit (3fdbf01098dd86aec5f5644532de222e87ba7e50) that our modifications are based on
3. Apply our custom modifications from this directory
4. Set up the necessary environment configuration

## Modified Files

- `app/api/generate-tailwind-css/route.ts` - API route for dynamically generating Tailwind CSS for TSX strings
- `app/components/chat.tsx` - Modified to support rendering HTML artifacts from MCP tools
- `app/store/chat.ts` - Modified to intercept MCP responses and create HTML artifacts
- `app/mcp/mcp_config.json` - Configuration for MCP servers

## How to Use

When you clone the slow-takeoff repository, run the setup script to set up NextChat:

```bash
./setup-nextchat.sh
```

This will clone the NextChat repository and apply our custom modifications.

## Making Changes

If you need to make additional changes to NextChat:

1. Make your changes in the `nextchat/` directory
2. Copy the modified files to the corresponding location in `custom-nextchat-files/`
3. Commit the changes to the `custom-nextchat-files/` directory

For example:

```bash
# After modifying nextchat/app/components/some-file.tsx
mkdir -p custom-nextchat-files/app/components/
cp nextchat/app/components/some-file.tsx custom-nextchat-files/app/components/
git add custom-nextchat-files/app/components/some-file.tsx
git commit -m "Update some-file.tsx with new feature"
```

This way, we only track the specific files we've modified, while the setup script handles downloading the rest of the NextChat repository.
