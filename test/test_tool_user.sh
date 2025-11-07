#!/bin/zsh
# filepath: /home/vardhin/Documents/git/Rhea/backend/test_tool_user.sh

# Tool User Server Test Script
# Usage: ./test_tool_user.sh

# Configuration
TOOL_USER_URL="http://localhost:5002"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "${YELLOW}=== Tool User Server Test Suite ===${NC}\n"

# Test 1: Health Check
echo "${YELLOW}Test 1: Health Check${NC}"
response=$(curl -s -X GET "${TOOL_USER_URL}/health")
if [ -n "$response" ]; then
    echo "Response: ${response}" | jq '.' 2>/dev/null || echo "${response}"
    if echo "${response}" | jq -e '.status' > /dev/null 2>&1; then
        echo "${GREEN}✓ Health check passed${NC}\n"
    else
        echo "${RED}✗ Health check failed${NC}\n"
    fi
else
    echo "${RED}✗ No response received${NC}\n"
fi

# Test 2: Configuration Check
echo "${YELLOW}Test 2: Configuration Check${NC}"
response=$(curl -s -X GET "${TOOL_USER_URL}/config")
if [ -n "$response" ]; then
    echo "Response: ${response}" | jq '.' 2>/dev/null || echo "${response}"
    if echo "${response}" | jq -e '.gemini.configured' > /dev/null 2>&1; then
        echo "${GREEN}✓ Configuration check passed${NC}\n"
    else
        echo "${RED}✗ Configuration check failed${NC}\n"
    fi
else
    echo "${RED}✗ No response received${NC}\n"
fi

# Test 3: Simple Query (No Tools Needed)
echo "${YELLOW}Test 3: Simple Query - Direct Response${NC}"
response=$(curl -s -X POST "${TOOL_USER_URL}/query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "Hello, how are you?",
        "max_tools": 3
    }')
echo "Response: ${response}" | jq '.'
if echo "${response}" | jq -e '.action' > /dev/null 2>&1; then
    echo "${GREEN}✓ Simple query passed${NC}\n"
else
    echo "${RED}✗ Simple query failed${NC}\n"
fi

# Test 4: Query Requiring Tool Use (Math)
echo "${YELLOW}Test 4: Query Requiring Tool Use - Calculator${NC}"
response=$(curl -s -X POST "${TOOL_USER_URL}/query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "What is 25 multiplied by 4?",
        "max_tools": 3
    }')
echo "Response: ${response}" | jq '.'
if echo "${response}" | jq -e '.action' > /dev/null 2>&1; then
    action=$(echo "${response}" | jq -r '.action')
    echo "Action taken: ${action}"
    if [[ "${action}" == "use_tool" ]]; then
        echo "${GREEN}✓ Tool use query passed${NC}\n"
    else
        echo "${YELLOW}⚠ Expected tool use, got ${action}${NC}\n"
    fi
else
    echo "${RED}✗ Tool use query failed${NC}\n"
fi

# Test 5: Query Requiring Tool Search
echo "${YELLOW}Test 5: Query Requiring Tool Search${NC}"
response=$(curl -s -X POST "${TOOL_USER_URL}/query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "I need to convert JSON to YAML format",
        "max_tools": 3
    }')
echo "Response: ${response}" | jq '.'
if echo "${response}" | jq -e '.action' > /dev/null 2>&1; then
    action=$(echo "${response}" | jq -r '.action')
    echo "Action taken: ${action}"
    echo "${GREEN}✓ Tool search query passed${NC}\n"
else
    echo "${RED}✗ Tool search query failed${NC}\n"
fi

# Test 6: Query Requiring Tool Creation
echo "${YELLOW}Test 6: Query Requiring Tool Creation${NC}"
response=$(curl -s -X POST "${TOOL_USER_URL}/query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "Create a tool to calculate the factorial of a number",
        "max_tools": 3
    }')
