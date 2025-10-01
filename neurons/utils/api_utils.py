import requests
from loguru import logger
import time
import uuid
import bittensor as bt
from typing import List, Dict, Optional, Tuple, TypedDict, Any
from datetime import datetime, timedelta
import asyncio
from utils.uptimedata import calculate_miner_rewards, log_uptime
import asyncio
import re
import numpy as np
import os
import logging
from fastapi import HTTPException
logging.getLogger("websockets.client").setLevel(logging.WARNING)

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

# Scoring and reward configuration
SCORE_THRESHOLD = 0.03  # Optimized threshold to include more medium-performance resources
MAX_POW_SCORE = 1.0  # Maximum allowed POW score - resources above this are skipped
MAX_CONTAINERS = 20  # Increased from 10 to allow more containers
SCORE_WEIGHT = 0.4  # Increased from 0.33 for better balance
CONTAINER_BONUS_MULTIPLIER = 1.5  # Reduced from 2.0 for more balanced scoring
MAX_SCORE = 500.0  # Maximum normalized score

# Uptime multiplier tiers for high uptime incentives (calibrated to prevent excessive bonuses)
UPTIME_MULTIPLIER_TIERS = {
    "excellent": {"threshold": 95.0, "multiplier": 1.15},  # ≥95% uptime: +15% bonus (reduced from 30%)
    "good": {"threshold": 85.0, "multiplier": 1.10},       # ≥85% uptime: +10% bonus (reduced from 20%)
    "average": {"threshold": 70.0, "multiplier": 1.05},    # ≥70% uptime: +5% bonus (reduced from 10%)
    "poor": {"threshold": 0.0, "multiplier": 1.0}          # <70% uptime: No bonus
}

# Rented machine bonus configuration (calibrated to prevent excessive bonuses)
RENTED_MACHINE_BONUS = {
    "base_multiplier": 1.08,  # +8% base bonus for having running containers (reduced from 15%)
    "container_scaling": 0.01,  # +1% per additional container beyond 1 (reduced from 2%)
    "max_bonus": 1.20  # Maximum 20% bonus for high container counts (reduced from 35%)
}

SUPPORTED_NETWORKS = ["finney", "mainnet", "test"]


# Cache for hotkey-to-UID mapping
_hotkey_to_uid_cache: Dict[str, int] = {}
_last_metagraph_sync: float = 0
_metagraph_sync_interval: float = 300  # 5 minutes in seconds
_metagraph = None

# Alpha stake incentive configuration
ALPHA_STAKE_TIERS = {
    "high": {"threshold": 5000, "bonus_percentage": 20},      # ≥5000 Alpha: +20% bonus
    "medium": {"threshold": 1000, "bonus_percentage": 10},    # ≥1000 Alpha: +10% bonus
    "low": {"threshold": 0, "bonus_percentage": 0}            # <1000 Alpha: No bonus
}

def safe_convert_to_float(value, default=0.0):
    """
    Safely converts Bittensor objects (Balance, etc.) to float values.
    
    Args:
        value: The value to convert (could be Balance object, float, int, etc.)
        default: Default value if conversion fails
        
    Returns:
        float: The converted value or default
    """
    try:
        if hasattr(value, '__float__'):
            return float(value)
        elif isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            return float(value)
        else:
            return default
    except (ValueError, TypeError, AttributeError):
        return default

def calculate_uptime_multiplier(uptime_percent: float) -> float:
    """
    Calculate uptime multiplier based on uptime percentage.
    
    Args:
        uptime_percent: Uptime percentage (0-100)
        
    Returns:
        float: Multiplier value (1.0 = no bonus, 1.3 = +30% bonus)
    """
    try:
        for tier_name, tier_config in UPTIME_MULTIPLIER_TIERS.items():
            if uptime_percent >= tier_config["threshold"]:
                return tier_config["multiplier"]
        return 1.0  # Default no bonus
    except Exception as e:
        logger.error(f"Error calculating uptime multiplier: {e}")
        return 1.0

def calculate_rented_machine_bonus(active_container_count: int) -> float:
    """
    Calculate bonus multiplier for rented machines (those with running containers).
    
    Args:
        active_container_count: Number of running containers
        
    Returns:
        float: Bonus multiplier (1.0 = no bonus, 1.35 = +35% bonus)
    """
    try:
        if active_container_count == 0:
            return 1.0  # No bonus for machines without containers
        
        # Base bonus for having at least one container
        bonus_multiplier = RENTED_MACHINE_BONUS["base_multiplier"]
        
        # Additional bonus for multiple containers
        if active_container_count > 1:
            additional_bonus = min(
                (active_container_count - 1) * RENTED_MACHINE_BONUS["container_scaling"],
                RENTED_MACHINE_BONUS["max_bonus"] - RENTED_MACHINE_BONUS["base_multiplier"]
            )
            bonus_multiplier += additional_bonus
        
        # Cap at maximum bonus
        return min(bonus_multiplier, RENTED_MACHINE_BONUS["max_bonus"])
        
    except Exception as e:
        logger.error(f"Error calculating rented machine bonus: {e}")
        return 1.0

def calculate_fair_resource_score(
    uptime_percent: float,
    scaled_compute_score: float,
    active_container_count: int,
    tempo: int,
    uptime_multiplier: float = 1.0,
    rented_machine_bonus: float = 1.0
) -> float:
    """
    Calculate fair resource score with balanced weighting and bonuses.
    
    Args:
        uptime_percent: Uptime percentage (0-100)
        scaled_compute_score: Raw compute performance score (PoW)
        active_container_count: Number of running containers
        tempo: Block interval in seconds
        uptime_multiplier: Uptime-based bonus multiplier
        rented_machine_bonus: Rented machine bonus multiplier
        
    Returns:
        float: Calculated resource score
    """
    try:
        # Calculate effective container count with better scaling
        if active_container_count <= MAX_CONTAINERS:
            effective_container_count = active_container_count
        else:
            # Logarithmic scaling for very high container counts to prevent abuse
            effective_container_count = MAX_CONTAINERS + np.log1p(active_container_count - MAX_CONTAINERS)
        
        # Base score calculation: Uptime + Container management (reliability & activity)
        # Uptime represents reliability and availability
        uptime_score = (uptime_percent / 100) * 10  # 0-10 scale
        
        # Container score represents active work being done
        container_score = min(effective_container_count, MAX_CONTAINERS) * 0.5  # 0-10 scale (max 20 containers)
        
        # Base score: combination of reliability and activity
        base_score = uptime_score + container_score  # 0-20 scale
        
        # Apply tempo scaling
        tempo_scaled_score = base_score * (tempo / 3600) * 10  # Compensate for tempo reduction
        
        # Apply compute multiplier: Raw PoW score represents compute specs/power
        # Higher compute specs = higher multiplier = higher rewards
        compute_multiplier = scaled_compute_score  # Direct PoW score as multiplier
        
        # Final score: Base reliability × Compute power × Bonuses
        final_score = tempo_scaled_score * compute_multiplier * uptime_multiplier * rented_machine_bonus
        
        logger.debug(f"Resource score calculation: uptime={uptime_percent:.1f}%, "
                    f"compute={scaled_compute_score:.2f}, containers={active_container_count}, "
                    f"uptime_mult={uptime_multiplier:.2f}, rented_bonus={rented_machine_bonus:.2f}, "
                    f"final_score={final_score:.2f}")
        
        return final_score
        
    except Exception as e:
        logger.error(f"Error calculating fair resource score: {e}")
        return 0.0

def log_resource_scoring_details(
    resource_id: str,
    miner_id: str,
    pog_score: float,
    scaled_compute_score: float,
    uptime_percent: float,
    active_container_count: int,
    uptime_multiplier: float,
    rented_machine_bonus: float,
    final_score: float,
    tempo: int
) -> None:
    """
    Log comprehensive details about resource scoring for transparency and debugging.
    
    Args:
        resource_id: Resource identifier
        miner_id: Miner identifier
        pog_score: Raw compute score
        scaled_compute_score: Raw compute score (PoW)
        uptime_percent: Uptime percentage
        active_container_count: Number of running containers
        uptime_multiplier: Uptime bonus multiplier
        rented_machine_bonus: Rented machine bonus multiplier
        final_score: Final calculated score
        tempo: Block interval in seconds
    """
    try:
        logger.info("=" * 80)
        logger.info(f"📊 RESOURCE SCORING DETAILS - {resource_id}")
        logger.info("=" * 80)
        logger.info(f"Miner ID: {miner_id}")
        logger.info(f"Tempo: {tempo} seconds ({tempo/3600:.2f} hours)")
        
        # Raw scores
        logger.info(f"\n🔢 RAW SCORES:")
        logger.info(f"  Compute Score (PoW): {pog_score:.4f}")
        logger.info(f"  Raw Compute Score (PoW): {scaled_compute_score:.4f}")
        logger.info(f"  Uptime Percentage: {uptime_percent:.1f}%")
        logger.info(f"  Active Containers: {active_container_count}")
        
        # Base score components for logging
        uptime_score = (uptime_percent / 100) * 10
        container_score = min(active_container_count, MAX_CONTAINERS) * 0.5
        
        logger.info(f"\n⚖️  BASE SCORE COMPONENTS:")
        logger.info(f"  Uptime Score (Reliability): {uptime_score:.2f}")
        logger.info(f"  Container Score (Activity): {container_score:.2f}")
        logger.info(f"  Base Score: {uptime_score + container_score:.2f}")
        
        # Compute multiplier and bonus calculations
        logger.info(f"\n🚀 COMPUTE & BONUS CALCULATIONS:")
        logger.info(f"  Compute Multiplier (PoW): {scaled_compute_score:.4f}x")
        logger.info(f"  Uptime Multiplier: {uptime_multiplier:.2f}x")
        logger.info(f"  Rented Machine Bonus: {rented_machine_bonus:.2f}x")
        logger.info(f"  Combined Bonus: {uptime_multiplier * rented_machine_bonus:.2f}x")
        
        # Final score breakdown
        logger.info(f"\n🏆 FINAL SCORE BREAKDOWN:")
        logger.info(f"  Base Score (Reliability + Activity): {uptime_score + container_score:.2f}")
        tempo_scaled = (uptime_score + container_score) * (tempo / 3600) * 10
        logger.info(f"  Tempo Scaled: {tempo_scaled:.2f}")
        logger.info(f"  With Compute Multiplier: {tempo_scaled * scaled_compute_score:.2f}")
        logger.info(f"  Final Score (with bonuses): {final_score:.2f}")
        
        # Threshold check
        if pog_score >= SCORE_THRESHOLD:
            logger.info(f"✅ Resource PASSES threshold ({pog_score:.4f} >= {SCORE_THRESHOLD})")
        else:
            logger.info(f"❌ Resource FAILS threshold ({pog_score:.4f} < {SCORE_THRESHOLD})")
        
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error logging resource scoring details: {e}")

