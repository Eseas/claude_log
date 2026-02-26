#!/bin/bash
# Test UserPromptSubmit hook context generation

echo "Testing hook context generation..."
echo ""

# Test 1: Bug fix prompt
echo "Test 1: Bug fix prompt"
echo '{"prompt":"fix debouncing bug"}' | ./.claude/hooks/start | jq .
echo ""

# Test 2: Feature addition
echo "Test 2: Feature addition"
echo '{"prompt":"add new feature"}' | ./.claude/hooks/start | jq .
echo ""

# Test 3: Investigation
echo "Test 3: Investigation"
echo '{"prompt":"check file watcher"}' | ./.claude/hooks/start | jq .
echo ""

echo "Check .claude/hook-events.log for detailed logs"
