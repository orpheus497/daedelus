#!/usr/bin/env bash
# CUDA and PyTorch Setup Fix Script for Daedelus
# Created by: orpheus497
# Ensures proper CUDA configuration and PyTorch GPU accessibility

set -e

echo "🔧 Daedelus CUDA/PyTorch Diagnostic & Fix Script"
echo "=================================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ] && [ "$1" != "--user-mode" ]; then
    echo -e "${YELLOW}Note: Some checks require root privileges${NC}"
    echo "Run with sudo for full diagnostics, or continue in user mode"
    echo ""
fi

# Detect Python
PYTHON_CMD=$(command -v python3.14 || command -v python3 || command -v python || echo "")
if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}❌ Python not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python: $($PYTHON_CMD --version)${NC}"

# Check CUDA installation
echo ""
echo "Checking CUDA installation..."
if command -v nvcc &> /dev/null; then
    NVCC_VERSION=$(nvcc --version | grep "release" | awk '{print $6}' | cut -d',' -f1)
    echo -e "${GREEN}✅ NVCC found: $NVCC_VERSION${NC}"
    CUDA_HOME=$(dirname $(dirname $(command -v nvcc)))
    echo "   CUDA_HOME: $CUDA_HOME"
else
    echo -e "${RED}❌ NVCC not found - CUDA may not be installed${NC}"
    CUDA_HOME=""
fi

# Check CUDA libraries
echo ""
echo "Checking CUDA libraries..."
CUDA_LIBS_FOUND=false
for cuda_path in /usr/local/cuda-* /usr/local/cuda /opt/cuda; do
    if [ -d "$cuda_path/lib64" ]; then
        echo -e "${GREEN}✅ CUDA libraries found: $cuda_path/lib64${NC}"
        CUDA_LIBS_FOUND=true
        CUDA_LIB_PATH="$cuda_path/lib64"
        break
    fi
done

if [ "$CUDA_LIBS_FOUND" = false ]; then
    echo -e "${YELLOW}⚠️  CUDA libraries not found in standard locations${NC}"
fi