def log_scoring_system_summary() -> None:
    """
    Log a summary of the new fair scoring system and its benefits.
    """
    try:
        logger.info("🚀 NEW FAIR SCORING SYSTEM IMPLEMENTED")
        logger.info("=" * 80)
        logger.info("📋 SCORING CONFIGURATION:")
        logger.info(f"  Score Threshold: {SCORE_THRESHOLD} (increased from 0.005)")
        logger.info(f"  Max Score: {MAX_SCORE}")
        logger.info(f"  Max Containers: {MAX_CONTAINERS} (increased from 10)")
        logger.info(f"  Score Weight: {SCORE_WEIGHT} (increased from 0.33)")
        
        logger.info("\n⚖️  NEW SCORING APPROACH:")
        logger.info("  Base Score: Uptime (reliability) + Containers (activity)")
        logger.info("  Compute Multiplier: Raw PoW score as multiplier (specs/power)")
        logger.info("  Final Score: Base Score × Compute Multiplier × Bonuses")
        
        logger.info("\n🎁 BONUS SYSTEMS:")
        logger.info("  Uptime Multipliers:")
        for tier_name, tier_config in UPTIME_MULTIPLIER_TIERS.items():
            logger.info(f"    {tier_name.title()}: ≥{tier_config['threshold']}% → {tier_config['multiplier']}x")
        
        logger.info("  Rented Machine Bonuses:")
        logger.info(f"    Base Bonus: +{int((RENTED_MACHINE_BONUS['base_multiplier'] - 1) * 100)}% for running containers")
        logger.info(f"    Container Scaling: +{int(RENTED_MACHINE_BONUS['container_scaling'] * 100)}% per additional container")
        logger.info(f"    Max Bonus: +{int((RENTED_MACHINE_BONUS['max_bonus'] - 1) * 100)}%")
        
        logger.info("\n✅ IMPROVEMENTS:")
        logger.info("  • Removed double counting of uptime rewards in scores")
        logger.info("  • Linear compute score scaling (was logarithmic)")
        logger.info("  • Balanced component weighting")
        logger.info("  • Uptime-based bonus incentives")
        logger.info("  • Rented machine bonuses for active containers")
        logger.info("  • Median-based score normalization (was 90th percentile)")
        logger.info("  • No first-time penalties for new miners")
        logger.info("  • Reduced status multiplier extremes (3x vs 8x)")
        
        logger.info("\n🎯 FAIRNESS FEATURES:")
        logger.info("  • High uptime miners get up to +30% bonus")
        logger.info("  • Machines with containers get up to +35% bonus")
        logger.info("  • Compute performance properly weighted")
        logger.info("  • Container count scaling prevents abuse")
        logger.info("  • Transparent scoring with detailed logging")
        
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error logging scoring system summary: {e}")

def analyze_scoring_fairness(results: Dict[str, MinerResult]) -> Dict[str, Any]:
    """
    Analyze the fairness of the scoring system based on miner results.
    
    Args:
        results: Dictionary mapping miner_id to MinerResult
        
    Returns:
        Dictionary containing fairness analysis metrics
    """
    try:
        if not results:
            return {"error": "No results to analyze"}
        
        # Extract scores
        scores = [result.get("total_score", 0) for result in results.values()]
        if not scores:
            return {"error": "No scores found in results"}
        
        # Calculate fairness metrics
        import numpy as np
        
        fairness_metrics = {
            "total_miners": len(scores),
            "score_range": {
                "min": float(np.min(scores)),
                "max": float(np.max(scores)),
                "range": float(np.max(scores) - np.min(scores))
            },
            "score_distribution": {
                "mean": float(np.mean(scores)),
                "median": float(np.median(scores)),
                "std": float(np.std(scores)),
                "q25": float(np.percentile(scores, 25)),
                "q75": float(np.percentile(scores, 75))
            },
            "score_equality": {
                "gini_coefficient": float(calculate_gini_coefficient(scores)),
                "coefficient_of_variation": float(np.std(scores) / np.mean(scores)) if np.mean(scores) > 0 else 0
            },
            "performance_tiers": {
                "high_performers": len([s for s in scores if s >= np.percentile(scores, 80)]),
                "medium_performers": len([s for s in scores if np.percentile(scores, 20) <= s < np.percentile(scores, 80)]),
                "low_performers": len([s for s in scores if s < np.percentile(scores, 20)])
            }
        }
        
        # Analyze score distribution fairness
        fairness_assessment = {
            "is_fair": True,
            "issues": [],
            "recommendations": []
        }
        
        # Check for extreme score disparities
        if fairness_metrics["score_equality"]["gini_coefficient"] > 0.6:
            fairness_assessment["is_fair"] = False
            fairness_assessment["issues"].append("High score inequality detected")
            fairness_assessment["recommendations"].append("Consider adjusting scoring weights")
        
        # Check for score compression
        if fairness_metrics["score_range"]["range"] < 10:
            fairness_assessment["issues"].append("Score compression detected")
            fairness_assessment["recommendations"].append("Consider expanding score range")
        
        return {
            "fairness_metrics": fairness_metrics,
            "fairness_assessment": fairness_assessment,
            "analysis_timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Error analyzing scoring fairness: {e}")
        return {"error": str(e)}

def calculate_gini_coefficient(scores: List[float]) -> float:
    """
    Calculate Gini coefficient for score distribution fairness analysis.
    
    Args:
        scores: List of scores
        
    Returns:
        Gini coefficient (0 = perfect equality, 1 = perfect inequality)
    """
    try:
        import numpy as np
        
        if len(scores) == 0:
            return 0.0
        
        # Sort scores
        sorted_scores = np.sort(scores)
        n = len(sorted_scores)
        
        # Calculate Gini coefficient
        cumsum = np.cumsum(sorted_scores)
        return (n + 1 - 2 * np.sum(cumsum) / cumsum[-1]) / n if cumsum[-1] > 0 else 0.0
        
    except Exception as e:
        logger.error(f"Error calculating Gini coefficient: {e}")
        return 0.0

def generate_scoring_report(results: Dict[str, MinerResult], fairness_analysis: Dict[str, Any]) -> str:
    """
    Generate a comprehensive scoring report based on results and fairness analysis.
    
    Args:
        results: Dictionary mapping miner_id to MinerResult
        fairness_analysis: Fairness analysis results
        
    Returns:
        Formatted scoring report string
    """
    try:
        if "error" in fairness_analysis:
            return f"❌ Scoring Report Error: {fairness_analysis['error']}"
        
        fairness_metrics = fairness_analysis.get("fairness_metrics", {})
        fairness_assessment = fairness_analysis.get("fairness_assessment", {})
        
        report_lines = [
            "📊 COMPREHENSIVE SCORING REPORT",
            "=" * 50,
            f"📈 Total Miners Processed: {fairness_metrics.get('total_miners', 0)}",
            "",
            "🎯 SCORE DISTRIBUTION:",
            f"  • Range: {fairness_metrics.get('score_range', {}).get('min', 0):.2f} - {fairness_metrics.get('score_range', {}).get('max', 0):.2f}",
            f"  • Mean: {fairness_metrics.get('score_distribution', {}).get('mean', 0):.2f}",
            f"  • Median: {fairness_metrics.get('score_distribution', {}).get('median', 0):.2f}",
            f"  • Std Dev: {fairness_metrics.get('score_distribution', {}).get('std', 0):.2f}",
            "",
            "⚖️ FAIRNESS METRICS:",
            f"  • Gini Coefficient: {fairness_metrics.get('score_equality', {}).get('gini_coefficient', 0):.3f}",
            f"  • Coefficient of Variation: {fairness_metrics.get('score_equality', {}).get('coefficient_of_variation', 0):.3f}",
            "",
            "📊 PERFORMANCE TIERS:",
            f"  • High Performers (80th+ percentile): {fairness_metrics.get('performance_tiers', {}).get('high_performers', 0)}",
            f"  • Medium Performers (20th-80th percentile): {fairness_metrics.get('performance_tiers', {}).get('medium_performers', 0)}",
            f"  • Low Performers (<20th percentile): {fairness_metrics.get('performance_tiers', {}).get('low_performers', 0)}",
            "",
            "✅ FAIRNESS ASSESSMENT:",
            f"  • System Fair: {'Yes' if fairness_assessment.get('is_fair', False) else 'No'}",
        ]
        
        # Add issues if any
        issues = fairness_assessment.get("issues", [])
        if issues:
            report_lines.extend([
                "",
                "⚠️ IDENTIFIED ISSUES:",
            ])
            for issue in issues:
                report_lines.append(f"  • {issue}")
        
        # Add recommendations if any
        recommendations = fairness_assessment.get("recommendations", [])
        if recommendations:
            report_lines.extend([
                "",
                "💡 RECOMMENDATIONS:",
            ])
            for rec in recommendations:
                report_lines.append(f"  • {rec}")
        
        # Add top performers
        if results:
            sorted_results = sorted(results.items(), key=lambda x: x[1].get("total_score", 0), reverse=True)
            report_lines.extend([
                "",
                "🏆 TOP 5 PERFORMERS:",
            ])
            for i, (miner_id, result) in enumerate(sorted_results[:5], 1):
                score = result.get("total_score", 0)
                report_lines.append(f"  {i}. Miner {miner_id}: {score:.2f}")
        
        report_lines.extend([
            "",
            "=" * 50,
            f"Report Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}"
        ])
        
        return "\n".join(report_lines)
        
    except Exception as e:
        logger.error(f"Error generating scoring report: {e}")
        return f"❌ Report Generation Error: {str(e)}"


# Cache for miners data from the common API endpoint
_miners_data_cache: Dict = {}
_miners_data_last_fetch: float = 0
_miners_data_cache_interval: float = 600  # 10 minutes in seconds (original)

def _sync_miners_data() -> None:
    """Fetches and caches miners data from the common API endpoint."""
    global _miners_data_cache, _miners_data_last_fetch
    try:
        logger.info("🔄 PULLING LATEST DATA: Fetching fresh miners data from API...")
        headers = {
            "Connection": "keep-alive",
            "x-api-key": "",
            "service-key": "",
            "service-name": "miner_service",
            "Content-Type": "application/json"
        }
        url ="https://polariscloudai-main-pf5lil.laravel.cloud/api/v1/validator/miners"
        logger.info(f"📡 API Request: {url}")
        response = requests.get(url)
        response.raise_for_status()
        _miners_data_cache = response.json().get("miners", [])
        _miners_data_last_fetch = time.time()
        logger.info(f"✅ LATEST DATA PULLED: Cached {len(_miners_data_cache)} miners successfully")
        logger.info(f"⏰ Cache timestamp: {time.strftime('%H:%M:%S', time.localtime(_miners_data_last_fetch))}")
    except Exception as e:
        logger.error(f"❌ FAILED TO PULL LATEST DATA: Error caching miners data: {e}")
        _miners_data_cache = []
        _miners_data_last_fetch = time.time()

