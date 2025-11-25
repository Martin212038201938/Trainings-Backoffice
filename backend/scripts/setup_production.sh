#!/bin/bash
# Initial production setup script for AlwaysData

set -e  # Exit on error

echo "========================================="
echo "  Production Setup - AlwaysData"
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

echo -e "${BLUE}Project directory: $PROJECT_DIR${NC}"
echo ""

# Check if we're on AlwaysData
if [[ ! $HOME =~ ^/home/y-b ]]; then
    echo -e "${YELLOW}⚠️  Warning: This doesn't look like an AlwaysData environment${NC}"
    read -p "Continue anyway? (yes/no): " -r
    echo
    if [[ ! $REPLY =~ ^[Yy](es)?$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

cd "$PROJECT_DIR"

echo -e "${BLUE}Step 1/7: Checking Python version...${NC}"
python_version=$(python3 --version)
echo "Python version: $python_version"
echo -e "${GREEN}✅ Python check completed${NC}"
echo ""

echo -e "${BLUE}Step 2/7: Installing Poetry...${NC}"
if ! command -v poetry &> /dev/null; then
    echo "Installing Poetry..."
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    echo -e "${GREEN}✅ Poetry installed${NC}"
else
    echo "Poetry is already installed"
    echo -e "${GREEN}✅ Poetry check completed${NC}"
fi
echo ""

echo -e "${BLUE}Step 3/7: Creating necessary directories...${NC}"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/backend/alembic/versions"
echo -e "${GREEN}✅ Directories created${NC}"
echo ""

echo -e "${BLUE}Step 4/7: Setting up environment file...${NC}"
if [ ! -f "$PROJECT_DIR/.env" ]; then
    if [ -f "$PROJECT_DIR/.env.production.example" ]; then
        cp "$PROJECT_DIR/.env.production.example" "$PROJECT_DIR/.env"
        echo -e "${GREEN}✅ .env file created from .env.production.example${NC}"
        echo -e "${YELLOW}⚠️  IMPORTANT: Edit .env file and set the following:${NC}"
        echo "   - DATABASE_URL (PostgreSQL connection string)"
        echo "   - SECRET_KEY (generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))')"
        echo "   - OPENAI_API_KEY (if using AI features)"
        echo ""
        read -p "Press Enter after you've updated the .env file..."
    else
        echo -e "${RED}Error: .env.production.example not found!${NC}"
        exit 1
    fi
else
    echo ".env file already exists"
    echo -e "${GREEN}✅ Environment file check completed${NC}"
fi
echo ""

echo -e "${BLUE}Step 5/7: Installing Python dependencies...${NC}"
cd "$PROJECT_DIR/backend"
poetry install --no-dev --no-interaction
echo -e "${GREEN}✅ Dependencies installed${NC}"
echo ""

echo -e "${BLUE}Step 6/7: Setting up database...${NC}"
echo "Testing database connection..."

# Source environment variables
set -a
source "$PROJECT_DIR/.env"
set +a

# Test database connection with Python
poetry run python3 << EOF
from app.config import settings
from app.database import engine
try:
    with engine.connect() as conn:
        print("✅ Database connection successful!")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo ""
    read -p "Do you want to run database migrations now? (yes/no): " -r
    echo
    if [[ $REPLY =~ ^[Yy](es)?$ ]]; then
        echo "Running migrations..."
        poetry run alembic upgrade head
        echo -e "${GREEN}✅ Database migrations completed${NC}"

        echo ""
        read -p "Do you want to create an admin user? (yes/no): " -r
        echo
        if [[ $REPLY =~ ^[Yy](es)?$ ]]; then
            echo "Creating admin user..."
            poetry run python3 scripts/create_admin_user.py
            echo -e "${GREEN}✅ Admin user created${NC}"
        fi
    fi
else
    echo -e "${RED}❌ Database connection failed. Please check your DATABASE_URL in .env${NC}"
    exit 1
fi
echo ""

echo -e "${BLUE}Step 7/7: Setting up Supervisor (if available)...${NC}"
if command -v supervisorctl &> /dev/null; then
    echo "Supervisor is available"
    if [ -f "$PROJECT_DIR/backend/deploy/supervisor.conf" ]; then
        echo "Please add the supervisor configuration to AlwaysData:"
        echo "  File: $PROJECT_DIR/backend/deploy/supervisor.conf"
        echo "  Location: Add via AlwaysData control panel > Sites > Advanced"
    fi
else
    echo -e "${YELLOW}⚠️  Supervisor not found. You'll need to configure the application startup via AlwaysData control panel.${NC}"
fi
echo ""

echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  Production setup completed!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Configure your AlwaysData site to point to: $PROJECT_DIR/backend"
echo "2. Set WSGI entry point to: wsgi:application"
echo "3. Set Python version to 3.11+"
echo "4. Start the application via AlwaysData control panel"
echo "5. Verify health check: https://yellow-boat.org/health"
echo ""
echo "For deployment updates, use: $PROJECT_DIR/backend/scripts/deploy.sh"
echo ""
