import json
import re
import logging
from datetime import datetime,timedelta
import requests
import tenacity
from typing import Dict, Any, List, Union
from loguru import logger
import numpy as np
from collections import defaultdict
from neurons.utils.proof_of_work import perform_ssh_tasks
from neurons.utils.api_utils import update_miner_compute_resource
import os
import time
from neurons.utils.uptimedata import calculate_miner_rewards,log_uptime
from fastapi import HTTPException

# # 
logger = logging.getLogger("remote_access")
import asyncio
# 
# from neurons.utils.pow import  perform_ssh_tasks
# from neurons.utils.compute_score import pow_tasks
# from neurons.utils.pogs import compare_compute_resources
# import asyncio
data={"zgUxdd0fosPUuUqLQivY":18}


import requests
from typing import List, Dict, Tuple
import logging

import requests
from loguru import logger
import time
import uuid
import bittensor as bt
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

# Cache for hotkey-to-UID mapping
_hotkey_to_uid_cache: Dict[str, int] = {}
_last_metagraph_sync: float = 0
_metagraph_sync_interval: float = 300  # 5 minutes in seconds
_metagraph = None
_miner_details_cache: Dict[str, dict] = {}

# Cache for miners data from the common API endpoint
_miners_data_cache: Dict = {}
_miners_data_last_fetch: float = 0
_miners_data_cache_interval: float = 3600  # 1 hour in seconds

def _sync_miners_data() -> None:
    """Fetches and caches miners data from the common API endpoint."""
    global _miners_data_cache, _miners_data_last_fetch
    try:
        headers = {
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "x-api-key": "dev-services-key",
            "x-use-encryption": "true",
            "service-key": "9e2e9d9d4370ba4c6ab90b7ab46ed334bb6b1a79af368b451796a6987988ed77",
            "service-name": "miner_service"
        }
        url = "https://polaris-interface.onrender.com/api/v1/services/miner/miners"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        _miners_data_cache = response.json().get("data", {}).get("miners", [])
        _miners_data_last_fetch = time.time()
        logger.info(f"Cached miners data, total miners: {len(_miners_data_cache)}")
    except Exception as e:
        logger.error(f"Error caching miners data: {e}")
        _miners_data_cache = []
        _miners_data_last_fetch = time.time()

def _get_cached_miners_data() -> List[dict]:
    """Returns cached miners data, refreshing if necessary."""
    global _miners_data_last_fetch
    if time.time() - _miners_data_last_fetch > _miners_data_cache_interval or not _miners_data_cache:
        _sync_miners_data()
    return _miners_data_cache

def _sync_metagraph(netuid: int, network: str = "finney") -> None:
    """Syncs the metagraph and updates the hotkey-to-UID cache."""
    global _hotkey_to_uid_cache, _last_metagraph_sync, _metagraph
    try:
        if time.time() - _last_metagraph_sync > _metagraph_sync_interval or _metagraph is None:
            subtensor = bt.subtensor(network=network)
            _metagraph = subtensor.metagraph(netuid=netuid)
            _hotkey_to_uid_cache = {hotkey: uid for uid, hotkey in enumerate(_metagraph.hotkeys)}
            _last_metagraph_sync = time.time()
            logger.info(f"Synced metagraph for netuid {netuid}, total nodes: {len(_metagraph.hotkeys)}")
    except Exception as e:
        logger.error(f"Error syncing metagraph for netuid {netuid}: {e}")
        _hotkey_to_uid_cache = {}
        _metagraph = None



# # Example usage
# allowed_uids = [0,4,13,27,231, 88, 188, 183, 203]  # Example list of allowed UIDs
# filtered_miners = get_filtered_miners(allowed_uids)
def extract_miner_ids(data: List[dict]) -> List[str]:
    """
    Extract miner IDs from the 'unique_miners_ips' list in the data.
    
    Args:
        data: List of dictionaries from get_miners_compute_resources().
    
    Returns:
        List of miner IDs (strings).
    """
    miner_ids = []
    
    try:
        # Validate input
        if not isinstance(data, list) or not data:
            logger.error("Data is not a non-empty list")
            return miner_ids
        
        # Access unique_miners_ips from the first dict
        multiple_miners_ips = data[0].get("unique_miners_ips", [])
        if not isinstance(multiple_miners_ips, list):
            logger.error("unique_miners_ips is not a list")
            return miner_ids
        
        # Extract keys from each dict in unique_miners_ips
        for item in multiple_miners_ips:
            if not isinstance(item, dict):
                logger.warning(f"Skipping non-dict item: {item}")
                continue
            if len(item) != 1:
                logger.warning(f"Skipping dict with unexpected key count: {item}")
                continue
            miner_id = next(iter(item))  # Get the single key
            if isinstance(miner_id, str) and miner_id:
                miner_ids.append(miner_id)
            else:
                logger.warning(f"Skipping invalid miner ID: {miner_id}")
        
        logger.info(f"Extracted {len(miner_ids)} miner IDs")
        return miner_ids
    
    except Exception as e:
        logger.error(f"Error extracting miner IDs: {e}")
        return miner_ids

def get_miners_compute_resources() -> dict[str, list]:
    """
    Retrieves compute resources for all miners.

    Returns:
        dict[str, list]: A dictionary mapping miner IDs to their compute_resources_details list.
    """
    try:
        # Get cached miners data
        miners = _get_cached_miners_data()

        # Construct dictionary of miner IDs to compute resource details
        return extract_miner_ids(miners)

    except Exception as e:
        logger.error(f"Error fetching miners compute resources: {e}")
        return {} 


def get_miner_details(miner_id: str) -> dict:
    """
    Retrieve miner details from _miners_data_cache by miner_id.

    Args:
        miner_id (str): The ID of the miner to look up.

    Returns:
        dict: The miner details if found in _miners_data_cache, otherwise an empty dict.
    """
    logger.info(f"Looking up miner {miner_id} in _miners_data_cache")
    
    # Get cached miners data
    miners_data = _get_cached_miners_data()
    
    # Search for the miner by ID
    for miner in miners_data:
        
        if miner.get("id") == miner_id:
            logger.info(f"Found miner {miner_id} in _miners_data_cache")
            return miner
    
    logger.warning(f"Miner {miner_id} not found in _miners_data_cache")
    return {}


