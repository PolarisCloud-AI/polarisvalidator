"""
Alpha Over-Selling Detection System

This module implements a penalty system that detects and penalizes miners who are
over-selling their Alpha tokens (retaining <60% of earnings as stake).

Key Features:
- Uses only metagraph data (stake, emission, trust)
- Maintains automatic history of stake changes
- 60% minimum stake retention requirement
- 7-day analysis period
- Protection for new miners
- No manual storage updates - automatic tracking
"""

import time
import logging
import json
import os
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AlphaOverSellingDetector:
    """
    Detects and penalizes miners who are over-selling Alpha tokens.
    
    The system tracks stake changes over time using metagraph data and penalizes
    miners who retain less than 60% of their earnings as stake.
    """
    
    def __init__(self, netuid: int = 49, network: str = "finney"):
        self.netuid = netuid
        self.network = network
        
        # Configuration
        self.stake_decrease_threshold = 0.05  # 5% stake decrease threshold
        self.new_miner_protection_entries = 10  # Protect miners with <10 history entries (for moving average)
        
        # Block-based consensus configuration
        self.snapshot_interval_blocks = 720  # Take snapshot every 720 blocks (~20 hours at 100s/block)
        self.analysis_lookback_blocks = 7200  # Analyze last 7200 blocks (~20 days)
        self.min_snapshots_for_analysis = 10  # Need 10 snapshots minimum
        self.new_miner_protection_blocks = 7200  # Protect miners registered within last 7200 blocks
        
        # Penalty configuration based on stake decrease percentage
        self.penalty_levels = {
            'moderate': {
                'min_decrease': 0.05,    # 5-15% stake decrease
                'max_decrease': 0.15,
                'score_reduction': 0.20,
                'duration_hours': 6      # Reduced from 24 to 6 hours
            },
            'high': {
                'min_decrease': 0.15,    # 15-30% stake decrease
                'max_decrease': 0.30,
                'score_reduction': 0.40,
                'duration_hours': 12     # Reduced from 48 to 12 hours
            },
            'extreme': {
                'min_decrease': 0.30,    # >30% stake decrease
                'max_decrease': 1.00,
                'score_reduction': 0.60,
                'duration_hours': 24     # Reduced from 96 to 24 hours
            }
        }
        
        # History storage
        self.stake_history_file = f"logs/alpha_stake_history_{netuid}.json"
        self.stake_history: Dict[int, List[Dict]] = defaultdict(list)
        self.active_penalties: Dict[int, Dict] = {}
        self.last_analysis_time = 0
        
        # Load existing history
        self._load_stake_history()
        
        logger.info(f"Initialized AlphaOverSellingDetector for subnet {netuid}")
    
    def _load_stake_history(self):
        """Load existing stake history from file."""
        try:
            if os.path.exists(self.stake_history_file):
                with open(self.stake_history_file, 'r') as f:
                    data = json.load(f)
                    for uid_str, history in data.items():
                        uid = int(uid_str)
                        self.stake_history[uid] = history
                logger.info(f"Loaded stake history for {len(self.stake_history)} miners")
            else:
                logger.info("No existing stake history found, starting fresh")
        except Exception as e:
            logger.error(f"Error loading stake history: {e}")
            self.stake_history = defaultdict(list)
    
    def _save_stake_history(self):
        """Save stake history to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.stake_history_file), exist_ok=True)
            
            # Convert to serializable format
            data = {str(uid): history for uid, history in self.stake_history.items()}
            
            with open(self.stake_history_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved stake history for {len(self.stake_history)} miners")
        except Exception as e:
            logger.error(f"Error saving stake history: {e}")
    
    def _update_stake_history(self, metagraph):
        """
        Update stake history with current metagraph data using BLOCK-BASED snapshots.
        
        This creates consensus across validators:
        - All validators snapshot at same block intervals
        - Analysis uses same block ranges
        - Same blocks = same data = same penalties across all validators
        """
        try:
            current_time = time.time()
            current_block = metagraph.block.item() if hasattr(metagraph.block, 'item') else metagraph.block
            
            # Check if we should take a snapshot at this block
            # Only snapshot at specific block intervals for consensus
            should_snapshot = self._should_take_snapshot(current_block)
            
            for i, uid in enumerate(metagraph.uids):
                uid = int(uid)
                
                # Skip if not active
                if i >= len(metagraph.stake):
                    continue
                
                current_stake = float(metagraph.stake[i])
                current_emission = float(metagraph.emission[i])
                current_trust = float(metagraph.trust[i])
                
                # Check if this block already recorded (avoid duplicates)
                if self.stake_history[uid]:
                    last_recorded_block = self.stake_history[uid][-1].get('block', 0)
                    if current_block <= last_recorded_block:
                        continue  # Already have this or newer block
                
                # Add snapshot if at interval OR if we have no history
                if should_snapshot or len(self.stake_history[uid]) == 0:
                    history_entry = {
                        'timestamp': current_time,
                        'block': current_block,
                        'stake': current_stake,
                        'emission': current_emission,
                        'trust': current_trust
                    }
                    
                    self.stake_history[uid].append(history_entry)
                    logger.debug(f"UID {uid}: Snapshot at block {current_block}, stake={current_stake:.2f}")
                
                # BLOCK-BASED CLEANUP: Keep blocks within analysis window
                cutoff_block = current_block - self.analysis_lookback_blocks
                
                # Filter by block height (CONSENSUS METHOD)
                block_filtered = [
                    entry for entry in self.stake_history[uid] 
                    if entry['block'] > cutoff_block
                ]
                
                # Safety: Keep minimum snapshots for analysis
                if len(block_filtered) >= self.min_snapshots_for_analysis:
                    # We have enough snapshots in the block window
                    self.stake_history[uid] = block_filtered
                    logger.debug(f"UID {uid}: Kept {len(self.stake_history[uid])} snapshots (blocks {cutoff_block}-{current_block})")
                else:
                    # Not enough snapshots in window, keep minimum regardless of block age
                    self.stake_history[uid] = self.stake_history[uid][-self.min_snapshots_for_analysis:]
                    if self.stake_history[uid]:
                        oldest_block = self.stake_history[uid][0]['block']
                        logger.debug(f"UID {uid}: Kept {len(self.stake_history[uid])} snapshots (below minimum, oldest block: {oldest_block})")
            
            # Save history periodically (every 100 updates or 1 hour)
            if (len(self.stake_history) % 100 == 0 or 
                current_time - self.last_analysis_time > 3600):
                self._save_stake_history()
                self.last_analysis_time = current_time
            
        except Exception as e:
            logger.error(f"Error updating stake history: {e}")
    
    def _should_take_snapshot(self, current_block: int) -> bool:
        """
        Determine if we should take a snapshot at this block.
        
        Snapshots taken at fixed block intervals creates consensus:
        - All validators snapshot at blocks: 1000, 1720, 2440, etc.
        - Even if validators run at different times
        - They all analyze the same block snapshots
        
        Args:
            current_block: Current block height
            
        Returns:
            True if should take snapshot
        """
        # Snapshot at intervals (e.g., every 720 blocks)
        return current_block % self.snapshot_interval_blocks == 0
    
    def _detect_stake_decrement(self, uid: int, current_block: int = None) -> Optional[Dict]:
        """
        DYNAMIC ADAPTIVE stake decrement detection using block-based consensus.
        
        Key Features:
        - Uses ALL available data points (no waiting for 7 days)
        - Adapts thresholds based on data availability
        - Block-based for validator consensus
        - Scales with actual time span covered
        
        Args:
            uid: Miner UID
            current_block: Current block height (for block-based filtering)
            
        Returns:
            Dictionary with stake analysis or None if insufficient data
        """
        try:
            if uid not in self.stake_history:
                return None
            
            history = self.stake_history[uid]
            if len(history) < 3:  # Minimum 3 snapshots for any analysis
                return None
            
            # DYNAMIC DATA SELECTION: Use all available recent data
            if current_block is not None:
                # Prefer data within analysis window, but use all if needed
                analysis_start_block = current_block - self.analysis_lookback_blocks
                
                block_range_data = [
                    entry for entry in history 
                    if entry['block'] > analysis_start_block
                ]
                
                # Use block-filtered if we have at least 3, otherwise use all
                recent_data = block_range_data if len(block_range_data) >= 3 else history
            else:
                recent_data = history
            
            if len(recent_data) < 3:
                return None
            
            # ADAPTIVE MOVING AVERAGE: Use what's available
            # More data = better average, less data = still works but flagged
            ma_window = min(7, len(recent_data))  # Use up to 7 snapshots
            stake_values = [entry['stake'] for entry in recent_data[-ma_window:]]
            moving_avg_stake = sum(stake_values) / len(stake_values)
            
            emission_values = [entry['emission'] for entry in recent_data[-ma_window:]]
            moving_avg_emission = sum(emission_values) / len(emission_values)
            
            # Get initial and current for trend
            initial_stake = recent_data[0]['stake']
            current_stake = recent_data[-1]['stake']
            initial_block = recent_data[0]['block']
            final_block = recent_data[-1]['block']
            blocks_analyzed = final_block - initial_block
            
            # DYNAMIC TIME-ADJUSTED THRESHOLDS
            # Scale thresholds based on time span
            # Longer span = more lenient (natural growth/shrinkage)
            # Shorter span = stricter (rapid dumps)
            
            blocks_per_day = 864  # ~864 blocks per day (100s per block)
            days_analyzed = blocks_analyzed / blocks_per_day if blocks_analyzed > 0 else 0
            
            # Adaptive threshold calculation
            if days_analyzed >= 7:
                # Long period: Use base threshold
                threshold_multiplier = 1.0
            elif days_analyzed >= 3:
                # Medium period: Slightly more strict
                threshold_multiplier = 0.85
            elif days_analyzed >= 1:
                # Short period: More strict for rapid dumps
                threshold_multiplier = 0.70
            else:
                # Very short: Strictest for flash dumps
                threshold_multiplier = 0.50
            
            adaptive_threshold = 5.0 * threshold_multiplier  # Base 5%
            adaptive_ma_threshold = 3.0 * threshold_multiplier  # Base 3%
            
            # Calculate stake change
            stake_change = current_stake - initial_stake
            stake_change_percent = (stake_change / initial_stake) * 100 if initial_stake > 0 else 0
            
            # Moving average trend
            moving_avg_change = current_stake - moving_avg_stake
            moving_avg_change_percent = (moving_avg_change / moving_avg_stake) * 100 if moving_avg_stake > 0 else 0
            
            # ADAPTIVE OVERSELLING DETECTION
            # Uses dynamic thresholds based on data available
            is_overselling = (
                stake_change < 0 and 
                abs(stake_change_percent) > adaptive_threshold and  # Adaptive threshold
                moving_avg_change_percent < -adaptive_ma_threshold  # Adaptive MA threshold
            )
            
            return {
                'initial_stake': initial_stake,
                'current_stake': current_stake,
                'moving_avg_stake': moving_avg_stake,
                'stake_change': stake_change,
                'stake_change_percent': stake_change_percent,
                'moving_avg_change': moving_avg_change,
                'moving_avg_change_percent': moving_avg_change_percent,
                'avg_emission': moving_avg_emission,
                'is_overselling': is_overselling,
                'data_points': len(recent_data),
                'blocks_analyzed': blocks_analyzed,
                'initial_block': initial_block,
                'final_block': final_block,
                'days_analyzed': days_analyzed,
                'adaptive_threshold': adaptive_threshold,
                'adaptive_ma_threshold': adaptive_ma_threshold,
                'ma_window': ma_window
            }
            
        except Exception as e:
            logger.error(f"Error detecting stake decrement for UID {uid}: {e}")
            return None
    
    def _is_new_miner(self, uid: int, current_block: int = None) -> bool:
        """
        DYNAMIC new miner protection using block-based consensus.
        
        Adaptive Protection:
        - Uses available data points (minimum 3 required for penalty)
        - Block-based for cross-validator consensus
        - Protects miners without sufficient data history
        
        Args:
            uid: Miner UID
            current_block: Current block height (for block-based protection)
            
        Returns:
            True if miner is new and protected
        """
        try:
            if uid not in self.stake_history:
                return True
            
            history = self.stake_history[uid]
            if not history:
                return True
            
            # ADAPTIVE PROTECTION: Need minimum data points for reliable analysis
            # Reduced from 10 to 5 for faster penalty activation
            MIN_SNAPSHOTS_FOR_PENALTY = 5
            
            if len(history) < MIN_SNAPSHOTS_FOR_PENALTY:
                logger.debug(f"UID {uid}: Protected (only {len(history)} snapshots, need {MIN_SNAPSHOTS_FOR_PENALTY})")
                return True
            
            # BLOCK-BASED PROTECTION: Minimum time since first snapshot
            # Ensures miner has been around long enough for meaningful analysis
            if current_block is not None and len(history) > 0:
                first_snapshot_block = history[0]['block']
                blocks_since_first = current_block - first_snapshot_block
                
                # Minimum 2 days of history (1728 blocks)
                MIN_BLOCKS_FOR_PENALTY = 1728  # ~2 days
                
                if blocks_since_first < MIN_BLOCKS_FOR_PENALTY:
                    logger.debug(f"UID {uid}: Protected (only {blocks_since_first} blocks since first, need {MIN_BLOCKS_FOR_PENALTY})")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking if UID {uid} is new miner: {e}")
            return True  # Default to protecting miner on error
    
    def detect_overselling_violations(self, metagraph) -> List[Dict]:
        """
        Detect miners who are over-selling Alpha tokens using BLOCK-BASED consensus.
        
        Args:
            metagraph: Current metagraph data
            
        Returns:
            List of violation dictionaries
        """
        try:
            # Get current block for block-based analysis
            current_block = metagraph.block.item() if hasattr(metagraph.block, 'item') else metagraph.block
            
            # Update stake history with current data
            self._update_stake_history(metagraph)
            
            violations = []
            
            logger.info(f"🔍 Analyzing stake changes at block {current_block}")
            logger.info(f"   Analysis window: blocks {current_block - self.analysis_lookback_blocks} to {current_block}")
            logger.info(f"   Snapshot interval: every {self.snapshot_interval_blocks} blocks")
            logger.info(f"   Min snapshots required: {self.min_snapshots_for_analysis}")
            logger.info(f"   Total miners in metagraph: {len(metagraph.uids)}")
            logger.info(f"   Miners with stake history: {len(self.stake_history)}")
            
            for i, uid in enumerate(metagraph.uids):
                uid = int(uid)
                
                # Skip if not active
                if i >= len(metagraph.stake):
                    continue
                
                # Skip new miners (protection) - BLOCK-BASED
                if self._is_new_miner(uid, current_block):
                    continue
                
                # Detect stake decrement with BLOCK-BASED analysis
                stake_analysis = self._detect_stake_decrement(uid, current_block)
                if stake_analysis is None:
                    # Debug: Show why analysis was skipped
                    history_count = len(self.stake_history.get(uid, []))
                    if history_count < self.min_snapshots_for_analysis:
                        logger.debug(f"   UID {uid}: Skipped - insufficient data ({history_count}/{self.min_snapshots_for_analysis} snapshots)")
                    continue
                
                # Check for over-selling (stake decrease > threshold)
                if stake_analysis['is_overselling']:
                    # Determine penalty level based on stake decrease percentage
                    penalty_level = None
                    decrease_percent = abs(stake_analysis['stake_change_percent']) / 100
                    
                    for level, config in self.penalty_levels.items():
                        if config['min_decrease'] <= decrease_percent <= config['max_decrease']:
                            penalty_level = level
                            break
                    
                    if penalty_level:
                        violations.append({
                            'uid': uid,
                            'violation_type': 'alpha_overselling',
                            'penalty_level': penalty_level,
                            'stake_change_percent': stake_analysis['stake_change_percent'],
                            'stake_change': stake_analysis['stake_change'],
                            'initial_stake': stake_analysis['initial_stake'],
                            'current_stake': stake_analysis['current_stake'],
                            'avg_emission': stake_analysis['avg_emission'],
                            'data_points': stake_analysis['data_points'],
                            'blocks_analyzed': stake_analysis['blocks_analyzed'],
                            'initial_block': stake_analysis['initial_block'],
                            'final_block': stake_analysis['final_block'],
                            'moving_avg_change_percent': stake_analysis['moving_avg_change_percent']
                        })
            
            if violations:
                logger.warning(f"🚨 ALPHA OVER-SELLING DETECTED: {len(violations)} violations found")
                for violation in violations:
                    logger.warning(f"   UID {violation['uid']}: {violation['penalty_level']} violation "
                                 f"(stake decrease: {violation['stake_change_percent']:.1f}%, "
                                 f"moving avg deviation: {violation['moving_avg_change_percent']:.1f}%, "
                                 f"stake change: {violation['stake_change']:+.2f})")
            else:
                logger.info("✅ No alpha over-selling violations detected")
                # Debug: Show analysis summary
                analyzed_count = 0
                for uid in self.stake_history.keys():
                    if len(self.stake_history[uid]) >= self.min_snapshots_for_analysis:
                        analyzed_count += 1
                logger.info(f"   Miners analyzed: {analyzed_count}/{len(self.stake_history)}")
                logger.info(f"   Miners with sufficient data: {analyzed_count}")
            
            return violations
            
        except Exception as e:
            logger.error(f"Error detecting over-selling violations: {e}")
            return []
    
    def apply_penalties(self, violations: List[Dict], current_block: int) -> Dict[int, Dict]:
        """
        Apply penalties to over-selling miners.
        
        Args:
            violations: List of violation dictionaries
            current_block: Current block number
            
        Returns:
            Dictionary of applied penalties
        """
        try:
            applied_penalties = {}
            
            for violation in violations:
                uid = violation['uid']
                penalty_level = violation['penalty_level']
                config = self.penalty_levels[penalty_level]
                
                # Calculate penalty duration in blocks (assuming ~100 second blocks)
                duration_hours = config['duration_hours']
                duration_blocks = int(duration_hours * 36)  # ~36 blocks per hour
                
                penalty_info = {
                    'uid': uid,
                    'violation_type': 'alpha_overselling',
                    'penalty_level': penalty_level,
                    'score_reduction': config['score_reduction'],
                    'duration_hours': duration_hours,
                    'duration_blocks': duration_blocks,
                    'start_block': current_block,
                    'end_block': current_block + duration_blocks,
                    'stake_change_percent': violation['stake_change_percent'],
                    'stake_change': violation['stake_change'],
                    'initial_stake': violation['initial_stake'],
                    'current_stake': violation['current_stake'],
                    'applied_at': time.time()
                }
                
                self.active_penalties[uid] = penalty_info
                applied_penalties[uid] = penalty_info
                
                logger.warning(f"⚖️ ALPHA OVER-SELLING PENALTY APPLIED to UID {uid}: "
                             f"{penalty_level} violation, {config['score_reduction']*100:.0f}% score reduction "
                             f"for {duration_hours} hours (stake decrease: {violation['stake_change_percent']:.1f}%, "
                             f"stake change: {violation['stake_change']:+.2f})")
            
            return applied_penalties
            
        except Exception as e:
            logger.error(f"Error applying over-selling penalties: {e}")
            return {}
    
    def check_penalty_expiration(self, current_block: int) -> List[int]:
        """
        Check for expired penalties and remove them.
        
        Args:
            current_block: Current block number
            
        Returns:
            List of UIDs with expired penalties
        """
        try:
            expired_uids = []
            
            for uid, penalty_info in list(self.active_penalties.items()):
                if current_block >= penalty_info['end_block']:
                    expired_uids.append(uid)
                    del self.active_penalties[uid]
                    
                    logger.info(f"⏰ ALPHA OVER-SELLING PENALTY EXPIRED for UID {uid} at block {current_block}")
            
            if expired_uids:
                logger.info(f"📋 EXPIRED OVER-SELLING PENALTY UIDs: {expired_uids}")
            
            return expired_uids
            
        except Exception as e:
            logger.error(f"Error checking penalty expiration: {e}")
            return []
    
    def apply_penalties_to_scores(self, scores: Dict[str, float], current_block: int) -> Tuple[Dict[str, float], float]:
        """
        Apply active penalties to miner scores and collect penalty losses for UID 44.
        
        Args:
            scores: Dictionary of UID -> score mappings
            current_block: Current block number
            
        Returns:
            Tuple of (adjusted_scores, total_penalty_loss):
            - adjusted_scores: Dictionary of adjusted scores
            - total_penalty_loss: Total points lost to penalties (to be given to UID 44)
        """
        try:
            adjusted_scores = scores.copy()
            penalties_applied = 0
            total_penalty_loss = 0.0
            penalty_details = []
            
            for uid_str, score in scores.items():
                try:
                    uid = int(uid_str)
                except (ValueError, TypeError):
                    continue
                
                if uid in self.active_penalties:
                    penalty_info = self.active_penalties[uid]
                    
                    # Check if penalty is still active
                    if current_block < penalty_info['end_block']:
                        reduction = penalty_info['score_reduction']
                        new_score = score * (1 - reduction)
                        penalty_loss = score - new_score  # Amount lost to penalty
                        
                        adjusted_scores[uid_str] = new_score
                        total_penalty_loss += penalty_loss
                        penalties_applied += 1
                        
                        penalty_details.append({
                            'uid': uid,
                            'original_score': score,
                            'penalized_score': new_score,
                            'penalty_loss': penalty_loss,
                            'penalty_level': penalty_info['penalty_level']
                        })
                        
                        logger.info(f"🚨 ALPHA OVER-SELLING PENALTY APPLIED to UID {uid}: "
                                   f"{score:.3f} → {new_score:.3f} ({reduction*100:.0f}% reduction, "
                                   f"{penalty_info['penalty_level']} violation, loss: {penalty_loss:.3f})")
            
            if penalties_applied > 0:
                logger.warning(f"🎯 ALPHA OVER-SELLING PENALTY SUMMARY: {penalties_applied} miners penalized")
                logger.warning(f"💰 TOTAL PENALTY LOSS COLLECTED: {total_penalty_loss:.3f} points")
                logger.warning(f"📋 PENALTY DETAILS: {[f'UID {d['uid']}: -{d['penalty_loss']:.3f}' for d in penalty_details]}")
                logger.info(f"🎁 UID 44 WILL RECEIVE: {total_penalty_loss:.3f} points from penalties")
            else:
                logger.info("✅ No active penalties - UID 44 receives 0 bonus points")
            
            return adjusted_scores, total_penalty_loss
            
        except Exception as e:
            logger.error(f"Error applying penalties to scores: {e}")
            return scores, 0.0
    
    def get_penalty_status(self, uid: int, current_block: int) -> Optional[Dict]:
        """
        Get current penalty status for a specific UID.
        
        Args:
            uid: Miner UID
            current_block: Current block number
            
        Returns:
            Penalty status dictionary or None if no active penalty
        """
        try:
            if uid not in self.active_penalties:
                return None
            
            penalty_info = self.active_penalties[uid]
            
            # Check if penalty is still active
            if current_block >= penalty_info['end_block']:
                return None
            
            remaining_blocks = penalty_info['end_block'] - current_block
            remaining_hours = remaining_blocks / 36  # Approximate hours
            
            return {
                'uid': uid,
                'violation_type': 'alpha_overselling',
                'penalty_level': penalty_info['penalty_level'],
                'score_reduction': penalty_info['score_reduction'],
                'remaining_blocks': remaining_blocks,
                'remaining_hours': remaining_hours,
                'end_block': penalty_info['end_block'],
                'stake_change_percent': penalty_info['stake_change_percent'],
                'stake_change': penalty_info['stake_change'],
                'initial_stake': penalty_info['initial_stake'],
                'current_stake': penalty_info['current_stake']
            }
            
        except Exception as e:
            logger.error(f"Error getting penalty status for UID {uid}: {e}")
            return None
    
    def get_penalty_summary(self) -> Dict:
        """
        Get summary of active penalties and system status.
        
        Returns:
            Dictionary with penalty summary
        """
        try:
            # Calculate total violations from active penalties
            total_violations = 0
            penalty_level_counts = {}
            
            for penalty_info in self.active_penalties.values():
                total_violations += 1
                level = penalty_info.get('penalty_level', 'unknown')
                penalty_level_counts[level] = penalty_level_counts.get(level, 0) + 1
            
            return {
                'active_penalties': len(self.active_penalties),
                'total_violations': total_violations,  # Added missing field
                'total_miners_tracked': len(self.stake_history),
                'stake_decrease_threshold': self.stake_decrease_threshold,
                'new_miner_protection_entries': self.new_miner_protection_entries,
                'penalty_levels': list(self.penalty_levels.keys()),
                'penalty_level_counts': penalty_level_counts,
                'active_penalty_uids': list(self.active_penalties.keys()),
                'history_file': self.stake_history_file
            }
            
        except Exception as e:
            logger.error(f"Error getting penalty summary: {e}")
            return {}
    
    def cleanup_old_history(self):
        """
        Clean up old history data to prevent file from growing too large.
        
        Strategy: Keep last 7 days OR minimum 15 entries (whichever is MORE)
        This ensures sufficient data for penalty analysis while managing storage.
        """
        try:
            current_time = time.time()
            cutoff_time = current_time - (7 * 24 * 3600)  # 7 days
            MIN_ENTRIES_TO_KEEP = 15
            
            cleaned_count = 0
            kept_count = 0
            removed_uids = []
            
            for uid in list(self.stake_history.keys()):
                original_count = len(self.stake_history[uid])
                
                # Filter by time
                time_filtered = [
                    entry for entry in self.stake_history[uid] 
                    if entry['timestamp'] > cutoff_time
                ]
                
                # Keep minimum entries for analysis capability
                if len(time_filtered) >= MIN_ENTRIES_TO_KEEP:
                    self.stake_history[uid] = time_filtered
                elif len(self.stake_history[uid]) >= MIN_ENTRIES_TO_KEEP:
                    # Keep last 15 entries regardless of age
                    self.stake_history[uid] = self.stake_history[uid][-MIN_ENTRIES_TO_KEEP:]
                # else: keep all if less than MIN_ENTRIES_TO_KEEP
                
                # Remove UIDs with no entries
                if not self.stake_history[uid]:
                    removed_uids.append(uid)
                    del self.stake_history[uid]
                    cleaned_count += 1
                else:
                    kept_count += 1
            
            logger.info(f"Cleanup complete: {kept_count} miners tracked, {cleaned_count} empty UIDs removed")
            if removed_uids:
                logger.info(f"Removed UIDs: {removed_uids}")
            
        except Exception as e:
            logger.error(f"Error cleaning up old history: {e}")