#!/bin/bash
# Matrix/Conduit User Setup Script
# Run this after Conduit is deployed to create users

set -e

CONDUIT_URL="${CONDUIT_URL:-http://conduit:6167}"
SERVER_NAME="agentic.local"

echo "=== Matrix (Conduit) User Setup ==="
echo ""
echo "Server: ${CONDUIT_URL}"
echo "Domain: ${SERVER_NAME}"
echo ""

# Function to create a user
create_user() {
    local username=$1
    local password=$2
    local admin=${3:-false}

    echo "Creating user: @${username}:${SERVER_NAME}"

    # Conduit uses the Matrix admin API for user creation
    # First, we need to get a registration token or use the admin endpoint

    response=$(curl -s -X POST "${CONDUIT_URL}/_matrix/client/v3/register" \
        -H "Content-Type: application/json" \
        -d "{
            \"username\": \"${username}\",
            \"password\": \"${password}\",
            \"auth\": {
                \"type\": \"m.login.dummy\"
            },
            \"admin\": ${admin}
        }" 2>&1)

    if echo "$response" | grep -q "user_id"; then
        echo "  ✓ Created @${username}:${SERVER_NAME}"
        return 0
    else
        echo "  ✗ Failed: $response"
        return 1
    fi
}

# Parse arguments
case "$1" in
    "create-bot")
        # Create the agentic bot user
        BOT_PASSWORD="${2:-$(openssl rand -base64 24)}"
        echo "Bot password: ${BOT_PASSWORD}"
        echo ""
        echo "Save this password to Infisical:"
        echo "  /root/.config/infisical/secrets.sh set /agentic-platform/matrix MATRIX_PASSWORD '${BOT_PASSWORD}'"
        echo ""
        create_user "agentic-bot" "${BOT_PASSWORD}" "false"
        ;;

    "create-admin")
        # Create an admin user (you)
        ADMIN_USER="${2:-charlie}"
        ADMIN_PASSWORD="${3:-$(openssl rand -base64 24)}"
        echo "Creating admin user: ${ADMIN_USER}"
        echo "Password: ${ADMIN_PASSWORD}"
        echo ""
        echo "Save this somewhere secure!"
        echo ""
        create_user "${ADMIN_USER}" "${ADMIN_PASSWORD}" "true"
        ;;

    "create-rooms")
        # Create the standard rooms
        echo "Creating rooms requires a logged-in user."
        echo "Use Element to create these rooms after logging in:"
        echo ""
        echo "Rooms to create (as a Space):"
        echo "  - AGENTIC PLATFORM (Space)"
        echo "    ├── #critical"
        echo "    ├── #infrastructure"
        echo "    ├── #improvements"
        echo "    ├── #approvals"
        echo "    ├── #gemini-chat"
        echo "    └── #activity-log"
        echo ""
        echo "Then invite @agentic-bot:${SERVER_NAME} to all rooms."
        ;;

    *)
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  create-bot              Create the agentic-bot user"
        echo "  create-admin [user]     Create your admin user (default: charlie)"
        echo "  create-rooms            Show room creation instructions"
        echo ""
        echo "Examples:"
        echo "  $0 create-admin charlie"
        echo "  $0 create-bot"
        echo ""
        echo "After creating users, connect with Element X:"
        echo "  1. Open Element X on Android"
        echo "  2. Tap 'Sign in'"
        echo "  3. Enter homeserver: https://matrix.yourdomain.com (or internal IP)"
        echo "  4. Enter username and password"
        ;;
esac
