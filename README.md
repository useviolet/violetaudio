# Violet Subnet - Audio Processing Network

Welcome to **Violet**, a cutting-edge Bittensor subnet dedicated to decentralized audio processing and AI-powered speech technologies. Our network leverages the power of distributed computing to provide high-quality transcription, text-to-speech synthesis, and audio analysis services.

## 🌟 Overview

Violet subnet enables a decentralized ecosystem where miners provide computational power for audio processing tasks while validators ensure quality and distribute rewards. The network integrates with a hosted proxy server for seamless task management and real-time processing.

## 💻 System Requirements

### Operating System
- **Linux** (Ubuntu 20.04+ recommended)
- **macOS** (10.15+)

### Hardware Requirements

#### For Miners
- **RAM**: 12 GB minimum
- **Storage**: 500 GB SSD
- **GPU**: NVIDIA GPU with 12 GB VRAM minimum (recommended for TTS tasks)
- **Network**: Stable internet connection (100+ Mbps)

#### For Validators
- **RAM**: 12 GB minimum
- **Storage**: 500 GB SSD
- **GPU**: NVIDIA GPU with 12 GB VRAM minimum
- **Network**: Stable internet connection (100+ Mbps)

### Software Dependencies
- **Python 3.10** (Required - Coqui TTS does not support Python 3.12)
- CUDA 11.8+ (for GPU acceleration)
- Bittensor CLI (`pip install bittensor-cli`)

**⚠️ Important:** Coqui TTS (used for text-to-speech) requires Python 3.9-3.11. Python 3.12 is NOT supported. You MUST use Python 3.10 in a virtual environment.

## 🚀 Quick Start

### Step 1: Clone the Repository

```bash
git clone https://github.com/hivetrainai/violet.git
cd violet
```

### Step 2: Create Python 3.10 Virtual Environment

**⚠️ CRITICAL:** Coqui TTS requires Python 3.10. You MUST create a Python 3.10 virtual environment before installing dependencies.

```bash
# Check if Python 3.10 is available
python3.10 --version

# If Python 3.10 is not installed, install it first:
# On macOS (using Homebrew):
# brew install python@3.10
# On Ubuntu/Debian:
# sudo apt-get install python3.10 python3.10-venv

# Create Python 3.10 virtual environment
python3.10 -m venv venv_py310

# Activate virtual environment
# On Linux/macOS:
source venv_py310/bin/activate
# On Windows:
venv_py310\Scripts\activate

# Verify Python version (should show 3.10.x)
python --version
```

### Step 3: Install Dependencies

**⚠️ IMPORTANT:** Ensure you are in the Python 3.10 virtual environment before installing:

```bash
# Verify you're in Python 3.10 virtual environment
python --version  # Should show Python 3.10.x

# Upgrade pip and setuptools
pip install --upgrade pip setuptools wheel

# Install the Violet package in development mode
pip install -e .

# Install additional requirements
pip install -r requirements.txt

# Note: If you encounter numpy/numba version conflicts, ensure numpy < 1.25.0
# pip install "numpy>=1.24.0,<1.25.0" --force-reinstall
```

### Step 4: Set Up Environment Variables

Create a `.env` file in the project root directory with the following required variables:

```bash
# Required: Hugging Face Token for model downloads
HF_TOKEN=your_huggingface_token_here

# Required: API Key for miner (get from subnet admin)
MINER_API_KEY=your_miner_api_key_here

# Required: API Key for validator (get from subnet admin)
VALIDATOR_API_KEY=your_validator_api_key_here

# Optional: Proxy server URL (defaults to production)
PROXY_SERVER_URL=https://violet-proxy-bl4w.onrender.com
```

#### Getting Your Tokens and API Keys

1. **Hugging Face Token:**
   - Go to https://huggingface.co/settings/tokens
   - Create a new token with "read" permissions
   - Copy the token and add it to your `.env` file as `HF_TOKEN`

2. **Miner/Validator API Keys:**
   - Contact the subnet administrator to obtain your API keys
   - Add them to your `.env` file as `MINER_API_KEY` and/or `VALIDATOR_API_KEY`

**Important:** Never commit your `.env` file to version control. It contains sensitive credentials.

### Step 5: Create Wallets

Create a coldkey and hotkey for your subnet wallet:

```bash
# Install bittensor CLI (if not already installed)
pip install bittensor-cli

# Create a coldkey for the validator/miner
btcli wallet new_coldkey --wallet.name <your_wallet_name>

# Create a hotkey for the validator/miner
btcli wallet new_hotkey --wallet.name <your_wallet_name> --wallet.hotkey default
```

### Step 6: Register on the Subnet

Register as a miner or validator on the subnet:

**Mainnet (NetUID 49):**
```bash
btcli subnet register --netuid 49 --subtensor.network finney --wallet.name <your_wallet_name> --wallet.hotkey default
```