# Check PyTorch installation and CUDA support
echo ""
echo "Checking PyTorch installation..."
PYTORCH_CHECK=$($PYTHON_CMD -c "
try:
    import torch
    print(f'INSTALLED|{torch.__version__}')
    if hasattr(torch.version, 'cuda') and torch.version.cuda:
        print(f'CUDA_VERSION|{torch.version.cuda}')
    else:
        print('CUDA_VERSION|CPU-only')
    
    # Try to check CUDA availability
    try:
        cuda_available = torch.cuda.is_available()
        print(f'CUDA_AVAILABLE|{cuda_available}')
        if cuda_available:
            print(f'GPU_COUNT|{torch.cuda.device_count()}')
            print(f'GPU_NAME|{torch.cuda.get_device_name(0)}')
    except Exception as e:
        print(f'CUDA_AVAILABLE|False')
        print(f'CUDA_ERROR|{str(e)}')
except ImportError:
    print('NOT_INSTALLED')
" 2>&1)

if echo "$PYTORCH_CHECK" | grep -q "NOT_INSTALLED"; then
    echo -e "${RED}❌ PyTorch not installed${NC}"
    PYTORCH_INSTALLED=false
else
    echo -e "${GREEN}✅ PyTorch installed${NC}"
    PYTORCH_INSTALLED=true
    
    # Parse PyTorch info
    PYTORCH_VERSION=$(echo "$PYTORCH_CHECK" | grep "INSTALLED" | cut -d'|' -f2)
    PYTORCH_CUDA=$(echo "$PYTORCH_CHECK" | grep "CUDA_VERSION" | cut -d'|' -f2)
    CUDA_AVAILABLE=$(echo "$PYTORCH_CHECK" | grep "CUDA_AVAILABLE" | cut -d'|' -f2)
    
    echo "   PyTorch Version: $PYTORCH_VERSION"
    echo "   Built with CUDA: $PYTORCH_CUDA"
    echo "   CUDA Available: $CUDA_AVAILABLE"
    
    if echo "$PYTORCH_CHECK" | grep -q "GPU_COUNT"; then
        GPU_COUNT=$(echo "$PYTORCH_CHECK" | grep "GPU_COUNT" | cut -d'|' -f2)
        GPU_NAME=$(echo "$PYTORCH_CHECK" | grep "GPU_NAME" | cut -d'|' -f2)
        echo -e "${GREEN}   GPU Detected: $GPU_NAME (Count: $GPU_COUNT)${NC}"
    fi
    
    if echo "$PYTORCH_CHECK" | grep -q "CUDA_ERROR"; then
        CUDA_ERROR=$(echo "$PYTORCH_CHECK" | grep "CUDA_ERROR" | cut -d'|' -f2)
        echo -e "${YELLOW}   CUDA Error: $CUDA_ERROR${NC}"
    fi
fi

# Check PEFT dependencies
echo ""
echo "Checking PEFT dependencies..."
PEFT_CHECK=$($PYTHON_CMD -c "
try:
    import peft
    import transformers
    import datasets
    import accelerate
    print('ALL_INSTALLED')
    print(f'peft|{peft.__version__}')
    print(f'transformers|{transformers.__version__}')
    print(f'datasets|{datasets.__version__}')
    print(f'accelerate|{accelerate.__version__}')
except ImportError as e:
    print(f'MISSING|{str(e)}')
" 2>&1)

if echo "$PEFT_CHECK" | grep -q "ALL_INSTALLED"; then
    echo -e "${GREEN}✅ All PEFT dependencies installed${NC}"
    echo "$PEFT_CHECK" | grep "|" | while read line; do
        echo "   $line" | tr '|' ' version '
    done
else
    echo -e "${RED}❌ Missing PEFT dependencies${NC}"
    MISSING=$(echo "$PEFT_CHECK" | grep "MISSING" | cut -d'|' -f2)
    echo "   Error: $MISSING"
fi

# Diagnosis and recommendations
echo ""
echo "=========================================="
echo "DIAGNOSIS & RECOMMENDATIONS"
echo "=========================================="
echo ""

if [ "$PYTORCH_INSTALLED" = true ] && [ "$CUDA_AVAILABLE" = "False" ] && [ -n "$CUDA_HOME" ]; then
    echo -e "${YELLOW}⚠️  ISSUE DETECTED: PyTorch cannot access CUDA${NC}"
    echo ""
    echo "Likely causes:"
    echo "1. PyTorch CUDA version mismatch with system CUDA"
    echo "   - System CUDA: $NVCC_VERSION"
    echo "   - PyTorch built with: $PYTORCH_CUDA"
    echo ""
    echo "2. Missing CUDA libraries in LD_LIBRARY_PATH"
    echo ""
    echo "RECOMMENDED FIXES:"
    echo ""
    echo "Option 1: Reinstall PyTorch with matching CUDA version"
    echo "  pip3 uninstall torch -y"
    echo "  # For CUDA 11.8 (most stable):"
    echo "  pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118"
    echo "  # For CUDA 12.1:"
    echo "  pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
    echo ""
    echo "Option 2: Set CUDA library path (temporary)"
    echo "  export LD_LIBRARY_PATH=$CUDA_LIB_PATH:\$LD_LIBRARY_PATH"
    echo "  export CUDA_HOME=$CUDA_HOME"
    echo ""
    echo "Option 3: Add to shell profile (permanent)"
    echo "  echo 'export LD_LIBRARY_PATH=$CUDA_LIB_PATH:\$LD_LIBRARY_PATH' >> ~/.bashrc"
    echo "  echo 'export CUDA_HOME=$CUDA_HOME' >> ~/.bashrc"
    echo "  source ~/.bashrc"
    echo ""
    echo "Option 4: Use CPU-only mode (slower but works)"
    echo "  # PyTorch will automatically fall back to CPU"
    echo "  # Training will be slower but functional"
    echo ""
elif [ "$PYTORCH_INSTALLED" = true ] && [ "$CUDA_AVAILABLE" = "True" ]; then
    echo -e "${GREEN}✅ GPU ACCELERATION WORKING!${NC}"
    echo ""
    echo "Your system is properly configured for GPU-accelerated training."
    echo "PEFT training will use GPU automatically."
elif [ -z "$CUDA_HOME" ]; then
    echo -e "${YELLOW}ℹ️  NO CUDA DETECTED${NC}"
    echo ""
    echo "CUDA is not installed on this system."
    echo "Daedelus will use CPU-only mode."
    echo ""
    echo "To enable GPU acceleration:"
    echo "1. Install NVIDIA CUDA Toolkit: https://developer.nvidia.com/cuda-downloads"
    echo "2. Install PyTorch with CUDA support"
    echo "3. Re-run this script to verify"
else
    echo -e "${GREEN}✅ SYSTEM APPEARS PROPERLY CONFIGURED${NC}"
fi

# Environment variable recommendations
echo ""
echo "=========================================="
echo "ENVIRONMENT SETUP"
echo "=========================================="
echo ""

if [ -n "$CUDA_HOME" ]; then
    echo "Add these to your shell profile (~/.bashrc or ~/.zshrc):"
    echo ""
    echo "export CUDA_HOME=$CUDA_HOME"
    echo "export PATH=\$CUDA_HOME/bin:\$PATH"
    echo "export LD_LIBRARY_PATH=\$CUDA_HOME/lib64:\$LD_LIBRARY_PATH"
    echo ""
fi

# Auto-fix option
echo ""
read -p "Would you like to automatically configure environment variables? (y/N) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]] && [ -n "$CUDA_HOME" ]; then
    SHELL_RC=""
    if [ -n "$ZSH_VERSION" ]; then
        SHELL_RC="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ]; then
        SHELL_RC="$HOME/.bashrc"
    else
        SHELL_RC="$HOME/.profile"
    fi
    
    echo "Adding CUDA environment variables to $SHELL_RC..."
    echo "" >> "$SHELL_RC"
    echo "# CUDA Configuration (added by Daedelus setup)" >> "$SHELL_RC"
    echo "export CUDA_HOME=$CUDA_HOME" >> "$SHELL_RC"
    echo "export PATH=\$CUDA_HOME/bin:\$PATH" >> "$SHELL_RC"
    echo "export LD_LIBRARY_PATH=\$CUDA_HOME/lib64:\$LD_LIBRARY_PATH" >> "$SHELL_RC"
    echo ""
    echo -e "${GREEN}✅ Environment variables added${NC}"
    echo "Run: source $SHELL_RC"
    echo "Or restart your terminal"
fi

echo ""
echo "=========================================="
echo "VERIFICATION COMPLETE"
echo "=========================================="
echo ""
echo "For more help, see: docs/TROUBLESHOOTING.md"