def filter_miners_by_id(
    bittensor_miners: Dict[str, int],
    netuid: int = 100,
    network: str = "test",
    hotkey_to_uid: Optional[Dict[str, int]] = None
) -> Dict[str, int]:
    """
    Keeps only miners from bittensor_miners whose IDs are in ids_to_keep, removing all others.
    
    Args:
        bittensor_miners: Dictionary mapping miner IDs to UIDs from get_filtered_miners.
        netuid: The subnet ID (default: 49).
        network: The Bittensor network to query (default: "finney").
        hotkey_to_uid: Optional cached mapping of hotkeys to UIDs (e.g., from PolarisNode).
    
    Returns:
        Dictionary mapping retained miner IDs to their UIDs.
    """
    try:
        # Validate inputs
        if not isinstance(bittensor_miners, dict):
            logger.error("bittensor_miners is not a dictionary")
            return {}
        # ids_to_keep = get_miners_compute_resources()
        
        ids_to_keep = list(bittensor_miners.keys())
        # Convert ids_to_keep to a set for O(1) lookup
        ids_to_keep_set = set(ids_to_keep)
        filtered_miners = {}

        # Use provided hotkey_to_uid cache or sync metagraph
        uid_cache = hotkey_to_uid if hotkey_to_uid is not None else _hotkey_to_uid_cache
        if hotkey_to_uid is None:
            _sync_metagraph(netuid, network)

        # Filter miners and verify hotkey-UID match
        for miner_id, uid in bittensor_miners.items():
            if miner_id not in ids_to_keep_set:
                logger.debug(f"Miner {miner_id} not in ids_to_keep, skipping")
                continue

            # Get miner details
            miner_details = get_miner_details(miner_id)
            hotkey = miner_details.get("bittensor_registration", {}).get("hotkey")
            if not hotkey or hotkey == "default":
                logger.warning(f"Invalid or missing hotkey for miner {miner_id}, skipping")
                continue

            # Verify UID using cached mapping
            subnet_uid = uid_cache.get(hotkey)
            if subnet_uid is None:
                _sync_metagraph(netuid, network)
                subnet_uid = _hotkey_to_uid_cache.get(hotkey)
                if subnet_uid is None:
                    logger.warning(f"Hotkey {hotkey} still not found after sync, skipping")
                    continue
            if subnet_uid != uid:
                logger.warning(f"UID mismatch for miner {miner_id}: metagraph UID {subnet_uid}, reported UID {uid}")
                continue

            filtered_miners[miner_id] = uid

        removed_count = len(bittensor_miners) - len(filtered_miners)
        logger.info(f"Kept {len(filtered_miners)} miners; removed {removed_count} miners")
        return filtered_miners

    except Exception as e:
        logger.error(f"Error filtering miners: {e}")
        return {}
