# Violet Subnet - Audio Processing Network

Welcome to **Violet**, a cutting-edge Bittensor subnet dedicated to decentralized audio processing and AI-powered speech technologies. Our network leverages the power of distributed computing to provide high-quality transcription, text-to-speech synthesis, and audio analysis services.

## 🌟 Overview

Violet subnet enables a decentralized ecosystem where miners provide computational power for audio processing tasks while validators ensure quality and distribute rewards. The network integrates with a hosted proxy server for seamless task management and real-time processing.

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


## 🔐 Security & Best Practices

- **Never commit `.env` files** - They contain sensitive credentials
- **Use virtual environments** - Isolate dependencies for each project
- **Keep API keys secure** - Rotate keys if compromised
- **Monitor GPU usage** - Ensure adequate cooling and power supply
- **Regular updates** - Keep dependencies and codebase up to date

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
- Python 3.12+
- CUDA 11.8+ (for GPU acceleration)
- Bittensor CLI (`pip install bittensor-cli`)

## 🚀 Quick Start

### Step 1: Clone the Repository

```bash
git clone https://github.com/hivetrainai/violet.git
cd violet
```

### Step 2: Create Virtual Environment

**Important:** Always create and activate a virtual environment before installing dependencies:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
# Install the Violet package in development mode
pip install -e .

# Install additional requirements
pip install -r requirements.txt
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

**Mainnet (NetUID TBC):**
```bash
btcli subnet register --netuid 49 --subtensor.network finney --wallet.name <your_wallet_name> --wallet.hotkey default
```

**Testnet (NetUID 292):**
```bash
btcli subnet register --netuid 292 --subtensor.network test --wallet.name <your_wallet_name> --wallet.hotkey default
```

**Note:** Registration requires 0.005 TAO for mainnet or test tokens for testnet.

### Step 7: Run the Miner

**Mainnet:**
```bash
python neurons/miner.py \
  --netuid TBC \
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

**Mainnet:**
```bash
python neurons/validator.py \
  --netuid TBC \
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
| Mainnet | TBC     | finney       | 0.005 TAO         |
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


## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section
- Review the API documentation

---

**Built with ❤️ for the Bittensor community**
