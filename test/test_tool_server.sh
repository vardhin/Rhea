#!/bin/zsh

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="http://localhost:5001"
API_USERNAME="admin"  # Changed from USERNAME to avoid conflict with system variable
API_PASSWORD="admin123"  # Changed from PASSWORD for consistency
TOKEN=""

# Print section header
print_section() {
    echo "${BLUE}================================================${NC}"
    echo "${BLUE}$1${NC}"
    echo "${BLUE}================================================${NC}"
}

# Print test result
print_result() {
    local exit_code=$1
    local endpoint=$2
    local response=$3
    
    if [[ $exit_code -eq 0 ]]; then
        echo "${GREEN}✓ SUCCESS${NC} - $endpoint"
        echo "Response: $response" | jq '.' 2>/dev/null || echo "$response"
    else
        echo "${RED}✗ FAILED${NC} - $endpoint"
        echo "Response: $response"
    fi
    echo ""
}

# Get JWT token
get_jwt_token() {
    print_section "Getting JWT Token"
    
    local response=$(curl -s -X POST "$BASE_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$API_USERNAME\", \"password\": \"$API_PASSWORD\"}")
    
    local exit_code=$?
    
    if [[ $exit_code -eq 0 ]]; then
        TOKEN=$(echo $response | jq -r '.token' 2>/dev/null)
        
        if [[ $TOKEN != "null" && -n $TOKEN ]]; then
            echo "${GREEN}✓ Successfully obtained JWT token${NC}"
            echo "Token: ${TOKEN:0:50}..."
            echo ""
            return 0
        else
            echo "${RED}✗ Failed to get token${NC}"
            echo "Response: $response"
            echo ""
            return 1
        fi
    else
        echo "${RED}✗ Failed to connect to auth endpoint${NC}"
        return 1
    fi
}