# info = filter_miners_by_id(data, netuid=49, network="finney")
# data={'074rZehlXjTmxVH7ePRR': '114', '0e8CRALWdml3Pnf27Z4C': '1', '0icypK4pgzlAuTS9c5Kl': '117'}
butt ={'0WKTOGat9IUVDWIvbynF': '49', '0e8CRALWdml3Pnf27Z4C': '1', '0icypK4pgzlAuTS9c5Kl': '117', '0rny3Vhvmne8DKEDHVsa': '192', '1arXF3eSoXrzJbdsYFFC': '19', '1eYBryIJWdHV76gmxT2S': '73', '1wEnm0ZcnWF3JuW355NT': '88', '2LpLqWHWf7AUVY2vPy7i': '46', '2T8Yono9z7HeuBiFC5lc': '84', '2d5ayYKanlefjvEqEjLe': '134', '2jN2m0492M9YMpfWKoxA': '251', '2mv3Z4eepUpafF1m8Ezb': '109', '2pDgM79QuL0TJ8BV0kq7': '170', '340NevUIWzoVhiYh669j': '37', '41SxnzgjAOGtaL5ePiMi': '249', '4eQQsfwqiVsa2Tq2jRS5': '199', '4r6R71dJ4vyvErClkd9x': '18', '4xegUUWQnAcydIapQR4a': '30', '5lOdoOA3VCXy8DB77oet': '152', '5nhKJm3EpPbNOi9B9n5c': '77', '6osulq8hR6oHSCbYY7Kw': '80', '7RnrqmhcC8Nr5rD1YmLO': '134', '8hvxxUmM16AAouBqmRsr': '61', '8iqtRaIv1TaBMqf6xsbe': '219', '9d4KAfmPhXNhfsqlltq3': '179', 'A0bel7PDzm5KbjWaPxsg': '184', 'A6erViSHjYOp3hYCEpfr': '48', 'AJjmbYUdYwBRfQRs2WeX': '99', 'AOoep8Z84sMW3V57Mclc': '106', 'B14zFYQjX1kD2STC308b': '141', 'CNrPZc8dmBIYe9qcvyX8': '80', 'CQcHZz7sWxptocMqV5bS': '13', 'D63CYkdLlWMaIf5i8Yh8': '103', 'DaPaRHc26J9TKwV4QDZe': '139', 'DnA8lTBnRTPu2d1dURMb': '17', 'E4QpIamMLoYsNffk2Izw': '106', 'E83NDzEkSsmSAFoLmE2t': '231', 'EsFaFAb8RFvX8quj0SZ9': '78', 'FqvzUNI5vYs0lrlF5mcy': '231', 'GMkAHTWBFArdzciK7f9f': '128', 'GYcaqFyVvm3TAkImFYFF': '109', 'H77hxM1S9cfko0BFqae1': '216', 'HDyTezxTLaPF0xwtTZWQ': '76', 'HNeGZT1fO6MMiaFvQXig': '76', 'IHkLesAOka0VDC0oUM1F': '84', 'IZDOmm6Xxs5LysowIEi8': '199', 'IxMgfuxMUlhKGzIy9bJk': '13', 'J4wqKHpewMbvp8yaU8Rs': '76', 'Kb3SlbFxGNAinDQCbOLq': '144', 'KmPadhTTI9dozBvXP8F5': '133', 'LDToI07GM3y89vPmg1kt': '116', 'LvPSJbE9kIyBvTONrEc2': '195', 'M1kMP40ZaaAuX3s5ciCz': '146', 'MQ96vMXYB6J37ZV9llJm': '63', 'MRQC5BCoFiqkteuNiw9u': '134', 'MT4O1PvKSDOcR5qOLuOW': '197', 'N4jfmWUvQ1Yfd24dBUeM': '117', 'ND0e3MtUuukQR2PflDgL': '40', 'NTOadeiCOeRPj8vwoo9e': '22', 'NyKoFh9xhRzKERPBuft2': '217', 'OlAcCHLSkxjEZwWYgKhn': '0', 'P8vw6BuadZrqKEsoSsfP': '4', 'Q6qlifLxb88jgm3N3P1n': '64', 'QL2Pj9Bz2rBkGxAriGni': '99', 'QP7Y8pm9xiJfMxymWTGc': '143', 'Qo58fb85M23qr3xrJXpx': '64', 'Rtl3qvMWMvPIZv8D8UcQ': '21', 'S2XJuMnC29rn7JQUUPIS': '231', 'SCJ2kuYzFhzQtEiTzAJ8': '0', 'SHgoiWPB5htfBs3pXjIN': '231', 'SYciHeMGsVuu55n07oKr': '231', 'T2h1RxfnUwWrGVKmuFla': '79', 'Th91HEEhtWhC4ylJnPMt': '101', 'TuLi2e3paFDt1KrFy8EB': '127', 'VTFxMIrze1deRrZGDGKj': '87', 'VraUo9eCGiAmCTdnz9eC': '154', 'WtSMNXfN9tx8B3f2D7bp': '103', 'X8szTKXH49tbgAvVJQzk': '85', 'XORDAt6vljYsR31xowvj': '203', 'XaaJ0RSTMA5gDbWK29Sp': '3', 'Xc8tfUJj2VYSuDGY905Y': '249', 'YILsF8Qxxr8UlKkwLzKt': '33', 'ZmtqC29ZCqhDYQCpHaIG': '6', 'aETz6JkF5PdrZaAN0Htw': '35', 'aPEICXX6LBgjZDieNTJd': '84', 'c92FHnjhUWSvscCkbFG8': '117', 'cPCN9jRRePOJww4ZxO08': '181', 'ctQ2N2txxCQbrTU1Tmwn': '221', 'diBAfIGiwBUJSNODpgkP': '37', 'eIkiUFkJgSPBoF4kXkvV': '84', 'eKScaWF2H96SAdPk774y': '19', 'eURPmpf42Pee8rxGCj89': '0', 'egl7lBFHIGfJttPEiEPh': '21', 'fJGaHD2t22KZjU9hab0o': '76', 'grYwTA7fnZatSR3qcezS': '249', 'gwk7FImD0Yl0ZdZ0dBWc': '106', 'h1nYxCo2xom42gkiP0lu': '182', 'hLoV2OXPw60SFHF51vYE': '197', 'hUarPqf7f0DppiuYa0co': '112', 'iArUCOD1ylnGEgrKVDKV': '60', 'iE0kLc88vWpz1qzOiSS6': '191', 'iH1SFIA8nAtF8lEWDCey': '0', 'jJhod5DBG7OfzLgECReE': '86', 'kO4NiuQW6rXZveDq6VKo': '117', 'klOBnZR1eFWtgOFOWDej': '87', 'l2oQm4OHla9CUI50pmlT': '0', 'lZ2Q9Ys6R3ynP3gfBJ9w': '27', 'md94sqyYwsm8ppbJKR6q': '117', 'mdSIRXm1x8OJJScmIn9q': '117', 'navcdCleGl4qsbRNuzZN': '3', 'nzQIc2THYhLiINzEtRBb': '163', 'o6yYmyNsID29l7jJMqMU': '106', 'ovtxvy6xXX97szRH7IMO': '2', 'pbPc0b4Uf1TxjwtQHsSN': '188', 'pcMrbPzBFu8iNwZ2wint': '29', 'ph5UdhtGyj6RDcJZn94S': '231', 'q8oiO4OsVhPBYS2iikkA': '141', 'qmJEdNYSYaToARHVyiCb': '154', 'qtYNDsUkH0lxyLfAcmL7': '69', 'rLQ1kttoG0nREKPizFKH': '136', 'sG3D9cMKoayIHId8Ib2h': '183', 'sP1QXKT46E48RyIsY4kM': '106', 'tIvwvtUntMoOFmZNfUom': '148', 'tdnIlo7ZsStHVTMdFTTa': '181', 'tlw9yqs4QFX6LRNmyu9g': '166', 'uWwXp6L82A3Zc0Q1nqnP': '125', 'uuD9ZsZeYPXZu08gSa1u': '176', 'veZPvA20PexrpUHDPiKb': '40', 'vzazHtvIaPVWab976yps': '77', 'w8FVsQszJYRHDkgEQgNR': '147', 'xHXtyMvHAvZ4WEKHNLM6': '111', 'xOygCIuLsMSVZh4geA39': '158', 'xSQbPSAlnbPy5z7gnWnl': '117', 'xuzS80dcNyIZDWmfcmoT': '141', 'yHQj7qDWqnQVi61yqQzJ': '109', 'yRi08zQBH3NLvFcf19Bl': '75', 'yueTiA1EIVOYEoTI5886': '174', 'zMJCmBjFQlLDupQPRGqa': '72', 'zexiPSfZ404mKfg5s52U': '60', 'zlGakvHqctqNDoW69or8': '145', 'zuERoymc9gRWByz6jcXs': '170'}