echo "Response: ${response}" | jq '.'
if echo "${response}" | jq -e '.action' > /dev/null 2>&1; then
    action=$(echo "${response}" | jq -r '.action')
    echo "Action taken: ${action}"
    if [[ "${action}" == "create_tool" ]]; then
        echo "${GREEN}✓ Tool creation query passed${NC}\n"
    else
        echo "${YELLOW}⚠ Expected tool creation, got ${action}${NC}\n"
    fi
else
    echo "${RED}✗ Tool creation query failed${NC}\n"
fi

# Test 7: Direct Tool Search Endpoint
echo "${YELLOW}Test 7: Direct Tool Search Endpoint${NC}"
response=$(curl -s -X POST "${TOOL_USER_URL}/tools/search" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "calculator math",
        "max_results": 3
    }')
echo "Response: ${response}" | jq '.'
if echo "${response}" | jq -e '.results' > /dev/null 2>&1; then
    count=$(echo "${response}" | jq '.results | length')
    echo "Found ${count} tools"
    echo "${GREEN}✓ Tool search endpoint passed${NC}\n"
else
    echo "${RED}✗ Tool search endpoint failed${NC}\n"
fi

# Test 8: Direct Tool Execution Endpoint
echo "${YELLOW}Test 8: Direct Tool Execution Endpoint${NC}"
response=$(curl -s -X POST "${TOOL_USER_URL}/tools/execute" \
    -H "Content-Type: application/json" \
    -d '{
        "tool_name": "add",
        "parameters": {
            "a": 15,
            "b": 27
        }
    }')
echo "Response: ${response}" | jq '.'
if echo "${response}" | jq -e '.success' > /dev/null 2>&1; then
    echo "${GREEN}✓ Tool execution endpoint passed${NC}\n"
else
    echo "${YELLOW}⚠ Tool execution may have failed (tool might not exist)${NC}\n"
fi

# Test 9: Complex Math Query
echo "${YELLOW}Test 9: Complex Math Expression${NC}"
response=$(curl -s -X POST "${TOOL_USER_URL}/query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "Calculate (15 + 25) * 3 - 10",
        "max_tools": 3
    }')
echo "Response: ${response}" | jq '.'
if echo "${response}" | jq -e '.action' > /dev/null 2>&1; then
    action=$(echo "${response}" | jq -r '.action')
    echo "Action taken: ${action}"
    echo "${GREEN}✓ Complex math query passed${NC}\n"
else
    echo "${RED}✗ Complex math query failed${NC}\n"
fi

# Test 10: Query with Conversation History
echo "${YELLOW}Test 10: Query with Conversation History${NC}"
response=$(curl -s -X POST "${TOOL_USER_URL}/query" \
    -H "Content-Type: application/json" \
    -d '{
        "query": "Now multiply that result by 2",
        "max_tools": 3,
        "history": [
            {"role": "user", "content": "What is 5 + 5?"},
            {"role": "assistant", "content": "5 + 5 equals 10."}
        ]
    }')
echo "Response: ${response}" | jq '.'
if echo "${response}" | jq -e '.action' > /dev/null 2>&1; then
    echo "${GREEN}✓ Query with history passed${NC}\n"
else
    echo "${RED}✗ Query with history failed${NC}\n"
fi

# Test 11: Invalid Request - Missing Query
echo "${YELLOW}Test 11: Invalid Request - Missing Query${NC}"
response=$(curl -s -X POST "${TOOL_USER_URL}/query" \
    -H "Content-Type: application/json" \
    -d '{}')
echo "Response: ${response}" | jq '.'
if echo "${response}" | jq -e '.error' > /dev/null 2>&1; then
    echo "${GREEN}✓ Error handling passed${NC}\n"
else
    echo "${RED}✗ Error handling failed${NC}\n"
fi

# Test 12: 404 Endpoint
echo "${YELLOW}Test 12: 404 Not Found${NC}"
response=$(curl -s -X GET "${TOOL_USER_URL}/nonexistent")
echo "Response: ${response}" | jq '.'
if echo "${response}" | jq -e '.error' > /dev/null 2>&1; then
    echo "${GREEN}✓ 404 handling passed${NC}\n"
else
    echo "${RED}✗ 404 handling failed${NC}\n"
fi

echo "${YELLOW}=== Test Suite Complete ===${NC}"