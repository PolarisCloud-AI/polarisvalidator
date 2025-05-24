#!/bin/bash
# GPU Support Installation Script for Polaris Validator
# Automatically detects system and installs appropriate GPU libraries

set -e

echo "🚀 Installing GPU support for Polaris Validator..."

# Check if running with appropriate permissions
if [[ $EUID -eq 0 ]]; then
   echo "❌ Don't run this script as root/sudo"
   exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python and pip
if ! command_exists python3; then
    echo "❌ Python 3 is required but not found"
    exit 1
fi

echo "✅ Python 3 found"

# Check if we're in an externally-managed environment (like macOS with Homebrew)
NEEDS_VENV=false
if python3 -m pip install --help >/dev/null 2>&1; then
    # Try a test install to see if we need a virtual environment
    if ! python3 -m pip list >/dev/null 2>&1; then
        NEEDS_VENV=true
    fi
else
    echo "❌ pip is required but not found"
    exit 1
fi

# Check if pip needs virtual environment (externally-managed-environment)
if python3 -c "import sys; exit(0 if hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix else 1)" 2>/dev/null; then
    echo "✅ Already in virtual environment"
    PIP_CMD="python3 -m pip"
elif python3 -m pip install --dry-run pynvml 2>&1 | grep -q "externally-managed-environment"; then
    echo "⚠️  Externally-managed environment detected (macOS/Homebrew)"
    echo "🔨 Creating virtual environment for GPU libraries..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv_gpu" ]; then
        python3 -m venv venv_gpu
    fi
    
    # Activate virtual environment
    source venv_gpu/bin/activate
    echo "✅ Virtual environment activated"
    PIP_CMD="pip"
    
    # Ensure pip is up to date
    pip install --upgrade pip
else
    echo "✅ Using system pip"
    PIP_CMD="python3 -m pip"
fi

# Install base GPU monitoring (works everywhere)
echo "📦 Installing NVIDIA GPU monitoring (pynvml)..."
$PIP_CMD install pynvml>=11.4.1

# Detect NVIDIA GPUs
echo "🔍 Detecting NVIDIA GPUs..."
if command_exists nvidia-smi; then
    echo "✅ NVIDIA GPU detected!"
    
    # Check CUDA version
    if command_exists nvcc; then
        CUDA_VERSION=$(nvcc --version | grep "release" | sed 's/.*release //' | sed 's/,.*//')
        echo "🎯 CUDA version detected: $CUDA_VERSION"
        
        if [[ $CUDA_VERSION == 12.* ]]; then
            echo "📦 Installing CuPy for CUDA 12.x..."
            $PIP_CMD install cupy-cuda12x>=12.0.0
        elif [[ $CUDA_VERSION == 11.* ]]; then
            echo "📦 Installing CuPy for CUDA 11.x..."
            $PIP_CMD install cupy-cuda11x>=11.0.0
        else
            echo "⚠️  Unknown CUDA version, skipping CuPy installation"
        fi
    else
        echo "⚠️  CUDA toolkit not found, GPU compute will be limited"
        echo "💡 Install CUDA from: https://developer.nvidia.com/cuda-downloads"
    fi
else
    echo "ℹ️  No NVIDIA GPU detected (nvidia-smi not found)"
fi

# Install OpenCL support (for AMD/Intel/Apple GPUs)
echo "📦 Installing OpenCL support..."
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    echo "🐧 Linux detected - installing OpenCL..."
    $PIP_CMD install pyopencl>=2023.1
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "🍎 macOS detected - installing OpenCL..."
    $PIP_CMD install pyopencl>=2023.1
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows
    echo "🪟 Windows detected - installing OpenCL..."
    $PIP_CMD install pyopencl>=2023.1
else
    echo "❓ Unknown OS: $OSTYPE"
    echo "📦 Attempting OpenCL installation anyway..."
    $PIP_CMD install pyopencl>=2023.1
fi

# Test installation
echo "🧪 Testing GPU library installation..."

# Use the correct Python environment for testing
if [ -n "${VIRTUAL_ENV}" ]; then
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

$PYTHON_CMD -c "
try:
    import pynvml
    print('✅ pynvml (NVIDIA monitoring) - OK')
except ImportError:
    print('❌ pynvml - Failed')

try:
    import pyopencl
    print('✅ pyopencl (OpenCL) - OK')
except ImportError:
    print('❌ pyopencl - Failed')

try:
    import cupy
    print('✅ cupy (CUDA compute) - OK')
except ImportError:
    print('ℹ️  cupy (CUDA compute) - Not available (install CUDA if needed)')

print('🔧 Testing GPU validation system...')
try:
    from gpu_proof_of_work import GPUProofOfWork
    gpu_pow = GPUProofOfWork()
    print(f'✅ GPU validation initialized: enabled={gpu_pow.enabled}')
    print(f'   NVIDIA available: {gpu_pow.nvidia_available}')
    print(f'   OpenCL available: {gpu_pow.opencl_available}')
except ImportError as e:
    print(f'⚠️  GPU validation module not found: {e}')
    print('   Make sure gpu_proof_of_work.py is in the current directory')
"

echo ""
echo "🎉 GPU support installation completed!"
echo ""
echo "📋 Summary:"
echo "   • pynvml: NVIDIA GPU monitoring"
echo "   • pyopencl: AMD/Intel/Apple GPU support"
echo "   • cupy: NVIDIA CUDA compute (if CUDA available)"
echo ""

if [ -n "${VIRTUAL_ENV}" ]; then
    echo "🔧 Virtual environment created: venv_gpu"
    echo "   To activate: source venv_gpu/bin/activate"
    echo "   To run validator: source venv_gpu/bin/activate && python3 neurons/validator.py"
else
    echo "🚀 Your Polaris Validator now has enhanced GPU validation capabilities!"
    echo "   Run with: python3 neurons/validator.py"
fi 