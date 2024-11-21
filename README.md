# Getting Started with A9 Labs Bittensor Subnet for Fine-tuning LLMs

**Author**: A9 Labs  
**Date**: `r Sys.Date()`  

---

## Introduction

The A9 Labs Bittensor subnet provides an environment for fine-tuning large language models (LLMs) on custom datasets, enabling the creation of optimized LLMs. Participants (miners) compete to train these models on specific datasets. Validators evaluate the submitted models, awarding the miner with the lowest evaluation loss. This subnet utilizes an incentive mechanism to reward high-performing miners and validators.

We assume that users of this subnet already have basic knowledge about Bittensor. If you are new to Bittensor, refer to the [Bittensor Subnet Template Repository](https://github.com/opentensor/bittensor-subnet-template/blob/main/docs/running_on_staging.md) for an introduction.

---

## Roles in the Subnet

### 1. **Miner**
- Miners train LLMs on provided datasets and submit models for evaluation.
- Miners compete to achieve the lowest evaluation loss on specific jobs.

### 2. **Validator**
- Validators download the models submitted by miners.
- They evaluate the models based on their performance (e.g., lowest evaluation loss) and reward the best-performing miner.

---

## Prerequisites

Ensure that:
1. Bittensor is installed on your machine.
2. You have at least **10 tokens** for registration and mining/validation.
3. Your environment includes a **GPU with at least 12 GB of RAM** for optimal performance.

---

## Step-by-step Guide

### A. Getting Started as a Miner

#### 1. Install Bittensor
```bash
pip install bittensor
```

#### 2. Create Wallet Keys
Generate cold and hot keys for the miner:
```bash
# Generate Cold Key
btcli wallet new_coldkey --wallet.name miner

# Generate Hot Key
btcli wallet new_hotkey --wallet.name miner --wallet.hotkey default
```

#### 3. Register as a Miner
Register on the testnet (UID 100) or mainnet (UID 12):
```bash
btcli subnet register --wallet.name miner --wallet.hotkey default --subtensor.network test
# or for mainnet:
btcli subnet register --wallet.name miner --wallet.hotkey default --subtensor.network main
```

#### 4. Clone the Repository
```bash
git clone https://github.com/tobiusaolo/yogptbittensor.git
cd yogptbittensor
```

#### 5. Install Required Packages
```bash
pip install e .
pip install -r requirements.txt
```

#### 6. Start Mining
Visit the [YoGPT.ai Jobs Page](https://yogpt.ai/jobs) and select an open job. Copy the `job_id` and `dataset_id` for your chosen job.

Run the mining program with the following command:
```bash
python3 neurons/runner_miner.py   --netuid <netuid>   --subtensor.network <network>   --wallet.name <walletname>   --wallet.hotkey <hotkeyname> --model_type <model_type>  --epoch <epochs>   --learning_rate <learning_rate>   --job_id <job_id>   --dataset_id <dataset_id>   --batchsize <batch_size>   --hf_token <huggingface_token>
```

**Example**:
```bash
python3 neurons/runner_miner.py   --netuid 100   --subtensor.network test   --wallet.name miner   --wallet.hotkey default --model_type llama2  --epoch 10   --learning_rate 0.001   --job_id 12345   --dataset_id mlabonne/guanaco-llama2-1k   --batchsize 32   --hf_token YOUR_HF_TOKEN
```

---

### B. Getting Started as a Validator

#### 1. Create Wallet Keys
Generate cold and hot keys for the validator:
```bash
# Generate Cold Key
btcli wallet new_coldkey --wallet.name validator

# Generate Hot Key
btcli wallet new_hotkey --wallet.name validator --wallet.hotkey default
```

#### 2. Register as a Validator
Register on the testnet (UID 100) or mainnet (UID 12):
```bash
btcli subnet register --wallet.name validator --wallet.hotkey default --subtensor.network test
# or for mainnet:
btcli subnet register --wallet.name validator --wallet.hotkey default --subtensor.network main
```

#### 3. Start Validating
Run the validator program with the following command:
```bash
python3 neurons/validator.py   --netuid <netuid>   --subtensor.network <network>   --wallet.name <walletname>   --wallet.hotkey <hotkeyname>
```

**Example**:
```bash
python3 neurons/validator.py   --netuid 100   --subtensor.network test   --wallet.name validator   --wallet.hotkey default
```

---

## Explanation of Arguments

| **Argument**           | **Description**                                                                          |
|-------------------------|------------------------------------------------------------------------------------------|
| `--netuid`             | Network UID (e.g., `100` for testnet or `12` for mainnet).                                |
| `--subtensor.network`  | Specifies the network (`test` or `main`).                                                 |
| `--wallet.name`        | Name of the wallet (e.g., `miner`, `validator`).                                          |
| `--wallet.hotkey`      | Name of the hotkey associated with the wallet (e.g., `default`).                          |
| `--epoch`              | Number of training epochs for the miner.                                                 |
| `--learning_rate`      | Learning rate for the miner's training process.                                           |
| `--job_id`             | Unique identifier for the mining job.                                                    |
| `--dataset_id`         | Identifier for the dataset to train the model.                                            |
| `--batchsize`          | Number of samples per training batch.                                                    |
| `--hf_token`           | Your HuggingFace API token for accessing datasets or pre-trained models.                  |

---

## Tips to Outperform Competitors

- Adjust the following parameters for better results:
  - **Batch size** (`--batchsize`)
  - **Learning rate** (`--learning_rate`)
  - **Epochs** (`--epoch`)
- Experiment with different combinations to optimize performance.
- Use GPUs with higher VRAM for faster processing.

---

## Conclusion

By following this guide, you can effectively participate in the A9 Labs Bittensor subnet as a miner or validator. The incentive mechanism rewards high-performing participants, ensuring competitive and high-quality contributions.

For further assistance, consult the [Bittensor documentation](https://github.com/opentensor/bittensor-subnet-template/blob/main/docs/running_on_staging.md) or join the community.

Happy Mining and Validating!