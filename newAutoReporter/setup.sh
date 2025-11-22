#!/bin/bash
# Tender Intelligence Report Generator - Setup Script

echo "=================================="
echo "Tender Report Generator - Setup"
echo "=================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi
echo "✅ Python found"
echo ""

# Install dependencies
echo "Installing dependencies..."
echo ""

# Try regular pip first
pip install -r requirements.txt 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Regular pip failed, trying with --break-system-packages..."
    pip install --break-system-packages -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        echo "Please install manually:"
        echo "  pip install requests psycopg2-binary openai python-dotenv"
        exit 1
    fi
fi

echo ""
echo "✅ Dependencies installed"
echo ""

# Create output directories
echo "Creating output directories..."
mkdir -p outputs/demo_reports
mkdir -p outputs/tender_reports
echo "✅ Directories created"
echo ""

# Copy environment template if .env doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✅ .env file created (edit with your settings)"
else
    echo "ℹ️  .env file already exists"
fi
echo ""

# Setup complete
echo "=================================="
echo "Setup Complete! ✅"
echo "=================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Run demo (no database needed):"
echo "   python demo_report_generator.py"
echo ""
echo "2. View generated reports:"
echo "   Open: ./outputs/demo_reports/*.html"
echo ""
echo "3. For production use:"
echo "   - Edit .env with your database credentials"
echo "   - Edit .env with your Bitdeer API key"
echo "   - Run: python report_integration.py single --tender-id '123'"
echo ""
echo "4. Read documentation:"
echo "   - INDEX.md - Navigation guide"
echo "   - QUICK_START.md - Integration guide"
echo ""
echo "Ready to generate reports! 🚀"
echo ""