# def get_filtered_miners() -> Tuple[Dict[str, Dict[str, str]], List[str]]:
#     try:
#         # Get cached miners data
#         miners = _get_cached_miners_data()

#         # Initialize outputs
#         filtered_miners = {}
#         miners_to_reject = []

#         for miner in miners:
#             miner_id = miner.get("id")
#             bittensor_reg = miner.get("bittensor_registration")

#             if not miner_id:
#                 continue 

#             if bittensor_reg is not None:
#                 miner_uid = bittensor_reg.get("miner_uid")
#                 hotkey = bittensor_reg.get("hotkey")
#                 if miner_uid is None or hotkey is None:
#                     miners_to_reject.append(miner_id)
#                 elif int(miner_uid):
#                     filtered_miners[miner_id] = {"miner_uid": str(miner_uid), "hotkey": hotkey}
#             else:
#                 miners_to_reject.append(miner_id)

#         return filtered_miners, miners_to_reject

#     except Exception as e:
#         logger.error(f"Error fetching filtered miners: {e}")
#         return {}, []

def get_miner_uid_by_hotkey(hotkey: str, netuid: int, network: str = "finney", force_refresh: bool = False) -> int | None:
    """
    Retrieves the miner UID for a given hotkey on a specific Bittensor subnet using cached metagraph data.

    Args:
        hotkey: The SS58 address of the miner's hotkey.
        netuid: The subnet ID (e.g., 49).
        network: The Bittensor network to query (default: "finney" for mainnet).
        force_refresh: If True, forces a refresh of the metagraph cache (default: False).

    Returns:
        int | None: The miner's UID if found, None otherwise.
    """
    global _hotkey_to_uid_cache, _last_metagraph_sync, _metagraph

    try:
        # Validate input
        if not hotkey or not isinstance(hotkey, str):
            logger.error(f"Invalid hotkey provided: {hotkey}")
            return None

        # Check if cache refresh is needed or forced
        if force_refresh or not _hotkey_to_uid_cache or time.time() - _last_metagraph_sync > _metagraph_sync_interval or _metagraph is None:
            logger.info(f"Refreshing metagraph cache for netuid {netuid} (force_refresh={force_refresh})")
            subtensor = bt.subtensor(network=network)
            logger.info(f"Connected to Bittensor network: {network}, querying subnet: {netuid}")
            _metagraph = subtensor.metagraph(netuid=netuid)
            _hotkey_to_uid_cache = {hotkey: uid for uid, hotkey in enumerate(_metagraph.hotkeys)}
            _last_metagraph_sync = time.time()
            logger.info(f"Synced metagraph for netuid {netuid}, total nodes: {len(_metagraph.hotkeys)}")

        # Look up hotkey in cache
        uid = _hotkey_to_uid_cache.get(hotkey)
        if uid is not None:
            logger.info(f"Found hotkey {hotkey} with UID {uid} in cache for subnet {netuid}")
            return uid

        logger.warning(f"Hotkey {hotkey} not found in cache for subnet {netuid}")
        return None

    except Exception as e:
        logger.error(f"Error retrieving miner UID for hotkey {hotkey} on subnet {netuid}: {e}")
        return None

tempo =90
current_block = 89378283
from typing import TypedDict, Tuple, List, Dict
SCORE_THRESHOLD = 0.005
MAX_CONTAINERS = 10
SCORE_WEIGHT = 0.33
CONTAINER_BONUS_MULTIPLIER = 2
SUPPORTED_NETWORKS = ["finney", "mainnet", "testnet"]

class MinerProcessingError(Exception):
    pass

class MinerResult(TypedDict):
    miner_id: str
    miner_uid: str
    hotkey: str
    total_score: float

class UptimeReward(TypedDict):
    reward_amount: float
    blocks_active: int
    uptime: int
    additional_details: Dict

