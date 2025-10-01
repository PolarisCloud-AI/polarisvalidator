#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Polaris Cloud Validator Launcher${NC}"
echo -e "${YELLOW}Detecting your operating system...${NC}"

# Detect the operating system
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="Linux"
    WALLET_PATH=~/.bittensor
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macOS"
    WALLET_PATH=~/.bittensor
elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    OS="Windows"
    # For Windows, we'll use PowerShell to get the home directory
    if command -v powershell.exe &> /dev/null; then
        WALLET_PATH=$(powershell.exe -Command "echo \$HOME\.bittensor" | tr -d '\r')
    else
        # Fallback to default Windows user profile location
        WALLET_PATH="C:\\Users\\$USERNAME\\.bittensor"
    fi
else
    echo -e "${RED}Unsupported operating system: $OSTYPE${NC}"
    exit 1
fi

echo -e "${GREEN}Detected OS: $OS${NC}"
echo -e "${GREEN}Wallet path: $WALLET_PATH${NC}"

# Get wallet name and hotkey from user input
read -p "Enter your wallet name (default: validator): " WALLET_NAME
WALLET_NAME=${WALLET_NAME:-validator}

read -p "Enter your hotkey name (default: default): " WALLET_HOTKEY
WALLET_HOTKEY=${WALLET_HOTKEY:-default}

echo -e "${YELLOW}Starting Polaris Cloud Validator with:${NC}"
echo -e "${YELLOW}Wallet Name: $WALLET_NAME${NC}"
echo -e "${YELLOW}Hotkey: $WALLET_HOTKEY${NC}"

# Run the appropriate docker command based on OS
if [[ "$OS" == "Linux" ]] || [[ "$OS" == "macOS" ]]; then
    echo -e "${GREEN}Running Docker container for $OS...${NC}"
    docker run --rm -it \
        -v "$WALLET_PATH:/root/.bittensor" \
        -e WALLET_NAME="$WALLET_NAME" \
        -e WALLET_HOTKEY="$WALLET_HOTKEY" \
        bigideaafrica/polaris-validator
elif [[ "$OS" == "Windows" ]]; then
    echo -e "${GREEN}Running Docker container for Windows...${NC}"
    # Convert path format for Docker
    DOCKER_WALLET_PATH=$(echo "$WALLET_PATH" | sed 's/\\/\//g' | sed 's/://')
    
    # Check if we're in PowerShell or Command Prompt and execute accordingly
    if [[ -n "$SHELL" ]] && [[ "$SHELL" == *"powershell"* ]]; then
        # PowerShell format
        docker run --rm -it \
            -v "${HOME}/.bittensor:/root/.bittensor" \
            -e WALLET_NAME="$WALLET_NAME" \
            -e WALLET_HOTKEY="$WALLET_HOTKEY" \
            bigideaafrica/polaris-validator
    else
        # Command Prompt format
        docker run --rm -it \
            -v "$WALLET_PATH:/root/.bittensor" \
            -e WALLET_NAME="$WALLET_NAME" \
            -e WALLET_HOTKEY="$WALLET_HOTKEY" \
            bigideaafrica/polaris-validator
    fi
fi