def _get_cached_miners_data(force_refresh: bool = False) -> List[dict]:
    """Returns cached miners data, refreshing if necessary or forced."""
    global _miners_data_last_fetch
    current_time = time.time()
    time_since_last_fetch = current_time - _miners_data_last_fetch
    
    # Check if we need to refresh
    needs_refresh = force_refresh or time_since_last_fetch > _miners_data_cache_interval or not _miners_data_cache
    
    if needs_refresh:
        if force_refresh:
            logger.info("🔄 FORCE REFRESH: Pulling latest data (forced)")
        elif time_since_last_fetch > _miners_data_cache_interval:
            logger.info(f"⏰ CACHE EXPIRED: Pulling latest data (expired {time_since_last_fetch:.1f}s ago)")
        elif not _miners_data_cache:
            logger.info("📭 EMPTY CACHE: Pulling latest data (no cached data)")
        
        _sync_miners_data()
    else:
        logger.info(f"📋 USING CACHED DATA: {len(_miners_data_cache)} miners (cached {time_since_last_fetch:.1f}s ago)")
    
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



def aggregate_rewards(results, uptime_rewards_dict):
    import logging
    import json
    import os
    logger.debug(f"Aggregating rewards for scored miners.................")

    aggregated_rewards = {}
    cpu_gpu_breakdown = {}  # Track CPU/GPU scores separately

    # Map miner_id to miner_uid from results
    miner_id_to_uid = {}
    for miner_id, info in results.items():
        miner_uid = info.get("miner_uid")
        miner_id_to_uid[miner_id] = miner_uid

        reward = info.get("total_score", 0)
        cpu_score = info.get("cpu_score", 0)
        gpu_score = info.get("gpu_score", 0)
        has_cpu = info.get("has_cpu_resources", False)
        
        if miner_uid:
            if miner_uid not in aggregated_rewards:
                aggregated_rewards[miner_uid] = 0
                cpu_gpu_breakdown[miner_uid] = {
                    "cpu_score": 0.0,
                    "gpu_score": 0.0,
                    "has_cpu_resources": False
                }
            
            aggregated_rewards[miner_uid] += reward
            cpu_gpu_breakdown[miner_uid]["cpu_score"] += cpu_score
            cpu_gpu_breakdown[miner_uid]["gpu_score"] += gpu_score
            cpu_gpu_breakdown[miner_uid]["has_cpu_resources"] = cpu_gpu_breakdown[miner_uid]["has_cpu_resources"] or has_cpu

    # Now aggregate from uptime_rewards_dict
    for miner_id, uptime_data in uptime_rewards_dict.items():
        uptime_reward = uptime_data.get("reward_amount", 0)

        miner_uid = miner_id_to_uid.get(miner_id)
        if miner_uid:
            if miner_uid not in aggregated_rewards:
                aggregated_rewards[miner_uid] = 0
                cpu_gpu_breakdown[miner_uid] = {
                    "cpu_score": 0.0,
                    "gpu_score": 0.0,
                    "has_cpu_resources": False
                }
            aggregated_rewards[miner_uid] += uptime_reward
        else:
            logging.warning(f"Miner ID {miner_id} not found in results. Skipping.")

    return aggregated_rewards, cpu_gpu_breakdown