**Testnet (NetUID 292):**
```bash
btcli subnet register --netuid 292 --subtensor.network test --wallet.name <your_wallet_name> --wallet.hotkey default
```

**Note:** Registration requires 0.005 TAO for mainnet or test tokens for testnet.

### Step 7: Run the Miner

**⚠️ IMPORTANT:** Before running the miner, ensure you are in the Python 3.10 virtual environment:

```bash
# Activate Python 3.10 virtual environment
source venv_py310/bin/activate  # Linux/macOS
# or
venv_py310\Scripts\activate  # Windows

# Verify you're using Python 3.10
python --version  # Should show Python 3.10.x
```

**Mainnet:**
```bash
python neurons/miner.py \
  --netuid 49 \
  --subtensor.network finney \
  --wallet.name <your_wallet_name> \
  --wallet.hotkey <your_hotkey> \
  --logging.debug \
  --axon.ip 0.0.0.0 \
  --axon.port <PORT> \
  --axon.external_ip <YOUR_PUBLIC_IP> \
  --axon.external_port <PORT>
```

**Testnet:**
```bash
python neurons/miner.py \
  --netuid 292 \
  --subtensor.network test \
  --wallet.name <your_wallet_name> \
  --wallet.hotkey <your_hotkey> \
  --logging.debug \
  --axon.ip 0.0.0.0 \
  --axon.port <PORT> \
  --axon.external_ip <YOUR_PUBLIC_IP> \
  --axon.external_port <PORT>
```

### Step 8: Run the Validator

**⚠️ IMPORTANT:** Before running the validator, ensure you are in the Python 3.10 virtual environment:

```bash
# Activate Python 3.10 virtual environment
source venv_py310/bin/activate  # Linux/macOS
# or
venv_py310\Scripts\activate  # Windows

# Verify you're using Python 3.10
python --version  # Should show Python 3.10.x
```

**Mainnet:**
```bash
python neurons/validator.py \
  --netuid 49 \
  --subtensor.network finney \
  --wallet.name <your_wallet_name> \
  --wallet.hotkey <your_hotkey> \
  --logging.debug \
  --axon.ip 0.0.0.0 \
  --axon.port <PORT> \
  --axon.external_ip <YOUR_PUBLIC_IP> \
  --axon.external_port <PORT>
```

**Testnet:**
```bash
python neurons/validator.py \
  --netuid 292 \
  --subtensor.network test \
  --wallet.name <your_wallet_name> \
  --wallet.hotkey <your_hotkey> \
  --logging.debug \
  --axon.ip 0.0.0.0 \
  --axon.port <PORT> \
  --axon.external_ip <YOUR_PUBLIC_IP> \
  --axon.external_port <PORT>
```

## 📋 Network Configuration

| Network | NetUID | Network Name | Registration Cost |
|---------|--------|--------------|-------------------|
| Mainnet | 49     | finney       | 0.005 TAO         |
| Testnet | 292    | test         | 0.005 test tokens |

## 🔧 Configuration

### GPU Configuration

Ensure your GPU is properly configured for CUDA:

```bash
# Check CUDA installation
nvidia-smi

# Verify PyTorch CUDA support
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python -c "import torch; print(f'CUDA version: {torch.version.cuda}')"
```

### Environment Variables Summary

| Variable | Required | Description |
|----------|----------|-------------|
| `HF_TOKEN` | ✅ Yes | Hugging Face token for downloading AI models |
| `MINER_API_KEY` | ✅ Yes (for miners) | API key for miner authentication |
| `VALIDATOR_API_KEY` | ✅ Yes (for validators) | API key for validator authentication |
| `PROXY_SERVER_URL` | ❌ No | Proxy server URL (defaults to production) |

## 🏗️ System Architecture

### Network Overview

Violet subnet operates as a decentralized network of miners and validators, coordinated through a centralized proxy server for task distribution and result aggregation.

#### Key Components

1. **Miners** (Computational Nodes)
   - Audio Processing: Transcription, TTS, and audio analysis
   - Task Execution: Processes assigned tasks with AI models
   - Response Submission: Sends results back to proxy server
   - Performance Monitoring: Tracks processing times and accuracy

2. **Validators** (Quality Assurance)
   - Response Evaluation: Assesses miner response quality
   - Reward Distribution: Calculates and distributes TAO rewards
   - Network Health: Monitors miner performance and availability

3. **Proxy Server** (Task Management)
   - Task Distribution: Routes tasks to available miners
   - Response Aggregation: Collects and buffers miner responses
   - Quality Control: Validates responses before final delivery
   - Load Balancing: Distributes computational load across miners

## 🔐 Security & Best Practices

- **Never commit `.env` files** - They contain sensitive credentials
- **Use virtual environments** - Isolate dependencies for each project
- **Keep API keys secure** - Rotate keys if compromised
- **Monitor GPU usage** - Ensure adequate cooling and power supply
- **Regular updates** - Keep dependencies and codebase up to date

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the API documentation

---

**Built with ❤️ for the Bittensor community**