async def get_filtered_miners_val(
    allowed_uids: List[int],
    netuid: int = 49,
    network: str = "finney",
    tempo: int = 4320,
    max_score: float = 100.0,
    current_block: int = 0
) -> Tuple[Dict[str, MinerResult], Dict[str, UptimeReward]]:
    """
    Fetches and processes miner data, aggregating scores and rewards for verified compute resources.

    Args:
        allowed_uids: List of allowed miner UIDs to filter.
        netuid: Subnet ID for hotkey verification (default: 49).
        network: Bittensor network name (default: "finney").
        tempo: Tempo interval in seconds (default: 4320 seconds = 72 minutes).
        max_score: Maximum normalized score (default: 100.0).
        current_block: Current block number for uptime logging (default: 0).

    Returns:
        Tuple of two dictionaries:
        - Dict mapping miner_id to {miner_id, miner_uid, hotkey, total_score}.
        - Dict mapping miner_id to {reward_amount, blocks_active, uptime, additional_details}.

    Raises:
        ValueError: If input parameters are invalid.
        MinerProcessingError: If processing fails critically.
    """
    # Input validation
    if not allowed_uids:
        logger.warning("Empty allowed_uids list provided")
        return {}, {}
    if tempo <= 0:
        raise ValueError("Tempo must be positive")
    if max_score <= 0:
        raise ValueError("max_score must be positive")
    if current_block < 0:
        raise ValueError("current_block cannot be negative")
    if network not in SUPPORTED_NETWORKS:
        raise ValueError(f"Network must be one of {SUPPORTED_NETWORKS}")

    try:
        # Get cached miners data
        miners = _get_cached_miners_data()

        miners =miners[:10]
        if not miners:
            logger.warning("No miners data available")
            return {}, {}
        logger.info(f"Fetched {len(miners)} miners")

        # Initialize result dictionaries
        results: Dict[str, MinerResult] = {}
        raw_results: Dict[str, dict] = {}
        uptime_rewards_dict: Dict[str, UptimeReward] = {}
        hotkey_cache: Dict[str, int] = {}
        uptime_logs = []

        # Iterate through miners
        for miner in miners:
            if (
                not miner.get("bittensor_registration")
                or miner["bittensor_registration"].get("miner_uid") is None
                or int(miner["bittensor_registration"]["miner_uid"]) not in allowed_uids
            ):
                continue

            hotkey = miner["bittensor_registration"].get("hotkey")
            miner_uid = int(miner["bittensor_registration"]["miner_uid"])
            miner_id = miner.get("id", "unknown")
            logger.info(f"Processing miner {miner_id} (UID: {miner_uid})")

            # Verify hotkey
            if hotkey not in hotkey_cache:
                logger.info(f"Verifying hotkey {hotkey} on subnet {netuid}")
                hotkey_cache[hotkey] = get_miner_uid_by_hotkey(hotkey, netuid, network)
            verified_uid = hotkey_cache[hotkey]
            if verified_uid is None or verified_uid != miner_uid:
                logger.warning(f"Hotkey verification failed for miner {miner_id}")
                continue

            # Initialize accumulators
            if miner_id not in uptime_rewards_dict:
                raw_results[miner_id] = {
                    "miner_id": miner_id,
                    "miner_uid": miner_uid,
                    "total_raw_score": 0.0
                }
                uptime_rewards_dict[miner_id] = {
                    "reward_amount": 0.0,
                    "blocks_active": 0,
                    "uptime": 0,
                    "additional_details": {"resources": {}}
                }
                results[miner_id] = {
                    "miner_id": miner_id,
                    "miner_uid": str(miner_uid),
                    "hotkey": hotkey,
                    "total_score": 0.0
                }

            # Process compute resources concurrently
            compute_details = miner.get("compute_resources_details", [])
            logger.info(f"Miner {miner_id} has {len(compute_details)} compute resource(s)")

            async def process_resource(resource, idx):
                resource_id = resource.get("id", "unknown")
                validation_status = resource.get("validation_status")
                if validation_status != "verified":
                    logger.info(f"Skipping resource {resource_id} (ID: {idx}): validation_status={validation_status}")
                    return None
                logger.info(f"Processing resource {idx} (ID: {resource_id})")
                ssh_value = resource.get("network", {}).get("ssh", "No SSH value available")
                try:
                    ssh_result = await perform_ssh_tasks(ssh_value)
                    pog_score = ssh_result["task_results"]["total_score"]
                    logger.info(f"Resource {resource_id}: compute_score={pog_score:.4f}")
                    return resource_id, pog_score
                except (OSError, asyncio.TimeoutError) as e:
                    logger.error(f"Error performing SSH tasks for resource {resource_id}: {e}")
                    return None
                except HTTPException as e:
                    logger.error(f"HTTP error performing SSH tasks for resource {resource_id}: {e.status_code} - {e.detail}")
                    return None
                except Exception as e:
                    logger.error(f"Unexpected error performing SSH tasks for resource {resource_id}: {e}")
                    return None

            tasks = [process_resource(resource, idx) for idx, resource in enumerate(compute_details, 1)]
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out None results and exceptions
            resource_results = []
            for result in task_results:
                if isinstance(result, Exception):
                    logger.error(f"Task failed with exception: {result}")
                    continue
                if result is not None:
                    resource_results.append(result)

            for resource_id, pog_score in resource_results:
                if pog_score < SCORE_THRESHOLD:
                    logger.warning(f"Resource {resource_id}: score={pog_score:.4f} below threshold")
                    update_result = update_miner_compute_resource(
                        miner_id=miner_id,
                        resource_id=resource_id,
                        reason=f"Low compute score: {pog_score:.4f}"
                    )
                    if not update_result:
                        logger.warning(f"Failed to update status for resource {resource_id}")
                    continue

                # Scale compute score
                scaled_compute_score = np.log1p(pog_score) * 10
                logger.info(f"Resource {resource_id}: scaled_compute_score={scaled_compute_score:.2f}")

                # Calculate uptime and rewards
                status = "active" if pog_score >= SCORE_THRESHOLD else "inactive"
                safe_resource_id = re.sub(r'[^a-zA-Z0-9_-]', '_', resource_id)
                log_file = os.path.join("logs/uptime", f"resource_{safe_resource_id}_uptime.json")
                is_new_resource = not os.path.exists(log_file)
                uptime_percent = 100.0 if status == "active" else 0.0

                uptime_logs.append({
                    "miner_uid": resource_id,
                    "status": status,
                    "compute_score": pog_score,
                    "uptime_reward": 0.0,
                    "block_number": current_block,
                    "reason": "Initial uptime log"
                })

                uptime_rewards = calculate_miner_rewards(resource_id, pog_score, current_block, tempo)
                if is_new_resource:
                    uptime_rewards["reward_amount"] = (tempo / 3600) * 0.2 * (pog_score / 100)
                    uptime_rewards["blocks_active"] = 1
                    uptime_rewards["uptime"] = tempo if status == "active" else 0
                    uptime_rewards["additional_details"] = {
                        "first_time_calculation": True,
                        "blocks_since_last": current_block
                    }

                uptime_rewards_dict[miner_id]["reward_amount"] += uptime_rewards["reward_amount"]
                uptime_rewards_dict[miner_id]["blocks_active"] += uptime_rewards.get("blocks_active", 0)
                uptime_rewards_dict[miner_id]["uptime"] += uptime_rewards.get("uptime", 0)
                uptime_rewards_dict[miner_id]["additional_details"]["resources"][resource_id] = {
                    "reward_amount": uptime_rewards["reward_amount"],
                    "blocks_active": uptime_rewards.get("blocks_active", 0),
                    "uptime": uptime_rewards.get("uptime", 0),
                    "details": uptime_rewards.get("additional_details", {})
                }
                logger.info(f"Resource {resource_id}: reward={uptime_rewards['reward_amount']:.6f}")

                uptime_logs.append({
                    "miner_uid": resource_id,
                    "status": status,
                    "compute_score": pog_score,
                    "uptime_reward": uptime_rewards["reward_amount"],
                    "block_number": current_block,
                    "reason": "Reward updated"
                })

                containers = get_containers_for_resource(resource_id)
                active_container_count = int(containers["running_count"])
                if active_container_count == 0 and containers.get("total_count", 0) > 0:
                    logger.warning(f"No running containers for resource {resource_id}, but {containers['total_count']} found")
                logger.info(f"Resource {resource_id}: running_containers={active_container_count}")

                # Calculate resource score
                effective_container_count = min(active_container_count, MAX_CONTAINERS) + np.log1p(max(0, active_container_count - MAX_CONTAINERS))
                container_bonus = np.sqrt(active_container_count) * CONTAINER_BONUS_MULTIPLIER
                base_score = (uptime_percent / 100) * 100 + SCORE_WEIGHT * effective_container_count + SCORE_WEIGHT * scaled_compute_score
                resource_score = (base_score * (tempo / 3600)) + container_bonus + uptime_rewards["reward_amount"]
                raw_results[miner_id]["total_raw_score"] += resource_score
                logger.info(
                    f"Resource {resource_id}: containers={active_container_count}, score={resource_score:.2f}"
                )

        # Normalize scores
        if raw_results:
            raw_scores = [entry["total_raw_score"] for entry in raw_results.values()]
            if raw_scores:
                percentile_90 = np.percentile(raw_scores, 90) if len(raw_scores) >= 5 else max(raw_scores)
                if percentile_90 > 0:
                    normalization_factor = max_score / percentile_90
                    for miner_id, entry in raw_results.items():
                        normalized_score = min(max_score, entry["total_raw_score"] * normalization_factor)
                        results[miner_id]["total_score"] = normalized_score
                        logger.info(
                            f"Miner ID {miner_id}: raw_score={entry['total_raw_score']:.2f}, normalized_score={normalized_score:.2f}"
                        )
                else:
                    logger.warning("All raw scores are zero. Skipping normalization.")
            else:
                logger.info("No valid scores to normalize.")
        else:
            logger.info("No valid resources to process.")

        # Write uptime logs
        for log_entry in uptime_logs:
            log_uptime(**log_entry)

        logger.info(f"Processed {len(results)} unique miner IDs")
        return results, uptime_rewards_dict

    except Exception as e:
        logger.critical(f"Fatal error processing miners: {e}")
        raise MinerProcessingError(f"Failed to process miners: {e}")