# Test authentication endpoints
test_auth() {
    print_section "Testing Authentication"
    
    echo "${YELLOW}1. Login with valid credentials${NC}"
    local response=$(curl -s -X POST "$BASE_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$API_USERNAME\", \"password\": \"$API_PASSWORD\"}")
    local exit_code=$?
    print_result $exit_code "POST /auth/login (valid)" "$response"
    
    echo "${YELLOW}2. Login with invalid credentials${NC}"
    response=$(curl -s -X POST "$BASE_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"username": "admin", "password": "wrongpass"}')
    exit_code=$?
    print_result $exit_code "POST /auth/login (invalid)" "$response"
    
    echo "${YELLOW}3. Verify token${NC}"
    response=$(curl -s "$BASE_URL/auth/verify" \
        -H "Authorization: Bearer $TOKEN")
    exit_code=$?
    print_result $exit_code "GET /auth/verify" "$response"
}

# Check if server is running
check_server() {
    print_section "Checking if server is running"
    local response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
    
    if [[ $response -eq 200 ]]; then
        echo "${GREEN}✓ Server is running${NC}"
        echo ""
        return 0
    else
        echo "${RED}✗ Server is not running on $BASE_URL${NC}"
        echo "Please start the server first: python tool_server.py"
        exit 1
    fi
}

# Test health endpoint
test_health() {
    print_section "Testing Health Check"
    
    local response=$(curl -s "$BASE_URL/health")
    local exit_code=$?
    print_result $exit_code "GET /health" "$response"
}

# Test list all tools
test_list_tools() {
    print_section "Testing List Tools"
    
    echo "${YELLOW}1. List available tools only${NC}"
    local response=$(curl -s "$BASE_URL/tools")
    local exit_code=$?
    print_result $exit_code "GET /tools" "$response"
    
    echo "${YELLOW}2. List all tools (including unavailable)${NC}"
    response=$(curl -s "$BASE_URL/tools?include_unavailable=true")
    exit_code=$?
    print_result $exit_code "GET /tools?include_unavailable=true" "$response"
}

# Test tool availability status
test_availability() {
    print_section "Testing Tool Availability"
    
    local response=$(curl -s "$BASE_URL/tools/availability")
    local exit_code=$?
    print_result $exit_code "GET /tools/availability" "$response"
}

# Test get specific tool info
test_get_tool_info() {
    print_section "Testing Get Tool Info"
    
    # First, get a list of available tools
    local tools=$(curl -s "$BASE_URL/tools" | jq -r '.tools | keys[]' 2>/dev/null | head -1)
    
    if [[ -n $tools ]]; then
        echo "${YELLOW}Testing with tool: $tools${NC}"
        local response=$(curl -s "$BASE_URL/tools/$tools")
        local exit_code=$?
        print_result $exit_code "GET /tools/$tools" "$response"
    else
        echo "${YELLOW}No tools available to test${NC}"
        echo ""
    fi
    
    echo "${YELLOW}Testing with non-existent tool${NC}"
    local response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/tools/non_existent_tool")
    local exit_code=$?
    print_result $exit_code "GET /tools/non_existent_tool" "$response"
}

# Test execute tool
test_execute_tool() {
    print_section "Testing Tool Execution"
    
    # Test with a simple calculator tool if available
    echo "${YELLOW}1. Testing add tool (if available)${NC}"
    local response=$(curl -s -X POST "$BASE_URL/tools/add/execute" \
        -H "Content-Type: application/json" \
        -d '{"a": 5, "b": 3}')
    local exit_code=$?
    print_result $exit_code "POST /tools/add/execute" "$response"
    
    echo "${YELLOW}2. Testing with missing parameters${NC}"
    response=$(curl -s -X POST "$BASE_URL/tools/add/execute" \
        -H "Content-Type: application/json" \
        -d '{"a": 5}')
    exit_code=$?
    print_result $exit_code "POST /tools/add/execute (missing param)" "$response"
    
    echo "${YELLOW}3. Testing with non-existent tool${NC}"
    response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/tools/fake_tool/execute" \
        -H "Content-Type: application/json" \
        -d '{}')
    exit_code=$?
    print_result $exit_code "POST /tools/fake_tool/execute" "$response"
}

# Test get tools context
test_tools_context() {
    print_section "Testing Tools Context for LLM"
    
    echo "${YELLOW}1. Get all tools context${NC}"
    local response=$(curl -s "$BASE_URL/tools/context")
    local exit_code=$?
    print_result $exit_code "GET /tools/context" "$response"
    
    echo "${YELLOW}2. Get tools context by category (math)${NC}"
    response=$(curl -s "$BASE_URL/tools/context?category=math")
    exit_code=$?
    print_result $exit_code "GET /tools/context?category=math" "$response"
}

# Test reload tools (requires authentication)
test_reload_tools() {
    print_section "Testing Reload Tools (Authenticated)"
    
    echo "${YELLOW}1. Without authentication${NC}"
    local response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST "$BASE_URL/tools/reload")
    local exit_code=$?
    print_result $exit_code "POST /tools/reload (no auth)" "$response"
    
    echo "${YELLOW}2. With authentication${NC}"
    response=$(curl -s -X POST "$BASE_URL/tools/reload" \
        -H "Authorization: Bearer $TOKEN")
    exit_code=$?
    print_result $exit_code "POST /tools/reload (with auth)" "$response"
}

# Test invalid endpoints
test_invalid_endpoints() {
    print_section "Testing Error Handling"
    
    echo "${YELLOW}1. 404 - Invalid endpoint${NC}"
    local response=$(curl -s -w "\nHTTP_CODE:%{http_code}" "$BASE_URL/invalid/endpoint")
    local exit_code=$?
    print_result $exit_code "GET /invalid/endpoint" "$response"
}

# Main execution
main() {
    echo "${GREEN}========================================${NC}"
    echo "${GREEN}   Tool Server API Test Suite${NC}"
    echo "${GREEN}========================================${NC}"
    echo ""
    
    # Debug: Show what credentials we're using
    echo "${YELLOW}Using credentials:${NC}"
    echo "  Username: $API_USERNAME"
    echo "  Password: ${API_PASSWORD:0:3}***"
    echo ""
    
    check_server
    
    # Get JWT token first
    get_jwt_token || {
        echo "${RED}Failed to obtain JWT token. Some tests may fail.${NC}"
        echo ""
    }
    
    test_auth
    test_health
    test_availability
    test_list_tools
    test_get_tool_info
    test_tools_context
    test_execute_tool
    test_reload_tools
    test_invalid_endpoints
    
    echo "${GREEN}========================================${NC}"
    echo "${GREEN}   All Tests Completed${NC}"
    echo "${GREEN}========================================${NC}"
}

# Run main function
main