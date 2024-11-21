# Getting Started with A9 Labs Bittensor Subnet for Fine-tuning LLMs

**Author**: A9 Labs  
## Introduction

A9 Labs Bittensor subnet is designed for fine-tuning large language models (LLMs) on custom datasets, creating optimized LLMs. Registered miners on this subnet compete by training models on specific datasets. The best-performing miner is rewarded using an incentive mechanism, ensuring high-quality contributions.

If you are new to Bittensor, refer to the [Bittensor Subnet Template Repository](https://github.com/opentensor/bittensor-subnet-template/blob/main/docs/running_on_staging.md) for initial setup.

This guide will walk you through getting started with mining on this subnet to participate in and compete for training jobs.

## Prerequisites

Before you start, ensure that:
- Bittensor is installed on your machine.
- You have at least **10 tokens** for registering and mining.

## Step-by-step Guide

### 1. Install Bittensor

Follow the installation instructions for Bittensor:
```{r, eval=FALSE}
# Install Bittensor (adjust command based on your OS)
pip install bittensor
```

### 2. Create Cold and Hot Wallet Keys

Generate and securely store your coldkey and hotkey. These keys will be used for subnet registration and mining.

```{bash, eval=FALSE}
# Generate Cold Key
btcli wallet new_coldkey --wallet.name miner

# Generate Hot Key
btcli wallet new_hotkey --wallet.name miner --wallet.hotkey default
```

**Important:** Save your mnemonic phrases securely as they are required for key recovery.

### 3. Register to the Subnet

Register on the testnet or mainnet subnet.

### For Testnet (UID 100)
```{bash, eval=FALSE}
btcli subnet register --wallet.name miner --wallet.hotkey default --subtensor.network test
```

### For Mainnet (UID 12)
```{bash, eval=FALSE}
btcli subnet register --wallet.name miner --wallet.hotkey default --subtensor.network main
```

Ensure you have **10 tokens** available in your wallet for the registration process.

### 4. Clone the Repository

Clone the A9 Labs repository for the mining setup.

```{bash, eval=FALSE}
git clone https://github.com/bigideainc/YoGPT_Bittensor.git
cd YoGPT_Bittensor
```

### 5. Install Required Packages

Install the necessary Python packages to set up the environment.

```{bash, eval=FALSE}
pip install e .
pip install -r requirements.txt
```

### 6. Select a Job and Start Mining

Visit the [YoGPT.ai Jobs Page](https://yogpt.ai/jobs) and select an open and running job. Note the `job_id` and `dataset_id` values for your chosen job.

Run the following command to start mining, replacing placeholders with your chosen parameters:

```{bash, eval=FALSE}
python3 neurons/runner_miner.py \
  --netuid <netuid> \
  --subtensor.network <stage> \
  --wallet.name <walletname> \
  ----wallet.hotkey <hotkeyname> \
  --epoch <epochs> \
  --learning_rate <learning rate> \
  --job_id <job_id> \
  --dataset_id <dataset id> \
  --batchsize <batch size>
```

### Example Command
```{bash, eval=FALSE}
python3 neurons/runner_miner.py \
  --netuid 100 \
  --subtensor.network test \
  --wallet.name miner \
  --wallet.hotkey default \
  -- model_type llama2 \
  --epoch 10 \
  --learning_rate 0.001 \
  --job_id 12345 \
  --dataset_id abc \
  --batchsize 32
```

**Note:** Ensure your environment includes a **GPU with at least 12 GB of RAM** for optimal performance.

# Tips to Outperform Competitors

To gain an edge:
- Fine-tune the following parameters:
  - **Batch size** (`--batchsize`)
  - **Learning rate** (`--learning_rate`)
  - **Epochs** (`--epoch`)
- Experiment with combinations to achieve better results.

# Conclusion

By following this guide, you are ready to participate in and compete for mining jobs on the A9 Labs Bittensor subnet. The incentive mechanism ensures your efforts are rewarded for optimal performance.

For further assistance, consult the [Bittensor documentation](https://github.com/opentensor/bittensor-subnet-template/blob/main/docs/running_on_staging.md) or reach out to the community.

Happy Mining!
