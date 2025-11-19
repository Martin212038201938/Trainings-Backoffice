#!/bin/bash
# Database migration script with error handling

set -e  # Exit on error

echo "========================================="
echo "  Database Migration Script"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_DIR"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please create .env file from .env.example"
    exit 1
fi

# Source environment variables
set -a
source .env
set +a

echo -e "${YELLOW}⚠️  IMPORTANT: Make sure you have a database backup before proceeding!${NC}"
echo ""
read -p "Do you have a recent database backup? (yes/no): " -r
echo
if [[ ! $REPLY =~ ^[Yy](es)?$ ]]; then
    echo -e "${RED}Please create a backup first before running migrations.${NC}"
    exit 1
fi

echo "Checking current migration status..."
alembic current

echo ""
echo "Pending migrations:"
alembic history --verbose

echo ""
read -p "Proceed with migration? (yes/no): " -r
echo
if [[ ! $REPLY =~ ^[Yy](es)?$ ]]; then
    echo "Migration cancelled."
    exit 0
fi

echo ""
echo "Running migrations..."
if alembic upgrade head; then
    echo -e "${GREEN}✅ Migrations completed successfully!${NC}"
    echo ""
    echo "Current migration status:"
    alembic current
    exit 0
else
    echo -e "${RED}❌ Migration failed!${NC}"
    echo "Please check the error message above and fix any issues."
    exit 1
fi
