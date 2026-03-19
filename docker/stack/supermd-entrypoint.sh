#!/bin/sh
# Wrapper entrypoint for the SuperMD container in the full stack.
# Reads the LLM API key from Docker secrets and exports it as the appropriate
# environment variable based on LLM_PROVIDER, then delegates to the original
# entrypoint.sh that ships with the SuperMD image.
set -e

LLM_PROVIDER="${LLM_PROVIDER:-openai}"

if [ -f /run/secrets/llm_api_key ]; then
    API_KEY=$(cat /run/secrets/llm_api_key | tr -d '\n')

    case "$LLM_PROVIDER" in
        openai)
            export OPENAI_API_KEY="$API_KEY"
            ;;
        gemini)
            export GEMINI_API_KEY="$API_KEY"
            ;;
        anthropic)
            export ANTHROPIC_API_KEY="$API_KEY"
            ;;
        *)
            echo "[supermd] WARNING: Unknown LLM_PROVIDER '${LLM_PROVIDER}'"
            echo "[supermd] Set LLM_PROVIDER to openai, gemini, or anthropic"
            export OPENAI_API_KEY="$API_KEY"
            ;;
    esac

    echo "[supermd] LLM API key loaded for provider: ${LLM_PROVIDER}"
else
    echo "[supermd] WARNING: No /run/secrets/llm_api_key found"
    echo "[supermd] LLM calls will fail unless a key is set via environment"
fi

# Delegate to the original SuperMD entrypoint (baked into the image).
exec /entrypoint.sh "$@"
