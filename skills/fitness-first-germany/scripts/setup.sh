#!/usr/bin/env bash
set -e

# Setup helper for Fitness First Germany in Hermes Agent
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../" && pwd)"
HERMES_DIR="${HOME}/.hermes"
SKILLS_DIR="${HERMES_DIR}/skills"
CONFIG_FILE="${HERMES_DIR}/config.yaml"

echo "=================================================="
echo " Fitness First Germany - Hermes Agent Setup Helper"
echo "=================================================="
echo "Repository path: ${REPO_DIR}"
echo ""

# 1. Symlink skill
mkdir -p "${SKILLS_DIR}"
TARGET_SKILL="${SKILLS_DIR}/fitness-first-germany"
if [ -L "${TARGET_SKILL}" ] || [ -d "${TARGET_SKILL}" ]; then
  echo "✓ Skill is already linked at ${TARGET_SKILL}"
else
  ln -s "${REPO_DIR}/skills/fitness-first-germany" "${TARGET_SKILL}"
  echo "✓ Linked skill to ${TARGET_SKILL}"
fi

echo ""
echo "--- Credential Configuration Options ---"
echo "1) Set credentials in Hermes (.env via hermes CLI)"
echo "2) Add MCP server entry to ~/.hermes/config.yaml"
echo "3) Use local .env file in the repository"
echo ""

read -rp "Would you like to configure credentials now via Hermes CLI? (y/N): " configure_now
if [[ "${configure_now}" =~ ^[Yy]$ ]]; then
  read -rp "Enter Fitness First Email: " ff_email
  read -rsp "Enter Fitness First Password: " ff_password
  echo ""

  if command -v hermes >/dev/null 2>&1; then
    hermes config set FITNESS_FIRST_EMAIL "${ff_email}"
    hermes config set FITNESS_FIRST_PASSWORD "${ff_password}"
    echo "✓ Credentials stored via 'hermes config set' (saved to ~/.hermes/.env)"
  else
    HERMES_ENV="${HERMES_DIR}/.env"
    mkdir -p "${HERMES_DIR}"
    echo "FITNESS_FIRST_EMAIL=${ff_email}" >> "${HERMES_ENV}"
    echo "FITNESS_FIRST_PASSWORD=${ff_password}" >> "${HERMES_ENV}"
    echo "✓ Saved credentials directly to ${HERMES_ENV}"
  fi
fi

echo ""
echo "--- Next Step: MCP Server Registration ---"
echo "Ensure your ~/.hermes/config.yaml contains the mcp_servers entry:"
echo ""
cat <<EOF
mcp_servers:
  fitness-first-germany:
    command: "uv"
    args: ["run", "--directory", "${REPO_DIR}", "fitness-first-germany-mcp"]
    env:
      FITNESS_FIRST_EMAIL: \${FITNESS_FIRST_EMAIL}
      FITNESS_FIRST_PASSWORD: \${FITNESS_FIRST_PASSWORD}
EOF
echo ""
echo "Setup complete! Restart or reload Hermes, then type /fitness-first to get started."