async def reward_mechanism(
    allowed_uids: List[int],
    netuid: int = 49,
    network: str = "finney",
    tempo: int = 4320,
    max_score: float = 500.0,
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
        logger.info("📊 REWARD MECHANISM: Getting miners data for processing...")
        miners = _get_cached_miners_data()

        if not miners:
            logger.warning("⚠️ REWARD MECHANISM: No miners data available")
            return {}, {}
        logger.info(f"✅ REWARD MECHANISM: Processing {len(miners)} miners")

        # Log the new fair scoring system summary
        log_scoring_system_summary()

        # Initialize result dictionaries
        results: Dict[str, MinerResult] = {}
        raw_results: Dict[str, dict] = {}
        uptime_rewards_dict: Dict[str, UptimeReward] = {}
        hotkey_cache: Dict[str, int] = {}
        uptime_logs = []

        # Iterate through miners
        for miner in miners:
            # Handle both "miner_id" and "id" fields, ensure string type
            miner_id_raw = miner.get("miner_id") or miner.get("id")
            miner_id = str(miner_id_raw) if miner_id_raw is not None else "unknown"
            
            # Check if miner has compute resources first
            compute_details = miner.get("resource_details", [])
            if not compute_details:
                logger.info(f"Miner {miner_id} has no compute resources, skipping")
                continue
            
            # Check if miner is Bittensor registered
            bittensor_details = miner.get("bittensor_details")
            if not bittensor_details or bittensor_details.get("miner_uid") is None:
                logger.info(f"Miner {miner_id} is not Bittensor registered, skipping")
                continue
                
            miner_uid = int(bittensor_details["miner_uid"])
            if miner_uid not in allowed_uids:
                logger.info(f"Miner {miner_id} UID {miner_uid} not in allowed UIDs, skipping")
                continue
                
            hotkey = bittensor_details.get("hotkey")
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
                    "total_raw_score": 0.0,
                    "cpu_score": 0.0,
                    "gpu_score": 0.0,
                    "has_cpu_resources": False
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
                    "total_score": 0.0,
                    "cpu_score": 0.0,
                    "gpu_score": 0.0,
                    "has_cpu_resources": False
                }

            # Process compute resources concurrently
            logger.info(f"Miner {miner_id} has {len(compute_details)} compute resource(s)")

            # Collect all resource IDs for batch container processing
            resource_ids = []
            for resource in compute_details:
                resource_id_raw = resource.get("id", "unknown")
                resource_id = str(resource_id_raw) if resource_id_raw != "unknown" else "unknown"
                if resource.get("validation_status") == "verified":
                    resource_ids.append(resource_id)
            
            # Batch fetch container data for all resources
            container_data = {}
            if resource_ids:
                try:
                    container_data = get_containers_for_multiple_resources(resource_ids)
                    logger.debug(f"Batch fetched container data for {len(resource_ids)} resources")
                except Exception as e:
                    logger.warning(f"Error batch fetching containers: {e}")
                    container_data = {rid: {"running_count": 0} for rid in resource_ids}

            async def process_resource(resource, idx):
                resource_id_raw = resource.get("id", "unknown")
                resource_id = str(resource_id_raw) if resource_id_raw != "unknown" else "unknown"
                validation_status = resource.get("validation_status")
                if validation_status != "verified":
                    logger.info(f"Skipping resource {resource_id} (ID: {idx}): validation_status={validation_status}")
                    return None
                logger.info(f"Processing resource {idx} (ID: {resource_id}) miner uid {miner_uid}")

                # Check monitoring_status fields
                monitoring_status = resource.get("monitoring_status", {})
                if not monitoring_status:
                    logger.warning(
                        f"Skipping resource {resource_id} for miner UID {miner_uid}: Empty monitoring_status"
                    )
                    return None
                conn_status = monitoring_status.get("conn", {}).get("status")
                auth_status = monitoring_status.get("auth", {}).get("status")
                docker_running = monitoring_status.get("docker", {}).get("running")
                docker_user_group = monitoring_status.get("docker", {}).get("user_group")
                if (
                    conn_status != "ok" or
                    auth_status != "ok"
                ):
                    logger.info(
                        f"Resource {resource_id} failed monitoring checks: "
                        f"conn_status={conn_status}, auth_status={auth_status}, "
                        f"docker_running={docker_running}, docker_user_group={docker_user_group}"
                    )
                    return None

                try:
                    # Use pow total as pog_score
                    pog_score = monitoring_status.get("pow", {}).get("total", 0.0)
                    logger.info(f"Resource {resource_id}: compute_score={pog_score:.4f}")
                    return resource_id, pog_score
                except Exception as e:
                    logger.error(f"Unexpected error fetching pog_score for resource {resource_id}: {e}")
                    return None

            tasks = [process_resource(resource, idx) for idx, resource in enumerate(compute_details, 1)]
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out None results and exceptions
            resource_results = []
            for result in task_results:
                if isinstance(result, Exception):
                    logger.error(f"Resource processing task failed with exception: {result}")
                    continue
                if result is not None:
                    resource_results.append(result)

            # Create a mapping of resource_id to resource_type
            resource_type_map = {}
            for resource in compute_details:
                resource_id_raw = resource.get("id", "unknown")
                resource_id_str = str(resource_id_raw) if resource_id_raw != "unknown" else "unknown"
                resource_type_map[resource_id_str] = resource.get("resource_type", "Unknown")

            for resource_id, pog_score in resource_results:
                # Skip resources with POW scores above maximum allowed
                if pog_score > MAX_POW_SCORE:
                    logger.warning(f"Resource {resource_id}: POW score={pog_score:.4f} exceeds maximum {MAX_POW_SCORE} - SKIPPING ENTIRELY")
                    continue
                
                if pog_score < SCORE_THRESHOLD:
                    logger.warning(f"Resource {resource_id}: score={pog_score:.4f} below threshold - SKIPPING ENTIRELY")
                    # Skip this resource entirely - no need to update status or process further
                    continue

                # Get resource type (CPU or GPU)
                resource_type = resource_type_map.get(resource_id, "Unknown")
                logger.info(f"Resource {resource_id}: type={resource_type}, POW={pog_score:.4f}")
                
                # Track if miner has CPU resources
                if resource_type == "CPU":
                    raw_results[miner_id]["has_cpu_resources"] = True

                # Use raw compute score (PoW) directly - no scaling needed
                compute_score = pog_score
                logger.info(f"Resource {resource_id}: compute_score={compute_score:.4f}")

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

                # Calculate uptime rewards (separate from scoring)
                # Calculate uptime rewards with graceful error handling
                try:
                    uptime_rewards = calculate_miner_rewards(resource_id, pog_score, current_block, tempo)
                    if is_new_resource:
                        uptime_rewards["reward_amount"] = (tempo / 3600) * 0.2 * (pog_score / 100)
                        uptime_rewards["blocks_active"] = 1
                        uptime_rewards["uptime"] = tempo if status == "active" else 0
                        uptime_rewards["additional_details"] = {
                            "first_time_calculation": True,
                            "blocks_since_last": current_block
                        }

                    uptime_rewards_dict[miner_id]["reward_amount"] += uptime_rewards.get("reward_amount", 0)
                    uptime_rewards_dict[miner_id]["blocks_active"] += uptime_rewards.get("blocks_active", 0)
                    uptime_rewards_dict[miner_id]["uptime"] += uptime_rewards.get("uptime", 0)
                    uptime_rewards_dict[miner_id]["additional_details"]["resources"][resource_id] = {
                        "reward_amount": uptime_rewards.get("reward_amount", 0),
                        "blocks_active": uptime_rewards.get("blocks_active", 0),
                        "uptime": uptime_rewards.get("uptime", 0),
                        "details": uptime_rewards.get("additional_details", {})
                    }
                    logger.info(f"Resource {resource_id}: reward={uptime_rewards.get('reward_amount', 0):.6f}")
                except Exception as e:
                    logger.warning(f"Error calculating uptime rewards for resource {resource_id}: {e}")
                    # Use default values if calculation fails
                    default_reward = (tempo / 3600) * 0.2 * (pog_score / 100) if pog_score >= SCORE_THRESHOLD else 0
                    uptime_rewards_dict[miner_id]["reward_amount"] += default_reward
                    uptime_rewards_dict[miner_id]["blocks_active"] += 1
                    uptime_rewards_dict[miner_id]["uptime"] += tempo if status == "active" else 0

                uptime_logs.append({
                    "miner_uid": resource_id,
                    "status": status,
                    "compute_score": pog_score,
                    "uptime_reward": uptime_rewards["reward_amount"],
                    "block_number": current_block,
                    "reason": "Reward updated"
                })

                # Get container information for rented machine bonus
                # Use pre-fetched container data for better performance
                try:
                    containers = container_data.get(resource_id, {"running_count": 0})
                    active_container_count = int(containers.get("running_count", 0))
                    logger.info(f"Resource {resource_id}: running_containers={active_container_count}")
                except Exception as e:
                    logger.warning(f"Error getting container data for resource {resource_id}: {e}, defaulting to 0")
                    active_container_count = 0

                # Calculate uptime multiplier based on current uptime (fallback to historical if available)
                try:
                    from neurons.utils.uptimedata import calculate_historical_uptime
                    historical_uptime = calculate_historical_uptime(resource_id, current_block)
                    uptime_multiplier = calculate_uptime_multiplier(historical_uptime)
                except ImportError:
                    # Fallback to current uptime if historical function not available
                    uptime_multiplier = calculate_uptime_multiplier(uptime_percent)
                    logger.debug(f"Using current uptime {uptime_percent}% for multiplier calculation (historical function not available)")
                
                # Calculate rented machine bonus for machines with running containers
                rented_machine_bonus = calculate_rented_machine_bonus(active_container_count)
                
                # Calculate fair resource score using new balanced formula with graceful error handling
                try:
                    resource_score = calculate_fair_resource_score(
                        uptime_percent=uptime_percent,
                        scaled_compute_score=compute_score,
                        active_container_count=active_container_count,
                        tempo=tempo,
                        uptime_multiplier=uptime_multiplier,
                        rented_machine_bonus=rented_machine_bonus
                    )
                    
                    # Add score to raw results (NO uptime rewards added to prevent double counting)
                    raw_results[miner_id]["total_raw_score"] += resource_score
                    
                    # Track CPU vs GPU scores separately
                    if resource_type == "CPU":
                        raw_results[miner_id]["cpu_score"] += resource_score
                        logger.info(f"Resource {resource_id}: Added {resource_score:.2f} to CPU score")
                    elif resource_type == "GPU":
                        raw_results[miner_id]["gpu_score"] += resource_score
                        logger.info(f"Resource {resource_id}: Added {resource_score:.2f} to GPU score")
                    else:
                        # Unknown type - treat as GPU for safety
                        raw_results[miner_id]["gpu_score"] += resource_score
                        logger.warning(f"Resource {resource_id}: Unknown type, treating as GPU")
                    
                    # Log comprehensive scoring details
                    log_resource_scoring_details(
                        resource_id=resource_id,
                        miner_id=miner_id,
                        pog_score=pog_score,
                        scaled_compute_score=compute_score,
                        uptime_percent=uptime_percent,
                        active_container_count=active_container_count,
                        uptime_multiplier=uptime_multiplier,
                        rented_machine_bonus=rented_machine_bonus,
                        final_score=resource_score,
                        tempo=tempo
                    )
                except Exception as e:
                    logger.warning(f"Error calculating resource score for {resource_id}: {e}")
                    # Use fallback calculation if the main function fails
                    fallback_score = (uptime_percent / 100) * 40 + compute_score * 0.4 + min(active_container_count, MAX_CONTAINERS) * 0.2
                    fallback_score = fallback_score * (tempo / 3600) * uptime_multiplier * rented_machine_bonus
                    raw_results[miner_id]["total_raw_score"] += fallback_score
                    
                    # Track fallback scores by type
                    if resource_type == "CPU":
                        raw_results[miner_id]["cpu_score"] += fallback_score
                    elif resource_type == "GPU":
                        raw_results[miner_id]["gpu_score"] += fallback_score
                    else:
                        raw_results[miner_id]["gpu_score"] += fallback_score
                    
                    logger.info(f"Resource {resource_id}: fallback_score={fallback_score:.2f}")

        # Implement optimized score normalization with better distribution
        if raw_results:
            raw_scores = [entry["total_raw_score"] for entry in raw_results.values()]
            if raw_scores:
                # Use 75th percentile for normalization to prevent score compression
                if len(raw_scores) >= 5:
                    normalization_reference = np.percentile(raw_scores, 75)
                    logger.info(f"Using 75th percentile score {normalization_reference:.2f} for normalization")
                elif len(raw_scores) >= 3:
                    normalization_reference = np.percentile(raw_scores, 80)
                    logger.info(f"Using 80th percentile score {normalization_reference:.2f} for normalization")
                else:
                    normalization_reference = max(raw_scores)
                    logger.info(f"Using max score {normalization_reference:.2f} for normalization (insufficient data for percentile)")
                
                if normalization_reference > 0:
                    # Apply logarithmic scaling for better score distribution
                    normalization_factor = MAX_SCORE / (normalization_reference * np.log1p(1))
                    logger.info(f"Optimized normalization factor: {normalization_factor:.4f}")
                    
                    for miner_id, entry in raw_results.items():
                        raw_score = entry["total_raw_score"]
                        cpu_score = entry["cpu_score"]
                        gpu_score = entry["gpu_score"]
                        has_cpu = entry["has_cpu_resources"]
                        
                        if raw_score > 0:
                            # Use logarithmic scaling to prevent score compression
                            scaled_score = raw_score * np.log1p(normalization_factor)
                            # Apply soft cap with gradual falloff above 80% of MAX_SCORE
                            if scaled_score > MAX_SCORE * 0.8:
                                falloff_factor = 1.0 - ((scaled_score - MAX_SCORE * 0.8) / (MAX_SCORE * 0.2)) * 0.2
                                scaled_score = scaled_score * falloff_factor
                            
                            normalized_score = min(MAX_SCORE, max(0, scaled_score))
                            
                            # Normalize CPU and GPU scores proportionally
                            if cpu_score > 0:
                                normalized_cpu = (cpu_score / raw_score) * normalized_score
                            else:
                                normalized_cpu = 0.0
                            
                            if gpu_score > 0:
                                normalized_gpu = (gpu_score / raw_score) * normalized_score
                            else:
                                normalized_gpu = 0.0
                        else:
                            normalized_score = 0.0
                            normalized_cpu = 0.0
                            normalized_gpu = 0.0
                        
                        results[miner_id]["total_score"] = normalized_score
                        results[miner_id]["cpu_score"] = normalized_cpu
                        results[miner_id]["gpu_score"] = normalized_gpu
                        results[miner_id]["has_cpu_resources"] = has_cpu
                        
                        logger.info(
                            f"Miner ID {miner_id} (UID {entry['miner_uid']}): "
                            f"total={normalized_score:.2f} (CPU={normalized_cpu:.2f}, GPU={normalized_gpu:.2f}), "
                            f"has_cpu_resources={has_cpu}"
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

        # Apply Alpha-stake based bonuses with graceful error handling
        if results:
            try:
                # Sync metagraph to get current stake information
                _sync_metagraph(netuid, network)
                
                if _metagraph is not None:
                    # Build UID stake information dictionary
                    uid_stake_info = {}
                    for miner_id, result in results.items():
                        miner_uid = result.get("miner_uid")
                        if miner_uid:
                            try:
                                uid_int = int(miner_uid)
                                stake_info = get_uid_alpha_stake_info(uid_int, _metagraph)
                                if stake_info:
                                    uid_stake_info[str(uid_int)] = stake_info
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Invalid miner_uid format for {miner_id}: {e}")
                                continue
                    
                    # Apply Alpha-stake bonuses to normalized scores
                    if uid_stake_info:
                        try:
                            results = apply_alpha_stake_bonus_to_normalized_scores(results, uid_stake_info)
                            logger.info(f"Applied Alpha-stake bonuses to normalized scores for {len(uid_stake_info)} UIDs")
                            
                            # Generate comprehensive Alpha-stake bonus analysis report
                            try:
                                generate_alpha_stake_analysis_report(results, uid_stake_info)
                            except Exception as report_e:
                                logger.warning(f"Error generating Alpha-stake report: {report_e}")
                        except Exception as bonus_e:
                            logger.error(f"Error applying Alpha-stake bonuses to normalized scores: {bonus_e}")
                            # Continue with normalized results if bonus application fails
                    else:
                        logger.warning("No valid UID stake information found for bonus application")
                else:
                    logger.warning("Failed to sync metagraph for Alpha-stake bonus application")
            except Exception as e:
                logger.error(f"Error applying Alpha-stake bonuses to normalized scores: {e}")
                # Continue without bonuses if there's an error
        else:
            logger.info("No results to apply Alpha-stake bonuses to")

        logger.info(f"Processed {len(results)} unique miner IDs")
        
        # Analyze scoring fairness
        try:
            fairness_analysis = analyze_scoring_fairness(results)
            if "error" not in fairness_analysis:
                # Generate and log comprehensive report
                scoring_report = generate_scoring_report(results, fairness_analysis)
                logger.info(scoring_report)
                
                # Log key fairness metrics
                if "fairness_metrics" in fairness_analysis:
                    metrics = fairness_analysis["fairness_metrics"]
                    logger.info(f"🎯 Scoring Fairness Summary:")
                    
                    # Log score equality metrics
                    if "score_equality" in metrics:
                        score_equality = metrics["score_equality"]
                        logger.info(f"  Gini Coefficient: {score_equality.get('gini_coefficient', 0):.4f}")
                        logger.info(f"  Coefficient of Variation: {score_equality.get('coefficient_of_variation', 0):.4f}")
                    
                    # Log score distribution
                    if "score_distribution" in metrics:
                        score_dist = metrics["score_distribution"]
                        logger.info(f"  Score Range: {score_dist.get('min', 0):.2f} - {score_dist.get('max', 0):.2f}")
                        logger.info(f"  Mean Score: {score_dist.get('mean', 0):.2f}")
                    
                    # Log fairness assessment
                    if "fairness_assessment" in fairness_analysis:
                        assessment = fairness_analysis["fairness_assessment"]
                        logger.info(f"  System Fair: {'Yes' if assessment.get('is_fair', False) else 'No'}")
                        if assessment.get('issues'):
                            logger.info(f"  Issues: {', '.join(assessment['issues'])}")
        except Exception as e:
            logger.warning(f"Error analyzing scoring fairness: {e}")
        
        # Ensure we return the expected format for the validator
        if not results:
            logger.warning("No results generated, returning empty structures")
            return {}, {}
            
        return results, uptime_rewards_dict

    except Exception as e:
        logger.critical(f"Fatal error processing miners: {e}")
        logger.error(f"Stack trace: {e}", exc_info=True)
        
        # Return empty results instead of crashing
        logger.warning("Returning empty results due to error, continuing validator operation")
        return {}, {}



def update_miner_status(miner_id: str, status: str, percentage: float, reason: str) -> Optional[str]:
    """
    Updates a miner's full status using the new PUT endpoint.

    Args:
        miner_id: The ID of the miner to update.
        status: New status string (e.g. 'active', 'inactive').
        percentage: Completion or activity percentage.
        reason: Reason for the status change.

    Returns:
        The updated status from the server or None if failed.
    """
    headers = {
            "Connection": "keep-alive",
            "x-api-key": "",
            "service-key": "",
            "service-name": "miner_service",
            "Content-Type": "application/json"
        }
    updated_at = datetime.utcnow()
    url = f"https://femi-aristodemos.onrender.com/api/v1/services/miner/miners/{miner_id}"
    payload = {
        "status": status,
        "percentage": percentage,
        "reason": reason,
        "updated_at": updated_at.isoformat() + "Z"
    }

    try:
        response = requests.put(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Miner {miner_id} successfully updated to {status} ({percentage}%) - Reason: {reason}")
        return response.json().get("status", "unknown")
    except Exception as e:
        logger.error(f"Failed to update miner {miner_id}: {e}")
        return None


def get_containers_for_miner(miner_id: str) -> List[str]:
    try:
        headers = {
            "Connection": "keep-alive",
            "x-api-key": "",
            "service-key": " ",
            "service-name": "miner_service",
            "Content-Type": "application/json"
        }

        url = f"https://femi-aristodemos.onrender.com/api/v1/services/container/container/containers/miner/{miner_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("containers", [])
        

    except Exception as e:
        logger.error(f"Error fetching containers for miner {miner_id}: {e}")
        return []
    


def update_container_payment_status(container_id: str) -> bool:
    """
    Updates the payment status of a container to 'completed' via PUT request.

    Args:
        container_id (str): The ID of the container to update.

    Returns:
        bool: True if update was successful, False otherwise.
    """
    headers = {
            "Connection": "keep-alive",
            "x-api-key": "",
            "service-key": " ",
            "service-name": "miner_service",
            "Content-Type": "application/json"
        }

    url = f"https://femi-aristodemos.onrender.com/api/v1/services/container/container/containers/{container_id}"
    payload = {
        "fields": {
            "payment_status": "paid"
        }
    }

    try:
        response = requests.put(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"[{response.status_code}] Payment status updated for container {container_id}")
        return True

    except requests.exceptions.HTTPError as http_err:
        logger.error(f"HTTP error while updating container {container_id}: {http_err}")
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error while updating container {container_id}: {req_err}")
    except Exception as e:
        logger.error(f"Unexpected error while updating container {container_id}: {e}", exc_info=True)

    return False

def check_resource_unique(resource_id: str, miner_id: str) -> bool:
    """
    Checks if a resource's IP and port combination is unique across all resources of all miners.

    Args:
        resource_id (str): The ID of the resource to check.
        miner_id (str): The ID of the miner owning the resource.

    Returns:
        bool: True if the resource's IP and port combination is unique, False otherwise.
    """
    try:
        # Fetch cached miners data
        miners = _get_cached_miners_data()
        if not miners:
            logger.error(f"No miner data in cache for uniqueness check of resource {resource_id}")
            return False

        # Extract target resource's IP and port
        target_ip_port = None
        for miner in miners:
            miner_id_from_data = str(miner.get("miner_id") or miner.get("id"))
            if miner_id_from_data == str(miner_id):
                compute_details = miner.get("resource_details", [])
                for resource in compute_details:
                    if resource.get("id") == resource_id:
                        ssh = resource.get("network", {}).get("ssh")
                        if not ssh or not ssh.startswith("ssh://"):
                            logger.error(f"Resource {resource_id} has invalid or missing SSH format: {ssh}")
                            return False
                        try:
                            address = ssh.split("://")[1].split("@")[1]
                            ip, port = address.split(":")
                            target_ip_port = (ip, port)
                        except (IndexError, ValueError) as e:
                            logger.error(f"Error parsing SSH for resource {resource_id}: {ssh}, error: {e}")
                            return False
                        break
                break
        else:
            logger.error(f"Resource {resource_id} not found for miner {miner_id}")
            return False

        # Check uniqueness across all resources
        for miner in miners:
            compute_details = miner.get("compute_resources_details", [])
            miner_id_from_data = str(miner.get("miner_id") or miner.get("id"))
            for resource in compute_details:
                if resource.get("id") == resource_id and miner_id_from_data == str(miner_id):
                    continue  # Skip the target resource itself

                ssh = resource.get("network", {}).get("ssh")
                if not ssh or not ssh.startswith("ssh://"):
                    continue

                try:
                    address = ssh.split("://")[1].split("@")[1]
                    ip, port = address.split(":")
                    if (ip, port) == target_ip_port:
                        logger.info(
                            f"Resource {resource_id} of miner {miner_id} shares IP {ip} and port {port} "
                            f"with resource {resource.get('id')} of miner {miner_id_from_data}"
                        )
                        return False
                except (IndexError, ValueError):
                    continue

        logger.info(f"Resource {resource_id} of miner {miner_id} is unique with IP and port: {target_ip_port}")
        return True

    except Exception as e:
        logger.error(f"Error checking uniqueness for resource {resource_id} of miner {miner_id}: {e}")
        return False

def get_miners_compute_resources() -> dict[str, dict]:
    """
    Retrieves compute resources for all miners.
    
    Returns:
        dict: A dictionary mapping miner IDs to their compute resources.
    """
    try:
        # Get cached miners data
        miners = _get_cached_miners_data()

        # Construct dictionary of miner IDs to compute resources
        return {
            str(miner.get("miner_id") or miner.get("id")): miner.get('resource_details', [])
            for miner in miners
            if miner.get("miner_id") or miner.get("id")
        }

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
        miner_id_from_data = str(miner.get("miner_id") or miner.get("id"))
        if miner_id_from_data == str(miner_id):
            logger.info(f"Found miner {miner_id} in _miners_data_cache")
            return miner
    
    logger.warning(f"Miner {miner_id} not found in _miners_data_cache")
    return {}

def get_miner_uid_by_hotkey(hotkey: str, netuid: int, network: str = "finney", force_refresh: bool = False) -> Optional[int]:
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
    

# Global cache for containers data
_containers_cache = {}
_containers_cache_timestamp = 0
_containers_cache_interval = 300  # 5 minutes cache interval

def _sync_containers_data() -> None:
    """Fetches and caches containers data from the API."""
    global _containers_cache, _containers_cache_timestamp
    try:
        logger.info("🔄 CONTAINERS CACHE: Fetching fresh containers data from API...")
        
        # API endpoint - no headers needed as tested
        url = "https://polariscloudai-main-pf5lil.laravel.cloud/api/v1/validator/containers"
        
        # Send GET request without headers for better performance
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Parse and cache response
        data = response.json()
        _containers_cache = data.get("containers", [])
        _containers_cache_timestamp = time.time()
        
        logger.info(f"✅ CONTAINERS CACHE: Cached {len(_containers_cache)} containers successfully")
        
    except Exception as e:
        logger.error(f"❌ CONTAINERS CACHE: Error caching containers data: {e}")
        _containers_cache = []
        _containers_cache_timestamp = time.time()

def _get_cached_containers_data(force_refresh: bool = False) -> List[dict]:
    """Returns cached containers data, refreshing if necessary or forced."""
    global _containers_cache_timestamp
    current_time = time.time()
    time_since_last_fetch = current_time - _containers_cache_timestamp
    
    needs_refresh = force_refresh or time_since_last_fetch > _containers_cache_interval or not _containers_cache
    
    if needs_refresh:
        if force_refresh:
            logger.info("🔄 CONTAINERS CACHE: Force refresh - pulling latest data")
        elif time_since_last_fetch > _containers_cache_interval:
            logger.info(f"⏰ CONTAINERS CACHE: Cache expired - pulling latest data ({time_since_last_fetch:.1f}s ago)")
        elif not _containers_cache:
            logger.info("📭 CONTAINERS CACHE: Empty cache - pulling latest data")
        
        _sync_containers_data()
    else:
        logger.debug(f"📋 CONTAINERS CACHE: Using cached data ({len(_containers_cache)} containers, {time_since_last_fetch:.1f}s old)")
    
    return _containers_cache

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
            return {"running_count": 0}

        # Get cached containers data
        container_list = _get_cached_containers_data()
        
        # Filter containers by resource_id and count running ones
        matching_containers = [container for container in container_list if container.get("resource_id") == resource_id]
        running_count = sum(1 for container in matching_containers if container.get("status") == "running")

        logger.debug(f"Resource {resource_id}: {len(matching_containers)} containers, {running_count} running")

        return {
            "running_count": running_count
        }

    except Exception as e:
        logger.error(f"Error fetching containers for resource {resource_id}: {e}")
        return {"running_count": 0}

def get_containers_for_multiple_resources(resource_ids: List[str]) -> Dict[str, Dict[str, any]]:
    """
    Efficiently fetches container counts for multiple resources using a single API call.
    
    Args:
        resource_ids (List[str]): List of resource IDs to check.
        
    Returns:
        Dict[str, Dict[str, any]]: Dictionary mapping resource_id to container data.
    """
    try:
        # Get cached containers data once
        container_list = _get_cached_containers_data()
        
        # Process all resources in one pass
        results = {}
        for resource_id in resource_ids:
            if not resource_id or not isinstance(resource_id, str):
                results[resource_id] = {"running_count": 0}
                continue
                
            matching_containers = [container for container in container_list if container.get("resource_id") == resource_id]
            running_count = sum(1 for container in matching_containers if container.get("status") == "running")
            
            results[resource_id] = {"running_count": running_count}
        
        logger.debug(f"Processed {len(resource_ids)} resources with {len(container_list)} total containers")
        return results
        
    except Exception as e:
        logger.error(f"Error fetching containers for multiple resources: {e}")
        return {resource_id: {"running_count": 0} for resource_id in resource_ids}

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

def filter_miners_by_id(
    bittensor_miners: Dict[str, int],
    netuid: int = 100,
    network: str = "finney",
    hotkey_to_uid: Optional[Dict[str, int]] = None
) -> Dict[str, int]:
    """
    Keeps only miners from bittensor_miners whose IDs are in ids_to_keep and whose hotkey-derived UID matches the provided UID.

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

        ids_to_keep = list(bittensor_miners.keys())
        ids_to_keep_set = set(ids_to_keep)
        filtered_miners = {}

        # Use provided hotkey_to_uid cache or sync metagraph
        uid_cache = hotkey_to_uid if hotkey_to_uid is not None else _hotkey_to_uid_cache
        if not uid_cache or hotkey_to_uid is None:
            _sync_metagraph(netuid, network)
            uid_cache = _hotkey_to_uid_cache

        # Filter miners and verify hotkey-UID match
        for miner_id, uid in bittensor_miners.items():
            if miner_id not in ids_to_keep_set:
                logger.debug(f"Miner {miner_id} not in ids_to_keep, skipping")
                continue

            # Get miner details
            miner_details = get_miner_details(miner_id)
            hotkey = miner_details.get("bittensor_details", {}).get("hotkey")
            if not hotkey or hotkey == "default":
                logger.warning(f"Invalid or missing hotkey for miner {miner_id}, skipping")
                continue

            subnet_uid = get_miner_uid_by_hotkey(hotkey, netuid, network)
            if subnet_uid is None:
                logger.warning(f"Hotkey {hotkey} for miner {miner_id} not found on subnet {netuid}, skipping")
                continue

            # Ensure type consistency
            try:
                uid = int(uid)  # Convert uid to int
                subnet_uid = int(subnet_uid)  # Ensure subnet_uid is int
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid UID types for miner {miner_id}: uid={uid} (type={type(uid)}), subnet_uid={subnet_uid} (type={type(subnet_uid)}), error={e}")
                continue

            # Debug logging for UID comparison
            logger.debug(f"Comparing UIDs for miner {miner_id}: uid={uid} (type={type(uid)}), subnet_uid={subnet_uid} (type={type(subnet_uid)})")

            if subnet_uid == uid:
                filtered_miners[miner_id] = uid
                logger.info(f"Miner {miner_id} validated: UID {uid} matches subnet UID {subnet_uid}")
            else:
                logger.warning(f"Miner {miner_id} UID {uid} does not match subnet UID {subnet_uid}, skipping")

        removed_count = len(bittensor_miners) - len(filtered_miners)
        logger.info(f"Kept {len(filtered_miners)} miners; removed {removed_count} miners")
        return filtered_miners

    except Exception as e:
        logger.error(f"Error filtering miners: {e}")
        return {}
    

def update_miner_compute_resource(
    miner_id: str,
    resource_id: str,
    status:str,
    reason:str,
) -> Optional[dict]:
    
    try:
    
        # Construct the full URL
        url = f"https://femi-aristodemos.onrender.com/api/v1/services/miner/miners/{miner_id}"

        # Prepare headers
    
        # Prepare payload
        payload = {
            "compute_resource_updates": [
                {
                    "id": resource_id,
                    "validation_status":status,
                    "reason":reason
                }
            ]
        }

        # Send PUT request
        logger.info(f"Sending PUT request with payload: {payload}")
        response = requests.put(url, headers=headers, json=payload)

        # Check response status
        if response.status_code == 200:
            logger.info(f"Successfully updated compute resource {resource_id} for miner {miner_id}")
            return response.json()
        else:
            logger.error(f"Failed to update compute resource {resource_id} for miner {miner_id}. "
                        f"Status code: {response.status_code}, Response: {response.text}")
            return None

    except requests.RequestException as e:
        logger.error(f"Network error while updating compute resource {resource_id} for miner {miner_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error while updating compute resource {resource_id} for miner {miner_id}: {e}")
        return None


async def sub_verification(allowed_uids: List[int]) -> Tuple[Dict[str, int], Dict]:
    """
    Verifies miner compute resources for a given list of allowed UIDs.
    
    Args:
        allowed_uids: List of allowed miner UIDs to process
        
    Returns:
        Tuple containing:
        - hotkey_cache: Dictionary mapping miner hotkeys to UIDs
        - verification_results: Dictionary containing verification outcomes
    """
    # Initialize result dictionaries
    hotkey_cache: Dict[str, int] = {}
    verification_results: Dict = {}

    # Validate input
    if not allowed_uids:
        logger.warning("Received empty allowed_uids list")
        return hotkey_cache, verification_results

    try:
        # Fetch miner data with proper error handling
        try:
            miners =  _get_cached_miners_data()
        except Exception as e:
            logger.error(f"Failed to fetch miners data: {str(e)}", exc_info=True)
            return hotkey_cache, verification_results

        if not miners:
            logger.warning("No miners data available in cache")
            return hotkey_cache, verification_results

        logger.info(f"Processing {len(miners)} miners for verification")

        async def process_miner(miner: Dict) -> None:
            """Process individual miner and their compute resources."""
            try:
                # Validate miner data
                miner_id_from_data = str(miner.get("miner_id") or miner.get("id") or "unknown")
                if not (bittensor_reg := miner.get("bittensor_details")):
                    logger.warning(f"Skipping miner {miner_id_from_data}: No bittensor registration")
                    return

                miner_uid = bittensor_reg.get("miner_uid")
                if miner_uid is None or int(miner_uid) not in allowed_uids:
                    logger.debug(f"Skipping miner {miner_id_from_data}: UID {miner_uid} not in allowed list")
                    return

                miner_uid = int(miner_uid)
                # Handle both "miner_id" and "id" fields, ensure string type
                miner_id_raw = miner.get("miner_id") or miner.get("id")
                miner_id = str(miner_id_raw) if miner_id_raw is not None else "unknown"
                hotkey_cache[miner_id] = miner_uid
                logger.info(f"Processing miner {miner_id} (UID: {miner_uid})")

                # Process compute resources
                compute_details = miner.get("resource_details", [])
                if not compute_details:
                    logger.info(f"Miner {miner_id} has no compute resources")
                    return
                logger.info(f"Miner {miner_id} has {len(compute_details)} compute resource(s)")

                async def process_resource(resource: Dict, idx: int) -> Tuple[str, float] | None:
                    """Process individual compute resource."""
                    try:
                        resource_id = resource.get("id", f"unknown_{idx}")
                        validation_status = resource.get("validation_status")

                        if validation_status == "verified":
                            logger.debug(f"Resource {resource_id} already verified, skipping")
                            return None
                        
                        # Check resource uniqueness
                        if not check_resource_unique(resource_id, miner_id):
                            logger.warning(f"Resource {resource_id} of miner {miner_id} is not unique. Skipping.")
                            return None

                        logger.info(f"Processing resource {idx} (ID: {resource_id})")
                        # Check monitoring_status fields
                        monitoring_status = resource.get("monitoring_status", {})
                        conn_status = monitoring_status.get("conn", {}).get("status")
                        auth_status = monitoring_status.get("auth", {}).get("status")
                        docker_running = monitoring_status.get("docker", {}).get("running")
                        docker_user_group = monitoring_status.get("docker", {}).get("user_group")

                        if (
                            conn_status != "ok" or
                            auth_status != "ok" 
                        ):
                            logger.info(
                                f"Resource {resource_id} failed monitoring checks: "
                                f"conn_status={conn_status}, auth_status={auth_status}, "
                                f"docker_running={docker_running}, docker_user_group={docker_user_group}"
                            )
                            return None

                        logger.info(f"Processing resource {idx} (ID: {resource_id})")

                        # Use pow total as pog_score
                        pog_score = monitoring_status.get("pow", {}).get("total", 0.0)
                        logger.info(f"Resource {resource_id}: compute_score={pog_score:.4f}")

                        return resource_id, pog_score

                    except (OSError, asyncio.TimeoutError) as e:
                        logger.error(f"Error processing resource {resource_id}: {str(e)}", exc_info=True)
                        return None
                    except Exception as e:
                        logger.error(f"Unexpected error processing resource {resource_id}: {str(e)}", exc_info=True)
                        return None

                # Process resources concurrently
                tasks = [process_resource(resource, idx) for idx, resource in enumerate(compute_details, 1)]
                task_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Filter out None results and exceptions
                resource_results = []
                for result in task_results:
                    if isinstance(result, Exception):
                        logger.error(f"Resource processing task failed with exception: {result}")
                        continue
                    if result is not None:
                        resource_results.append(result)

                # Update verification results
                for resource_id, pog_score in resource_results:
                    # Skip resources with POW scores above maximum allowed
                    if pog_score > MAX_POW_SCORE:
                        logger.warning(f"Resource {resource_id}: POW score={pog_score:.4f} exceeds maximum {MAX_POW_SCORE} - SKIPPING VERIFICATION")
                        continue
                    
                    try:
                        status = "verified" if pog_score >= SCORE_THRESHOLD else "rejected"
                        reason = (f"Verified with score: {pog_score:.4f}" if status == "verified" 
                                else f"Low compute score: {pog_score:.4f}")
                        
                        update_result = update_miner_compute_resource(
                            miner_id=miner_id,
                            resource_id=resource_id,
                            status=status,
                            reason=reason
                        )
                        
                        if not update_result:
                            logger.warning(f"Failed to update status for resource {resource_id}")
                        
                        verification_results[f"{miner_id}_{resource_id}"] = {
                            "status": status,
                            "score": pog_score,
                            "reason": reason
                        }
                        
                    except Exception as e:
                        logger.error(f"Error updating resource {resource_id} for miner {miner_id}: {str(e)}", 
                                   exc_info=True)

            except Exception as e:
                logger.error(f"Error processing miner {miner_id_from_data}: {str(e)}", exc_info=True)

        # Process miners concurrently
        await asyncio.gather(*[process_miner(miner) for miner in miners], return_exceptions=True)
        
        return verification_results

    except Exception as e:
        logger.error(f"Unexpected error in sub_verification: {str(e)}", exc_info=True)
        return verification_results


def analyze_alpha_stake_distribution(metagraph) -> Dict:
    """
    Analyzes the distribution of Alpha stakes across all miners in the metagraph.
    
    Args:
        metagraph: The Bittensor metagraph object containing neuron information.
        
    Returns:
        Dict containing:
            - total_miners: Total number of miners
            - stake_tiers: Count of miners in each tier (high, medium, low)
            - total_alpha_staked: Total Alpha tokens staked across all miners
            - average_stake: Average Alpha stake per miner
            - tier_breakdown: Detailed breakdown of each tier
    """
    try:
        if not metagraph or not hasattr(metagraph, 'neurons'):
            logger.error("Invalid metagraph provided for analysis")
            return {}
        
        total_miners = len(metagraph.neurons)
        if total_miners == 0:
            logger.warning("No neurons found in metagraph")
            return {"total_miners": 0, "stake_tiers": {}, "total_alpha_staked": 0, "average_stake": 0}
        
        stake_tiers = {"high": 0, "medium": 0, "low": 0}
        total_alpha_staked = 0
        tier_breakdown = {"high": [], "medium": [], "low": []}
        
        for uid, neuron in enumerate(metagraph.neurons):
            if neuron.is_null:
                continue
                
            total_stake = safe_convert_to_float(neuron.total_stake, 0.0)
            total_alpha_staked += total_stake
            
            # Classify into tiers
            if total_stake >= ALPHA_STAKE_TIERS["high"]["threshold"]:
                stake_tiers["high"] += 1
                tier_breakdown["high"].append({"uid": uid, "stake": total_stake, "hotkey": neuron.hotkey})
            elif total_stake >= ALPHA_STAKE_TIERS["medium"]["threshold"]:
                stake_tiers["medium"] += 1
                tier_breakdown["medium"].append({"uid": uid, "stake": total_stake, "hotkey": neuron.hotkey})
            else:
                stake_tiers["low"] += 1
                tier_breakdown["low"].append({"uid": uid, "stake": total_stake, "hotkey": neuron.hotkey})
        
        average_stake = total_alpha_staked / total_miners if total_miners > 0 else 0
        
        result = {
            "total_miners": total_miners,
            "stake_tiers": stake_tiers,
            "total_alpha_staked": total_alpha_staked,
            "average_stake": average_stake,
            "tier_breakdown": tier_breakdown
        }
        
        logger.info(f"Alpha stake analysis: {stake_tiers['high']} high-tier, {stake_tiers['medium']} medium-tier, "
                   f"{stake_tiers['low']} low-tier miners. Total staked: {total_alpha_staked:.2f} Alpha")
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing Alpha stake distribution: {e}")
        return {}


def get_uid_alpha_stake_info(uid: int, metagraph) -> Dict:
    """
    Retrieves comprehensive Alpha stake information for a specific UID from the metagraph.
    
    Args:
        uid: The UID to query
        metagraph: The Bittensor metagraph object
        
    Returns:
        Dict containing:
            - uid: The miner's UID
            - total_stake: Total Alpha tokens staked
            - emission: Current emission rate
            - rank: Current rank
            - trust: Current trust score
            - hotkey: Miner's hotkey
            - coldkey: Miner's coldkey
            - stake_tier: Classification tier (high, medium, low)
            - bonus_percentage: Applicable bonus percentage
            - stake_details: Detailed stake breakdown
    """
    try:
        if not metagraph or not hasattr(metagraph, 'neurons'):
            logger.error("Invalid metagraph provided for UID stake info")
            return {}
        
        if uid >= len(metagraph.neurons):
            logger.error(f"UID {uid} out of range for metagraph with {len(metagraph.neurons)} neurons")
            return {}
        
        neuron = metagraph.neurons[uid]
        if neuron.is_null:
            logger.warning(f"UID {uid} is null/inactive")
            return {}
        
        # Handle Bittensor Balance objects properly using utility function
        total_stake = safe_convert_to_float(neuron.total_stake, 0.0)
        emission = safe_convert_to_float(neuron.emission, 0.0)
        rank = safe_convert_to_float(neuron.rank, 0.0)
        trust = safe_convert_to_float(neuron.trust, 0.0)
            
        hotkey = neuron.hotkey
        coldkey = neuron.coldkey
        
        # Determine stake tier and bonus
        stake_tier = "low"
        bonus_percentage = ALPHA_STAKE_TIERS["low"]["bonus_percentage"]
        
        if total_stake >= ALPHA_STAKE_TIERS["high"]["threshold"]:
            stake_tier = "high"
            bonus_percentage = ALPHA_STAKE_TIERS["high"]["bonus_percentage"]
        elif total_stake >= ALPHA_STAKE_TIERS["medium"]["threshold"]:
            stake_tier = "medium"
            bonus_percentage = ALPHA_STAKE_TIERS["medium"]["bonus_percentage"]
        
        # Extract stake details - handle Bittensor Balance objects properly
        stake_details = {}
        if hasattr(neuron, 'stake') and neuron.stake:
            try:
                # Handle different stake object types
                if hasattr(neuron.stake, 'items'):
                    # If stake is a dict-like object
                    for coldkey_addr, amount in neuron.stake.items():
                        stake_details[coldkey_addr] = float(amount) if hasattr(amount, '__float__') else amount
                elif hasattr(neuron.stake, '__getitem__'):
                    # If stake supports indexing
                    for i in range(len(neuron.stake)):
                        key = f"stake_{i}"
                        value = neuron.stake[i]
                        stake_details[key] = float(value) if hasattr(value, '__float__') else value
                else:
                    # If stake is a single value
                    stake_details["total"] = float(neuron.stake) if hasattr(neuron.stake, '__float__') else neuron.stake
            except Exception as e:
                logger.warning(f"Error extracting stake details for UID {uid}: {e}")
                stake_details["error"] = str(e)
        
        result = {
            "uid": uid,
            "total_stake": total_stake,
            "emission": emission,
            "rank": rank,
            "trust": trust,
            "hotkey": hotkey,
            "coldkey": coldkey,
            "stake_tier": stake_tier,
            "bonus_percentage": bonus_percentage,
            "stake_details": stake_details
        }
        
        # Safe formatting for logging
        try:
            stake_display = f"{total_stake:.2f}" if isinstance(total_stake, (int, float)) else str(total_stake)
            logger.debug(f"UID {uid} stake info: {stake_display} Alpha, tier: {stake_tier}, bonus: {bonus_percentage}%")
        except Exception as e:
            logger.debug(f"UID {uid} stake info: {total_stake} Alpha, tier: {stake_tier}, bonus: {bonus_percentage}%")
        return result
        
    except Exception as e:
        logger.error(f"Error retrieving Alpha stake info for UID {uid}: {e}")
        # Return minimal info to prevent complete failure
        return {
            "uid": uid,
            "total_stake": 0.0,
            "emission": 0.0,
            "rank": 0.0,
            "trust": 0.0,
            "hotkey": "unknown",
            "coldkey": "unknown",
            "stake_tier": "low",
            "bonus_percentage": 0,
            "stake_details": {"error": str(e)}
        }


def apply_alpha_stake_bonus(rewards: Dict, uid_stake_info: Dict) -> Dict:
    """
    Applies Alpha stake-based bonuses to miner rewards.
    
    Args:
        rewards: Dictionary of miner rewards with 'miner_uid' field
        uid_stake_info: Dictionary mapping UIDs to their stake information
        
    Returns:
        Updated rewards dictionary with applied bonuses and bonus metadata
    """
    try:
        if not rewards:
            logger.warning("No rewards provided for Alpha stake bonus application")
            return rewards
        
        if not uid_stake_info:
            logger.warning("No UID stake information provided, returning original rewards")
            return rewards
        
        updated_rewards = {}
        
        for miner_id, reward_data in rewards.items():
            miner_uid = reward_data.get("miner_uid")
            if not miner_uid:
                logger.warning(f"Miner {miner_id} missing miner_uid, skipping bonus")
                updated_rewards[miner_id] = reward_data
                continue
            
            # Convert miner_uid to string for dictionary lookup if needed
            uid_key = str(miner_uid) if isinstance(miner_uid, (int, str)) else miner_uid
            
            if uid_key not in uid_stake_info:
                logger.debug(f"No stake info for UID {uid_key}, no bonus applied")
                updated_rewards[miner_id] = reward_data
                continue
            
            stake_info = uid_stake_info[uid_key]
            bonus_percentage = stake_info.get("bonus_percentage", 0)
            total_stake = stake_info.get("total_stake", 0)
            stake_tier = stake_info.get("stake_tier", "low")
            
            if bonus_percentage > 0:
                # Apply bonus to total_score
                original_score = reward_data.get("total_score", 0)
                
                # If miner has no score but has sufficient stake, give minimum participation score
                if original_score == 0.0:
                    min_score = 10.0  # Minimum participation score for staked miners
                    original_score = min_score
                    logger.info(f"🎁 Gave minimum score {min_score} to staked miner {miner_id} "
                               f"(UID {uid_key}) with {bonus_percentage}% bonus")
                
                bonus_multiplier = 1 + (bonus_percentage / 100)
                new_score = original_score * bonus_multiplier
                
                # Create updated reward data
                updated_reward = reward_data.copy()
                updated_reward["total_score"] = new_score
                updated_reward["alpha_stake_bonus"] = {
                    "bonus_percentage": bonus_percentage,
                    "stake_amount": total_stake,
                    "stake_tier": stake_tier,
                    "original_score": original_score,
                    "bonus_amount": new_score - original_score,
                    "bonus_multiplier": bonus_multiplier,
                    "minimum_score_given": original_score > 0 and reward_data.get("total_score", 0) == 0
                }
                
                updated_rewards[miner_id] = updated_reward
                logger.info(f"💰 BONUS APPLIED: Miner {miner_id} (UID {uid_key})")
                logger.info(f"   Alpha Stake: {total_stake:.2f} → Tier: {stake_tier}")
                logger.info(f"   Bonus: {bonus_percentage}% → Multiplier: {bonus_multiplier:.3f}")
                logger.info(f"   Score: {original_score:.2f} → {new_score:.2f} (+{new_score - original_score:.2f})")
                logger.info(f"   Bonus Amount: +{new_score - original_score:.2f}")
                if original_score > 0 and reward_data.get("total_score", 0) == 0:
                    logger.info(f"   🎁 Minimum participation score given due to stake")
            else:
                # No bonus, keep original
                updated_rewards[miner_id] = reward_data
        
        total_bonuses = sum(1 for r in updated_rewards.values() if "alpha_stake_bonus" in r)
        logger.info(f"Applied Alpha stake bonuses to {total_bonuses} out of {len(rewards)} miners")
        
        return updated_rewards
        
    except Exception as e:
        logger.error(f"Error applying Alpha stake bonuses: {e}")
        return rewards


def get_metagraph_alpha_stake_summary(netuid: int = 49, network: str = "finney") -> Dict:
    """
    Gets a summary of Alpha stake distribution for a specific subnet.
    
    Args:
        netuid: The subnet ID (default: 49)
        network: The Bittensor network (default: "finney")
        
    Returns:
        Dictionary containing Alpha stake summary and distribution analysis
    """
    try:
        # Sync metagraph if needed
        _sync_metagraph(netuid, network)
        
        if _metagraph is None:
            logger.error("Failed to sync metagraph for Alpha stake summary")
            return {}
        
        # Analyze stake distribution
        stake_analysis = analyze_alpha_stake_distribution(_metagraph)
        
        # Get additional metadata
        summary = {
            "netuid": netuid,
            "network": network,
            "last_sync": _last_metagraph_sync,
            "cache_age_seconds": time.time() - _last_metagraph_sync,
            "total_nodes": len(_metagraph.hotkeys) if _metagraph.hotkeys else 0,
            **stake_analysis
        }
        
        logger.info(f"Alpha stake summary for subnet {netuid}: {stake_analysis.get('total_miners', 0)} miners, "
                   f"total staked: {stake_analysis.get('total_alpha_staked', 0):.2f} Alpha")
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting Alpha stake summary for subnet {netuid}: {e}")
        return {}


def generate_alpha_stake_analysis_report(results: Dict, uid_stake_info: Dict) -> None:
    """
    Generates and logs a comprehensive analysis report of Alpha-stake bonuses applied.
    
    Args:
        results: Dictionary of miner results after bonus application
        uid_stake_info: Dictionary mapping UIDs to their stake information
    """
    try:
        logger.info("=" * 80)
        logger.info("🎯 ALPHA-STAKE BONUS ANALYSIS REPORT")
        logger.info("=" * 80)
        
        # Initialize counters
        total_miners = len(results)
        miners_with_bonus = 0
        total_bonus_amount = 0.0
        tier_counts = {"high": 0, "medium": 0, "low": 0}
        total_alpha_staked = 0.0
        
        # Collect bonus details
        bonus_details = []
        
        for miner_id, result in results.items():
            miner_uid = result.get("miner_uid")
            if not miner_uid:
                continue
                
            uid_key = str(miner_uid)
            if uid_key in uid_stake_info:
                stake_info = uid_stake_info[uid_key]
                total_stake = stake_info.get("total_stake", 0)
                stake_tier = stake_info.get("stake_tier", "low")
                bonus_percentage = stake_info.get("bonus_percentage", 0)
                
                total_alpha_staked += total_stake
                tier_counts[stake_tier] += 1
                
                if "alpha_stake_bonus" in result:
                    miners_with_bonus += 1
                    bonus_info = result["alpha_stake_bonus"]
                    original_score = bonus_info.get("original_score", 0)
                    final_score = result.get("total_score", 0)
                    bonus_amount = bonus_info.get("bonus_amount", 0)
                    
                    total_bonus_amount += bonus_amount
                    
                    bonus_details.append({
                        "miner_id": miner_id,
                        "uid": uid_key,
                        "alpha_stake": total_stake,
                        "tier": stake_tier,
                        "bonus_percentage": bonus_percentage,
                        "original_score": original_score,
                        "final_score": final_score,
                        "bonus_amount": bonus_amount
                    })
                    
                    # Log individual bonus details
                    logger.info(f"💰 Miner {miner_id} (UID {uid_key}): "
                              f"Alpha Stake: {total_stake:.2f} → Tier: {stake_tier} → "
                              f"Bonus: {bonus_percentage}% → "
                              f"Score: {original_score:.2f} → {final_score:.2f} "
                              f"(+{bonus_amount:.2f})")
        
        # Generate summary statistics
        logger.info("-" * 80)
        logger.info("📊 SUMMARY STATISTICS")
        logger.info("-" * 80)
        logger.info(f"Total Miners Processed: {total_miners}")
        logger.info(f"Miners Receiving Bonuses: {miners_with_bonus}")
        logger.info(f"Miners Without Bonuses: {total_miners - miners_with_bonus}")
        logger.info(f"Bonus Success Rate: {(miners_with_bonus/total_miners*100):.1f}%")
        
        logger.info(f"\n🏆 STAKE TIER DISTRIBUTION:")
        logger.info(f"High Tier (≥5000 Alpha): {tier_counts['high']} miners")
        logger.info(f"Medium Tier (≥1000 Alpha): {tier_counts['medium']} miners")
        logger.info(f"Low Tier (<1000 Alpha): {tier_counts['low']} miners")
        
        logger.info(f"\n💎 ALPHA STAKE TOTALS:")
        logger.info(f"Total Alpha Staked: {total_alpha_staked:.2f}")
        logger.info(f"Average Alpha per Miner: {total_alpha_staked/total_miners:.2f}")
        
        logger.info(f"\n🎁 BONUS IMPACT:")
        logger.info(f"Total Bonus Amount Applied: {total_bonus_amount:.2f}")
        logger.info(f"Average Bonus per Eligible Miner: {total_bonus_amount/max(miners_with_bonus, 1):.2f}")
        
        # Top bonus recipients
        if bonus_details:
            logger.info(f"\n🏅 TOP 10 BONUS RECIPIENTS:")
            sorted_bonuses = sorted(bonus_details, key=lambda x: x["bonus_amount"], reverse=True)
            for i, detail in enumerate(sorted_bonuses[:10], 1):
                logger.info(f"{i:2d}. Miner {detail['miner_id']} (UID {detail['uid']}): "
                          f"Alpha: {detail['alpha_stake']:.2f}, "
                          f"Tier: {detail['tier']}, "
                          f"Bonus: {detail['bonus_percentage']}%, "
                          f"Score: {detail['original_score']:.2f} → {detail['final_score']:.2f} "
                          f"(+{detail['bonus_amount']:.2f})")
        
        logger.info("=" * 80)
        logger.info("📋 DETAILED BONUS BREAKDOWN BY TIER")
        logger.info("=" * 80)
        
        # Group by tier for detailed analysis
        tier_analysis = {"high": [], "medium": [], "low": []}
        for detail in bonus_details:
            tier_analysis[detail["tier"]].append(detail)
        
        for tier in ["high", "medium", "low"]:
            tier_details = tier_analysis[tier]
            if tier_details:
                logger.info(f"\n🔸 {tier.upper()} TIER ANALYSIS ({len(tier_details)} miners):")
                tier_bonus_total = sum(d["bonus_amount"] for d in tier_details)
                tier_alpha_total = sum(d["alpha_stake"] for d in tier_details)
                
                logger.info(f"   Total Alpha Staked: {tier_alpha_total:.2f}")
                logger.info(f"   Total Bonus Applied: {tier_bonus_total:.2f}")
                logger.info(f"   Average Bonus per Miner: {tier_bonus_total/len(tier_details):.2f}")
                
                # Show top 3 in this tier
                sorted_tier = sorted(tier_details, key=lambda x: x["bonus_amount"], reverse=True)
                for i, detail in enumerate(sorted_tier[:3], 1):
                    logger.info(f"   {i}. UID {detail['uid']}: Alpha {detail['alpha_stake']:.2f}, "
                              f"Bonus {detail['bonus_percentage']}%, Score +{detail['bonus_amount']:.2f}")
        
        logger.info("=" * 80)
        logger.info("✅ ALPHA-STAKE BONUS ANALYSIS COMPLETE")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Error generating Alpha-stake analysis report: {e}")
        logger.error("Continuing without detailed analysis report")
def apply_alpha_stake_bonus_to_normalized_scores(rewards: Dict, uid_stake_info: Dict) -> Dict:
    """
    Applies Alpha stake-based bonuses to ALREADY NORMALIZED miner scores.
    
    Args:
        rewards: Dictionary of miner rewards with normalized 'total_score' field
        uid_stake_info: Dictionary mapping UIDs to their stake information
        
    Returns:
        Updated rewards dictionary with applied bonuses to normalized scores
    """
    try:
        if not rewards:
            logger.warning("No rewards provided for Alpha stake bonus application")
            return rewards
        
        if not uid_stake_info:
            logger.warning("No UID stake information provided, returning original rewards")
            return rewards
        
        updated_rewards = {}
        
        for miner_id, reward_data in rewards.items():
            miner_uid = reward_data.get("miner_uid")
            if not miner_uid:
                logger.warning(f"Miner {miner_id} missing miner_uid, skipping bonus")
                updated_rewards[miner_id] = reward_data
                continue
            
            # Convert miner_uid to string for dictionary lookup if needed
            uid_key = str(miner_uid) if isinstance(miner_uid, (int, str)) else miner_uid
            
            if uid_key not in uid_stake_info:
                logger.debug(f"No stake info for UID {uid_key}, no bonus applied")
                updated_rewards[miner_id] = reward_data
                continue
            
            stake_info = uid_stake_info[uid_key]
            bonus_percentage = stake_info.get("bonus_percentage", 0)
            total_stake = stake_info.get("total_stake", 0)
            stake_tier = stake_info.get("stake_tier", "low")
            
            if bonus_percentage > 0:
                # Get the NORMALIZED score (already processed through normalization)
                normalized_score = reward_data.get("total_score", 0)
                
                # Apply bonus to normalized score
                bonus_multiplier = 1 + (bonus_percentage / 100)
                new_score = normalized_score * bonus_multiplier
                
                # Create updated reward data
                updated_reward = reward_data.copy()
                updated_reward["total_score"] = new_score
                updated_reward["alpha_stake_bonus"] = {
                    "bonus_percentage": bonus_percentage,
                    "stake_amount": total_stake,
                    "stake_tier": stake_tier,
                    "normalized_score": normalized_score,  # Store the normalized score
                    "bonus_amount": new_score - normalized_score,
                    "bonus_multiplier": bonus_multiplier,
                    "bonus_applied_to": "normalized_score"  # Indicate when bonus was applied
                }
                
                updated_rewards[miner_id] = updated_reward
                logger.info(f"💰 BONUS APPLIED TO NORMALIZED SCORE: Miner {miner_id} (UID {uid_key})")
                logger.info(f"   Alpha Stake: {total_stake:.2f} → Tier: {stake_tier}")
                logger.info(f"   Bonus: {bonus_percentage}% → Multiplier: {bonus_multiplier:.3f}")
                logger.info(f"   Normalized Score: {normalized_score:.2f} → {new_score:.2f} (+{new_score - normalized_score:.2f})")
                logger.info(f"   Bonus Amount: +{new_score - normalized_score:.2f}")
            else:
                # No bonus, keep original
                updated_rewards[miner_id] = reward_data
        
        total_bonuses = sum(1 for r in updated_rewards.values() if "alpha_stake_bonus" in r)
        logger.info(f"Applied Alpha stake bonuses to normalized scores for {total_bonuses} out of {len(rewards)} miners")
        
        return updated_rewards
        
    except Exception as e:
        logger.error(f"Error applying Alpha stake bonuses to normalized scores: {e}")
        return rewards


