#!/bin/bash
# Deployment script for AlwaysData

set -e  # Exit on error

echo "========================================="
echo "  Trainings Backoffice Deployment"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_DIR"

# Check if we're in the right directory
if [ ! -f "backend/wsgi.py" ]; then
    echo -e "${RED}Error: Not in project root directory!${NC}"
    exit 1
fi

echo -e "${BLUE}Step 1/6: Pulling latest changes from Git...${NC}"
git fetch origin
CURRENT_BRANCH=$(git branch --show-current)
echo "Current branch: $CURRENT_BRANCH"

if [ -n "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}⚠️  Warning: You have uncommitted changes!${NC}"
    git status --short
    read -p "Do you want to stash these changes and continue? (yes/no): " -r
    echo
    if [[ $REPLY =~ ^[Yy](es)?$ ]]; then
        git stash
        echo "Changes stashed. You can restore them later with 'git stash pop'"
    else
        echo "Deployment cancelled."
        exit 1
    fi
fi

git pull origin "$CURRENT_BRANCH"
echo -e "${GREEN}✅ Git pull completed${NC}"
echo ""

echo -e "${BLUE}Step 2/6: Installing dependencies...${NC}"
cd backend

# Check if poetry is available
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}Error: Poetry not found!${NC}"
    echo "Please install poetry first: https://python-poetry.org/docs/#installation"
    exit 1
fi

poetry install --no-dev --no-interaction
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

echo -e "${BLUE}Step 3/6: Running database migrations...${NC}"
read -p "Do you want to run database migrations? (yes/no): " -r
echo
if [[ $REPLY =~ ^[Yy](es)?$ ]]; then
    poetry run alembic upgrade head
    echo -e "${GREEN}✅ Migrations completed${NC}"
else
    echo -e "${YELLOW}⚠️  Skipping migrations${NC}"
fi
echo ""

echo -e "${BLUE}Step 4/6: Collecting static files (if any)...${NC}"
# Add static file collection here if needed
echo -e "${GREEN}✅ Static files ready${NC}"
echo ""

echo -e "${BLUE}Step 5/6: Restarting application...${NC}"
# For AlwaysData, you might need to restart via their control panel or supervisor
# This is a placeholder - adjust based on your actual restart method

# If using supervisor on AlwaysData:
if command -v supervisorctl &> /dev/null; then
    supervisorctl restart trainings-backoffice
    echo -e "${GREEN}✅ Application restarted via supervisor${NC}"
else
    echo -e "${YELLOW}⚠️  Please restart the application manually via AlwaysData control panel${NC}"
    echo "   Site ID: #993983"
    echo "   Or run: supervisorctl restart trainings-backoffice"
fi
echo ""

echo -e "${BLUE}Step 6/6: Running health check...${NC}"
sleep 5  # Wait for application to start

# Try to hit the health endpoint
HEALTH_URL="https://yellow-boat.org/health"
if command -v curl &> /dev/null; then
    if curl -f -s "$HEALTH_URL" > /dev/null; then
        echo -e "${GREEN}✅ Health check passed!${NC}"
        echo ""
        echo -e "${GREEN}=========================================${NC}"
        echo -e "${GREEN}  Deployment completed successfully!${NC}"
        echo -e "${GREEN}=========================================${NC}"
    else
        echo -e "${RED}❌ Health check failed!${NC}"
        echo "Please check application logs and verify the deployment."
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  curl not available, skipping health check${NC}"
    echo "Please manually verify: $HEALTH_URL"
fi

echo ""
echo "Deployment completed at: $(date)"
echo ""
