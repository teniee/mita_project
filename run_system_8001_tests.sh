#!/bin/bash

# SYSTEM_8001 Error Isolation Test Runner
# Run this script to systematically test authentication components and isolate the error

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 SYSTEM_8001 Error Isolation Test Suite${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# Default configuration
SERVER_URL="http://localhost:8000"
PYTHON_CMD="python3"
OUTPUT_FILE="system_8001_test_report_$(date +%Y%m%d_%H%M%S).txt"

# Check if custom server URL is provided
if [ "$1" != "" ]; then
    SERVER_URL="$1"
fi

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    if command -v python &> /dev/null; then
        PYTHON_CMD="python"
        echo -e "${YELLOW}⚠️ Using 'python' instead of 'python3'${NC}"
    else
        echo -e "${RED}❌ Python not found. Please install Python 3.${NC}"
        exit 1
    fi
fi

# Check if required Python packages are installed
echo -e "${BLUE}🔧 Checking dependencies...${NC}"

if ! $PYTHON_CMD -c "import aiohttp" 2>/dev/null; then
    echo -e "${YELLOW}📦 Installing required packages...${NC}"
    pip install aiohttp || {
        echo -e "${RED}❌ Failed to install aiohttp. Please run: pip install aiohttp${NC}"
        exit 1
    }
fi

echo -e "${GREEN}✅ Dependencies checked${NC}"
echo ""

# Display test configuration
echo -e "${BLUE}🎯 Test Configuration:${NC}"
echo -e "  Server URL: ${YELLOW}$SERVER_URL${NC}"
echo -e "  Output File: ${YELLOW}$OUTPUT_FILE${NC}"
echo -e "  Python: ${YELLOW}$PYTHON_CMD${NC}"
echo ""

# Check if server is reachable
echo -e "${BLUE}🌐 Checking server connectivity...${NC}"
if curl -s --connect-timeout 5 "$SERVER_URL/health" >/dev/null 2>&1 || \
   curl -s --connect-timeout 5 "$SERVER_URL" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Server is reachable${NC}"
else
    echo -e "${YELLOW}⚠️ Server may not be reachable at $SERVER_URL${NC}"
    echo -e "${YELLOW}   The tests will still run and show connection errors if server is down${NC}"
fi
echo ""

# Run the test suite
echo -e "${BLUE}🚀 Starting SYSTEM_8001 isolation tests...${NC}"
echo -e "${BLUE}This will systematically test each component to isolate the error source${NC}"
echo ""

# Run Python test script
$PYTHON_CMD test_system_8001_isolation.py \
    --server-url="$SERVER_URL" \
    --output-file="$OUTPUT_FILE" \
    --verbose

# Check if report was generated
if [ -f "$OUTPUT_FILE" ]; then
    echo ""
    echo -e "${GREEN}📄 Test report saved to: $OUTPUT_FILE${NC}"
    echo ""
    
    # Show quick summary from report
    echo -e "${BLUE}📊 Quick Summary:${NC}"
    echo -e "${BLUE}=================${NC}"
    
    if grep -q "SYSTEM_8001 Count: 0" "$OUTPUT_FILE"; then
        echo -e "${GREEN}✅ No SYSTEM_8001 errors detected${NC}"
    else
        SYSTEM_8001_COUNT=$(grep "SYSTEM_8001 Count:" "$OUTPUT_FILE" | head -1 | grep -o '[0-9]\+')
        if [ "$SYSTEM_8001_COUNT" != "" ] && [ "$SYSTEM_8001_COUNT" -gt 0 ]; then
            echo -e "${RED}🚨 $SYSTEM_8001_COUNT SYSTEM_8001 error(s) detected${NC}"
        fi
    fi
    
    # Show success rate
    SUCCESS_RATE=$(grep "Success Rate:" "$OUTPUT_FILE" | head -1 | grep -o '[0-9.]\+%')
    if [ "$SUCCESS_RATE" != "" ]; then
        echo -e "📈 Success Rate: ${YELLOW}$SUCCESS_RATE${NC}"
    fi
    
    # Show failed components
    if grep -q "❌ Failed Components:" "$OUTPUT_FILE"; then
        echo -e "${RED}❌ Some components failed - check the full report${NC}"
    else
        echo -e "${GREEN}✅ All components passed${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}💡 Next Steps:${NC}"
    echo -e "   1. Review the full report: ${YELLOW}$OUTPUT_FILE${NC}"
    echo -e "   2. Focus on any components showing SYSTEM_8001 errors"
    echo -e "   3. Check server logs for additional error details"
    echo -e "   4. Run individual component tests for deeper debugging"
    echo ""
    
else
    echo -e "${RED}❌ Test report was not generated${NC}"
    echo -e "   Check the error output above for issues"
fi

# Individual test commands
echo -e "${BLUE}🔧 Manual Test Commands:${NC}"
echo -e "${BLUE}========================${NC}"
echo -e "Test password hashing only:"
echo -e "  ${YELLOW}curl -X POST $SERVER_URL/api/auth/test-password-hashing -H 'Content-Type: application/json' -d '{\"password\":\"TestPass123!\"}'${NC}"
echo ""
echo -e "Test database operations only:"
echo -e "  ${YELLOW}curl -X POST $SERVER_URL/api/auth/test-database-operations -H 'Content-Type: application/json' -d '{\"email\":\"test@example.com\"}'${NC}"
echo ""
echo -e "Test response generation only:"
echo -e "  ${YELLOW}curl -X POST $SERVER_URL/api/auth/test-response-generation -H 'Content-Type: application/json' -d '{\"test\":true}'${NC}"
echo ""
echo -e "Test full registration flow:"
echo -e "  ${YELLOW}curl -X POST $SERVER_URL/api/auth/test-registration -H 'Content-Type: application/json' -d '{\"email\":\"test@example.com\",\"password\":\"TestPass123!\",\"country\":\"US\"}'${NC}"
echo ""

echo -e "${GREEN}🏁 SYSTEM_8001 isolation tests completed!${NC}"