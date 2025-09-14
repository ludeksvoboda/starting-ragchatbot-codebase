#!/bin/bash

# Frontend Code Quality Check Script
# This script runs code quality checks on frontend files

echo "🎨 Frontend Code Quality Tools"
echo "============================="

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install Node.js and npm first."
    exit 1
fi

# Function to run a command and check its exit status
run_check() {
    local check_name="$1"
    local command="$2"

    echo "🔍 Running $check_name..."
    if eval "$command"; then
        echo "✅ $check_name passed"
        return 0
    else
        echo "❌ $check_name failed"
        return 1
    fi
}

# Initialize variables
format_passed=false
lint_passed=false

# Run Prettier format check
if run_check "Prettier format check" "npm run format:check"; then
    format_passed=true
fi

echo ""

# Run ESLint
if run_check "ESLint code quality check" "npm run lint"; then
    lint_passed=true
fi

echo ""
echo "📊 Summary:"
echo "==========="

if $format_passed && $lint_passed; then
    echo "🎉 All checks passed! Your frontend code is looking great!"
    exit 0
else
    echo "⚠️  Some checks failed. Run the following to fix issues:"
    if ! $format_passed; then
        echo "   - Format code: npm run format"
    fi
    if ! $lint_passed; then
        echo "   - Fix linting: npm run lint:fix"
    fi
    echo "   - Or fix all: npm run quality:fix"
    exit 1
fi