def get_containers_for_resource(resource_id: str) -> Dict[str, any]:
    """
    Fetches containers for a specific resource ID from the Polaris API and counts those in 'running' status.

    Args:
        resource_id (str): The ID of the compute resource to filter containers (e.g., 'c6469c-4b1c-4bca-98e6-b9bf45b88260').

    Returns:
        Dict[str, any]: A dictionary containing:
            - 'running_count': Number of containers in 'running' status for the resource.
            - 'containers': List of containers matching the resource_id (optional, for further use).
    """
    try:
        # Validate input
        if not resource_id or not isinstance(resource_id, str):
            logger.error(f"Invalid resource_id provided: {resource_id}")
            return {"running_count": 0, "containers": []}

        # Set up headers
        headers = {
            "Connection": "keep-alive",
            "x-api-key": "dev-services-key",
            "x-use-encryption": "true",
            "service-key": "9e2e9d9d4370ba4c6ab90b7ab46ed334bb6b1a79af368b451796a6987988ed77",
            "service-name": "miner_service",
            "Content-Type": "application/json"
        }

        # API endpoint
        url = "https://polaris-interface.onrender.com/api/v1/services/container/container/containers"
        logger.info(f"Fetching containers for resource_id: {resource_id} from {url}")

        # Send GET request
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raises an exception for 4xx/5xx status codes

        # Parse response
        container_list = response.json().get("containers", [])
        logger.info(f"Retrieved {len(container_list)} containers for resource_id: {resource_id}")

        # Filter containers by resource_id and count running ones
        matching_containers = [container for container in container_list if container.get("resource_id") == resource_id]
        running_count = sum(1 for container in matching_containers if container.get("status") == "running")

        logger.info(f"Found {len(matching_containers)} containers for resource_id {resource_id}, "
                    f"{running_count} in 'running' status")

        return {
            "running_count": running_count
        }

    except requests.RequestException as e:
        logger.error(f"Network error fetching containers for resource {resource_id}: {e}")
        return {"running_count": 0, "containers": []}
    except Exception as e:
        logger.error(f"Unexpected error fetching containers for resource {resource_id}: {e}")
        return {"running_count": 0, "containers": []}

def aggregate_rewards(results, uptime_rewards_dict):
    import logging
    aggregated_rewards = {}

    # Map miner_id to miner_uid from results
    miner_id_to_uid = {}
    for miner_id, info in results.items():
        miner_uid = info.get("miner_uid")
        miner_id_to_uid[miner_id] = miner_uid

        reward = info.get("total_score", 0)
        if miner_uid:
            if miner_uid not in aggregated_rewards:
                aggregated_rewards[miner_uid] = 0
            aggregated_rewards[miner_uid] += reward

    # Now aggregate from uptime_rewards_dict
    for miner_id, uptime_data in uptime_rewards_dict.items():
        uptime_reward = uptime_data.get("reward_amount", 0)

        miner_uid = miner_id_to_uid.get(miner_id)
        if miner_uid:
            if miner_uid not in aggregated_rewards:
                aggregated_rewards[miner_uid] = 0
            aggregated_rewards[miner_uid] += uptime_reward
        else:
            logging.warning(f"Miner ID {miner_id} not found in results. Skipping.")

    return aggregated_rewards


results= {'4r6R71dJ4vyvErClkd9x': {'miner_id': '4r6R71dJ4vyvErClkd9x', 'miner_uid': '18', 'hotkey': '5GpL9oHchoR5C6kr9YzfxvoWMitvqcdmS2m6NzaEEzNqigWx', 'total_score': 500}, '8hvxxUmM16AAouBqmRsr': {'miner_id': '8hvxxUmM16AAouBqmRsr', 'miner_uid': '61', 'hotkey': '5Cvx6ejZgavFzSST1orvwQBfy19Pa1AcfV3ar2zhT35BxtNy', 'total_score': 499.99090122099597}, 'AOoep8Z84sMW3V57Mclc': {'miner_id': 'AOoep8Z84sMW3V57Mclc', 'miner_uid': '106', 'hotkey': '5FecipgExVUeSfRaBCTZ6HEa9zpfcHkUXszZ6V7xFetejJHc', 'total_score': 0.0}, 'Qo58fb85M23qr3xrJXpx': {'miner_id': 'Qo58fb85M23qr3xrJXpx', 'miner_uid': '64', 'hotkey': '5En5mNrnjfwgLxJHhfM13rkLGVfokDm594wzdtMLNCw4KzWi', 'total_score': 496.30937524512456}, 'iArUCOD1ylnGEgrKVDKV': {'miner_id': 'iArUCOD1ylnGEgrKVDKV', 'miner_uid': '60', 'hotkey': '5CJ4qzLMfER9vcUbiCNAcoFm799y5gEMprzAQGDAXC6JmroJ', 'total_score': 497.1720950065381}, 'qIixWdT07862KFu87tIa': {'miner_id': 'qIixWdT07862KFu87tIa', 'miner_uid': '4', 'hotkey': '5HQtLy8dwVS9Ub2NURCGPDpA6hZHVnhJyHkyjLXsiPcDEUYM', 'total_score': 496.8987467297253}, 'qtYNDsUkH0lxyLfAcmL7': {'miner_id': 'qtYNDsUkH0lxyLfAcmL7', 'miner_uid': '69', 'hotkey': '5CtkvNmLVNWgd8UfsR6vpiNpgkeDqLaws2PLr41fJjdv5TUs', 'total_score': 495.6830916187421}, 's663AjJ38d9YEWvrn3Kn': {'miner_id': 's663AjJ38d9YEWvrn3Kn', 'miner_uid': '57', 'hotkey': '5F1r4TBMBVQp96MvqLiiA1na1ZmfTn53n8s9AGLoCYDEkLoV', 'total_score': 499.4458636313434}, 'uMtcUAZUQIKS1iCtTYUv': {'miner_id': 'uMtcUAZUQIKS1iCtTYUv', 'miner_uid': '48', 'hotkey': '5G7QNPTjgAA5rUv8zvZwwyik5GxSsZMiD4sDAXte94ofbi8u', 'total_score': 496.8987467297253}, 'zexiPSfZ404mKfg5s52U': {'miner_id': 'zexiPSfZ404mKfg5s52U', 'miner_uid': '60', 'hotkey': '5CJ4qzLMfER9vcUbiCNAcoFm799y5gEMprzAQGDAXC6JmroJ', 'total_score': 497.1720950065381}}
uptime_dict ={'4r6R71dJ4vyvErClkd9x': {'reward_amount': 2.4145e-05, 'blocks_active': 1, 'uptime': 99, 'additional_details': {'resources': {'cc5e3090-a267-4e73-b407-1dfb9cd50aa2': {'reward_amount': 2.4145e-05, 'blocks_active': 1, 'uptime': 99, 'details': {'first_time_calculation': True, 'blocks_since_last': 4659444}}}}}, '8hvxxUmM16AAouBqmRsr': {'reward_amount': 2.3705e-05, 'blocks_active': 1, 'uptime': 99, 'additional_details': {'resources': {'314b2044-06ce-42c5-9088-a84825991dfd': {'reward_amount': 2.3705e-05, 'blocks_active': 1, 'uptime': 99, 'details': {'first_time_calculation': True, 'blocks_since_last': 4659444}}}}}, 'AOoep8Z84sMW3V57Mclc': {'reward_amount': 0.0, 'blocks_active': 0, 'uptime': 0, 'additional_details': {'resources': {}}}, 'Qo58fb85M23qr3xrJXpx': {'reward_amount': 7.81e-06, 'blocks_active': 1, 'uptime': 99, 'additional_details': {'resources': {'034450e8-a29b-4fe9-b618-5762a2879049': {'reward_amount': 7.81e-06, 'blocks_active': 1, 'uptime': 99, 'details': {'first_time_calculation': True, 'blocks_since_last': 4659444}}}}}, 'iArUCOD1ylnGEgrKVDKV': {'reward_amount': 1.122e-05, 'blocks_active': 1, 'uptime': 99, 'additional_details': {'resources': {'a20cba62-0db0-46a3-b3e9-5f09ddea1d60': {'reward_amount': 1.122e-05, 'blocks_active': 1, 'uptime': 99, 'details': {'first_time_calculation': True, 'blocks_since_last': 4659444}}}}}, 'qIixWdT07862KFu87tIa': {'reward_amount': 1.0120000000000001e-05, 'blocks_active': 1, 'uptime': 99, 'additional_details': {'resources': {'ba4f23a7-6a32-4fbc-af0b-fcee9c06acb0': {'reward_amount': 1.0120000000000001e-05, 'blocks_active': 1, 'uptime': 99, 'details': {'first_time_calculation': True, 'blocks_since_last': 4659444}}}}}, 'qtYNDsUkH0lxyLfAcmL7': {'reward_amount': 5.445e-06, 'blocks_active': 1, 'uptime': 99, 'additional_details': {'resources': {'9175b852-0aa0-4f24-b652-cbf5d07ae950': {'reward_amount': 5.445e-06, 'blocks_active': 1, 'uptime': 99, 'details': {'first_time_calculation': True, 'blocks_since_last': 4659444}}}}}, 's663AjJ38d9YEWvrn3Kn': {'reward_amount': 2.112e-05, 'blocks_active': 1, 'uptime': 99, 'additional_details': {'resources': {'e44e86c7-b495-47e1-ba13-198e2eac1952': {'reward_amount': 2.112e-05, 'blocks_active': 1, 'uptime': 99, 'details': {'first_time_calculation': True, 'blocks_since_last': 4659444}}}}}, 'uMtcUAZUQIKS1iCtTYUv': {'reward_amount': 1.0120000000000001e-05, 'blocks_active': 1, 'uptime': 99, 'additional_details': {'resources': {'dee3929c-4171-40bf-af0c-6911c973b4be': {'reward_amount': 1.0120000000000001e-05, 'blocks_active': 1, 'uptime': 99, 'details': {'first_time_calculation': True, 'blocks_since_last': 4659444}}}}}, 'zexiPSfZ404mKfg5s52U': {'reward_amount': 1.122e-05, 'blocks_active': 1, 'uptime': 99, 'additional_details': {'resources': {'8756ebd8-9068-4b05-b2ed-759368964369': {'reward_amount': 1.122e-05, 'blocks_active': 1, 'uptime': 99, 'details': {'first_time_calculation': True, 'blocks_since_last': 4659444}}}}}}
data2 = aggregate_rewards(results=results, uptime_rewards_dict=uptime_dict)
print(f"hehehehe {data2}")

# async def verify_miners(
#     allowed_uids: List[int],
#     netuid: int = 49,
#     network: str = "finney",
# ) -> Tuple[Dict[str, MinerResult]]:
#     """
#     Fetches and processes miner data, aggregating scores and rewards for verified compute resources.

#     Args:
#         allowed_uids: List of allowed miner UIDs to filter.
#         netuid: Subnet ID for hotkey verification (default: 49).
#         network: Bittensor network name (default: "finney").
#         tempo: Tempo interval in seconds (default: 4320 seconds = 72 minutes).
#         max_score: Maximum normalized score (default: 100.0).
#         current_block: Current block number for uptime logging (default: 0).

#     Returns:
#         Tuple of two dictionaries:
#         - Dict mapping miner_id to {miner_id, miner_uid, hotkey, total_score}.
#         - Dict mapping miner_id to {reward_amount, blocks_active, uptime, additional_details}.

#     Raises:
#         ValueError: If input parameters are invalid.
#         MinerProcessingError: If processing fails critically.
#     """
#     # Input validation
#     if not allowed_uids:
#         logger.warning("Empty allowed_uids list provided")
#         return {}, {}
#     if network not in SUPPORTED_NETWORKS:
#         raise ValueError(f"Network must be one of {SUPPORTED_NETWORKS}")

#     try:
#         # Get cached miners data
#         miners = _get_cached_miners_data()

#         miners =miners[:10]
#         if not miners:
#             logger.warning("No miners data available")
#             return {}, {}
#         logger.info(f"Fetched {len(miners)} miners")

#         # Initialize result dictionaries
#         hotkey_cache: Dict[str, int] = {}

#         # Iterate through miners
#         for miner in miners:
#             if (
#                 not miner.get("bittensor_registration")
#                 or miner["bittensor_registration"].get("miner_uid") is None
#                 or int(miner["bittensor_registration"]["miner_uid"]) not in allowed_uids
#             ):
#                 continue

#             miner_uid = int(miner["bittensor_registration"]["miner_uid"])
#             miner_id = miner.get("id", "unknown")
#             logger.info(f"Processing miner {miner_id} (UID: {miner_uid})")

#             # Process compute resources concurrently
#             compute_details = miner.get("compute_resources_details", [])
#             logger.info(f"Miner {miner_id} has {len(compute_details)} compute resource(s)")

#             async def process_resource(resource, idx):
#                 resource_id = resource.get("id", "unknown")
#                 validation_status = resource.get("validation_status")
#                 if validation_status == "verified":
#                     return None
#                 logger.info(f"Processing resource {idx} (ID: {resource_id})")
#                 ssh_value = resource.get("network", {}).get("ssh", "No SSH value available")
#                 try:
#                     ssh_result = await perform_ssh_tasks(ssh_value)
#                     pog_score = ssh_result["task_results"]["total_score"]
#                     logger.info(f"Resource {resource_id}: compute_score={pog_score:.4f}")
#                     return resource_id, pog_score
#                 except (OSError, asyncio.TimeoutError) as e:
#                     logger.error(f"Error performing SSH tasks for resource {resource_id}: {e}")
#                     return None

#             tasks = [process_resource(resource, idx) for idx, resource in enumerate(compute_details, 1)]
#             resource_results = [r for r in await asyncio.gather(*tasks, return_exceptions=True) if r is not None]

#             for resource_id, pog_score in resource_results:
#                 if pog_score < SCORE_THRESHOLD:
#                     logger.warning(f"Resource {resource_id}: score={pog_score:.4f} below threshold")
#                     update_result = update_miner_compute_resource(
#                         miner_id=miner_id,
#                         resource_id=resource_id,
#                         reason=f"Low compute score: {pog_score:.4f}"
#                     )
#                     if not update_result:
#                         logger.warning(f"Failed to update status for resource {resource_id}")
#                     continue
#         return results, uptime_rewards_dict

#     except Exception as e:
#         logger.critical(f"Fatal error processing miners: {e}")
#         raise MinerProcessingError(f"Failed to process miners: {e}")



# async def main():
#     """
#     Example main function to run get_filtered_miners_val.
#     """
#     # Configure logging
#     logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

#     # Example allowed UIDs
#     allowed_uids = [18,0,37,195, 231]

#     # Run the function
#     results, uptime_rewards_dict = await get_filtered_miners_val(
#         allowed_uids=allowed_uids,
#         netuid=49,
#         network="finney",
#         tempo=4320,
#         current_block=1000
#     )

#     aggregated_rewards = aggregate_rewards(results, uptime_rewards_dict)
#     print(aggregate_rewards)


# if __name__ == "__main__":
#     asyncio.run(main())