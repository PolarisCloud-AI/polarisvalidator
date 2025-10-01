"""
Dynamic Alpha Overselling Penalty System

This module implements a dynamic penalty system that detects and penalizes
miners who are overselling alpha tokens on the subnet. The system uses
real-time network statistics to calculate thresholds and apply contextual
penalties based on multiple factors.
"""

import time
import logging
import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DynamicPenaltySystem:
    """
    Dynamic penalty system for detecting and penalizing alpha overselling.
    
    The system calculates penalties based on:
    - Real-time network statistics
    - Individual miner behavior patterns
    - Network conditions and economic indicators
    - Historical violation frequency
    """
    
    def __init__(self, netuid: int = 49, network: str = "finney"):
        self.netuid = netuid
        self.network = network
        
        # Penalty configuration
        self.base_durations = {
            'low': 6,        # 6 hours
            'moderate': 12,  # 12 hours
            'high': 24,      # 24 hours
            'extreme': 48    # 48 hours
        }
        
        # Multiplier factors
        self.frequency_multipliers = {
            'first_offense': 1.0,
            'second_offense': 1.5,
            'third_offense': 2.0,
            'persistent': 3.0
        }
        
        self.network_multipliers = {
            'normal': 1.0,
            'high_activity': 1.2,
            'low_activity': 0.8,
            'crisis': 2.0
        }
        
        self.economic_multipliers = {
            'stable': 1.0,
            'volatile': 1.3,
            'low_liquidity': 1.5,
            'market_stress': 2.0
        }
        
        self.historical_multipliers = {
            'new_miner': 0.8,
            'established': 1.0,
            'repeat_offender': 1.5,
            'persistent_violator': 2.0
        }
        
        # Tracking data
        self.penalty_history: Dict[int, List[Dict]] = defaultdict(list)
        self.violation_counts: Dict[int, int] = defaultdict(int)
        self.network_stats: Dict = {}
        self.penalty_records: Dict[int, Dict] = {}
        
        logger.info(f"Initialized DynamicPenaltySystem for subnet {netuid}")
    
    def calculate_network_thresholds(self, metagraph) -> Dict[str, float]:
        """
        Calculate dynamic thresholds based on current network statistics.
        
        Args:
            metagraph: Bittensor metagraph object
            
        Returns:
            Dict containing threshold values for different violation levels
        """
        try:
            stakes = metagraph.stake
            emissions = metagraph.emission
            trust_scores = metagraph.trust
            
            # Filter active nodes
            active_data = []
            for i in range(len(stakes)):
                if stakes[i] > 0 and emissions[i] > 0:
                    emission_stake_ratio = emissions[i] / stakes[i]
                    active_data.append({
                        'uid': i,
                        'emission_stake_ratio': emission_stake_ratio,
                        'trust': trust_scores[i],
                        'stake': stakes[i],
                        'emission': emissions[i]
                    })
            
            if not active_data:
                # Default thresholds if no active data
                return {
                    'low_threshold': 0.05,
                    'moderate_threshold': 0.08,
                    'high_threshold': 0.12,
                    'extreme_threshold': 0.20,
                    'trust_low': 0.8,
                    'trust_moderate': 0.7,
                    'trust_high': 0.6,
                    'trust_extreme': 0.5
                }
            
            # Calculate percentiles for emission/stake ratios
            ratios = [data['emission_stake_ratio'] for data in active_data]
            trust_scores_list = [data['trust'] for data in active_data]
            
            # Calculate thresholds
            thresholds = {
                'low_threshold': np.percentile(ratios, 75),      # 75th percentile
                'moderate_threshold': np.percentile(ratios, 85), # 85th percentile
                'high_threshold': np.percentile(ratios, 95),     # 95th percentile
                'extreme_threshold': np.percentile(ratios, 99),  # 99th percentile
            }
            
            # Trust thresholds based on average
            avg_trust = np.mean(trust_scores_list)
            thresholds.update({
                'trust_low': avg_trust * 0.8,
                'trust_moderate': avg_trust * 0.7,
                'trust_high': avg_trust * 0.6,
                'trust_extreme': avg_trust * 0.5
            })
            
            # Store network stats
            self.network_stats = {
                'total_active_nodes': len(active_data),
                'median_emission_stake_ratio': np.median(ratios),
                'avg_trust': avg_trust,
                'total_stake': sum(data['stake'] for data in active_data),
                'total_emission': sum(data['emission'] for data in active_data),
                'timestamp': time.time()
            }
            
            logger.info(f"Calculated network thresholds: {thresholds}")
            return thresholds
            
        except Exception as e:
            logger.error(f"Error calculating network thresholds: {e}")
            # Return default thresholds
            return {
                'low_threshold': 0.05,
                'moderate_threshold': 0.08,
                'high_threshold': 0.12,
                'extreme_threshold': 0.20,
                'trust_low': 0.8,
                'trust_moderate': 0.7,
                'trust_high': 0.6,
                'trust_extreme': 0.5
            }
    
    def detect_violations(self, metagraph) -> List[Dict]:
        """
        Detect alpha overselling violations using dynamic thresholds.
        
        Args:
            metagraph: Bittensor metagraph object
            
        Returns:
            List of violation records for each miner
        """
        try:
            thresholds = self.calculate_network_thresholds(metagraph)
            violations = []
            
            stakes = metagraph.stake
            emissions = metagraph.emission
            trust_scores = metagraph.trust
            
            for uid in range(len(stakes)):
                if stakes[uid] > 0 and emissions[uid] > 0:
                    emission_stake_ratio = emissions[uid] / stakes[uid]
                    trust = trust_scores[uid]
                    
                    # Determine violation level
                    violation_level = None
                    reasons = []
                    
                    # Check emission/stake ratio violations
                    if emission_stake_ratio > thresholds['extreme_threshold']:
                        violation_level = 'extreme'
                        reasons.append(f'Extreme emission/stake ratio: {emission_stake_ratio:.6f}')
                    elif emission_stake_ratio > thresholds['high_threshold']:
                        violation_level = 'high'
                        reasons.append(f'High emission/stake ratio: {emission_stake_ratio:.6f}')
                    elif emission_stake_ratio > thresholds['moderate_threshold']:
                        violation_level = 'moderate'
                        reasons.append(f'Moderate emission/stake ratio: {emission_stake_ratio:.6f}')
                    elif emission_stake_ratio > thresholds['low_threshold']:
                        violation_level = 'low'
                        reasons.append(f'Low emission/stake ratio: {emission_stake_ratio:.6f}')
                    
                    # Check trust score violations
                    if trust < thresholds['trust_extreme'] and emission_stake_ratio > thresholds['moderate_threshold']:
                        if violation_level != 'extreme':
                            violation_level = 'high'
                        reasons.append(f'Low trust ({trust:.4f}) with high emissions')
                    elif trust < thresholds['trust_high'] and emission_stake_ratio > thresholds['low_threshold']:
                        if violation_level not in ['high', 'extreme']:
                            violation_level = 'moderate'
                        reasons.append(f'Low trust ({trust:.4f}) with moderate emissions')
                    
                    if violation_level:
                        violations.append({
                            'uid': uid,
                            'violation_level': violation_level,
                            'emission_stake_ratio': emission_stake_ratio,
                            'trust_score': trust,
                            'stake': stakes[uid],
                            'emission': emissions[uid],
                            'reasons': reasons,
                            'thresholds_used': thresholds
                        })
            
            logger.info(f"Detected {len(violations)} alpha overselling violations")
            return violations
            
        except Exception as e:
            logger.error(f"Error detecting violations: {e}")
            return []
    
    def calculate_penalty_duration(self, violation: Dict, current_block: int) -> Dict:
        """
        Calculate penalty duration based on violation and contextual factors.
        
        Args:
            violation: Violation record
            current_block: Current blockchain block
            
        Returns:
            Dict containing penalty information
        """
        try:
            uid = violation['uid']
            violation_level = violation['violation_level']
            
            # Base duration
            base_duration_hours = self.base_durations[violation_level]
            
            # Get multipliers
            frequency_mult = self._get_frequency_multiplier(uid)
            network_mult = self._get_network_multiplier()
            economic_mult = self._get_economic_multiplier()
            historical_mult = self._get_historical_multiplier(uid)
            
            # Calculate final duration
            final_duration_hours = (
                base_duration_hours * 
                frequency_mult * 
                network_mult * 
                economic_mult * 
                historical_mult
            )
            
            # Convert to blocks (assuming 12 seconds per block)
            final_duration_blocks = int(final_duration_hours * 3600 / 12)
            
            penalty_info = {
                'uid': uid,
                'violation_level': violation_level,
                'base_duration_hours': base_duration_hours,
                'final_duration_hours': final_duration_hours,
                'final_duration_blocks': final_duration_blocks,
                'start_block': current_block,
                'end_block': current_block + final_duration_blocks,
                'multipliers': {
                    'frequency': frequency_mult,
                    'network': network_mult,
                    'economic': economic_mult,
                    'historical': historical_mult
                },
                'applied_at': time.time(),
                'violation_details': violation
            }
            
            return penalty_info
            
        except Exception as e:
            logger.error(f"Error calculating penalty duration for UID {violation.get('uid', 'unknown')}: {e}")
            return {}
    
    def _get_frequency_multiplier(self, uid: int) -> float:
        """Get frequency multiplier based on violation history."""
        violation_count = self.violation_counts[uid]
        
        if violation_count == 0:
            return self.frequency_multipliers['first_offense']
        elif violation_count == 1:
            return self.frequency_multipliers['second_offense']
        elif violation_count == 2:
            return self.frequency_multipliers['third_offense']
        else:
            return self.frequency_multipliers['persistent']
    
    def _get_network_multiplier(self) -> float:
        """Get network condition multiplier."""
        # For now, return normal multiplier
        # In a full implementation, this would analyze network conditions
        return self.network_multipliers['normal']
    
    def _get_economic_multiplier(self) -> float:
        """Get economic condition multiplier."""
        # For now, return stable multiplier
        # In a full implementation, this would analyze economic indicators
        return self.economic_multipliers['stable']
    
    def _get_historical_multiplier(self, uid: int) -> float:
        """Get historical pattern multiplier."""
        violation_count = self.violation_counts[uid]
        
        if violation_count == 0:
            return self.historical_multipliers['new_miner']
        elif violation_count < 3:
            return self.historical_multipliers['established']
        elif violation_count < 6:
            return self.historical_multipliers['repeat_offender']
        else:
            return self.historical_multipliers['persistent_violator']
    
    def apply_penalties(self, violations: List[Dict], current_block: int) -> Dict[int, Dict]:
        """
        Apply penalties to detected violations.
        
        Args:
            violations: List of detected violations
            current_block: Current blockchain block
            
        Returns:
            Dict mapping UID to penalty information
        """
        penalties = {}
        
        for violation in violations:
            penalty_info = self.calculate_penalty_duration(violation, current_block)
            
            if penalty_info:
                uid = penalty_info['uid']
                
                # Store penalty record
                self.penalty_records[uid] = penalty_info
                
                # Update violation count
                self.violation_counts[uid] += 1
                
                # Add to penalty history
                self.penalty_history[uid].append(penalty_info)
                
                penalties[uid] = penalty_info
                
                logger.info(f"Applied {penalty_info['violation_level']} penalty to UID {uid}: "
                           f"{penalty_info['final_duration_hours']:.1f} hours")
        
        return penalties
    
    def check_penalty_expiration(self, current_block: int) -> List[int]:
        """
        Check for expired penalties and return list of expired UIDs.
        
        Args:
            current_block: Current blockchain block
            
        Returns:
            List of UIDs with expired penalties
        """
        expired_uids = []
        
        for uid, penalty_info in list(self.penalty_records.items()):
            if current_block >= penalty_info['end_block']:
                expired_uids.append(uid)
                del self.penalty_records[uid]
                
                logger.info(f"Penalty expired for UID {uid} at block {current_block}")
        
        return expired_uids
    
    def get_penalty_status(self, uid: int, current_block: int) -> Optional[Dict]:
        """
        Get current penalty status for a specific UID.
        
        Args:
            uid: Miner UID
            current_block: Current blockchain block
            
        Returns:
            Penalty status information or None if no active penalty
        """
        if uid not in self.penalty_records:
            return None
        
        penalty_info = self.penalty_records[uid]
        
        if current_block >= penalty_info['end_block']:
            return None
        
        remaining_blocks = penalty_info['end_block'] - current_block
        remaining_hours = remaining_blocks * 12 / 3600
        
        return {
            'uid': uid,
            'violation_level': penalty_info['violation_level'],
            'remaining_blocks': remaining_blocks,
            'remaining_hours': remaining_hours,
            'end_block': penalty_info['end_block'],
            'multipliers': penalty_info['multipliers']
        }
    
    def apply_penalties_to_scores(self, scores: Dict, current_block: int) -> Dict:
        """
        Apply penalty reductions to miner scores.
        
        Args:
            scores: Dict mapping UID (int or str) to score
            current_block: Current blockchain block
            
        Returns:
            Dict with penalty-adjusted scores (same key type as input)
        """
        adjusted_scores = scores.copy()
        
        # Convert scores to integer keys for penalty lookup
        scores_int_keys = {}
        for key, value in scores.items():
            try:
                int_key = int(key)
                scores_int_keys[int_key] = value
            except (ValueError, TypeError):
                # Skip non-integer keys
                continue
        
        penalties_applied = 0
        
        for uid, penalty_info in self.penalty_records.items():
            if current_block < penalty_info['end_block'] and uid in scores_int_keys:
                violation_level = penalty_info['violation_level']
                
                # Apply penalty factor based on violation level
                penalty_factors = {
                    'low': 0.2,      # 20% reduction
                    'moderate': 0.4,  # 40% reduction
                    'high': 0.6,      # 60% reduction
                    'extreme': 0.8    # 80% reduction
                }
                
                penalty_factor = penalty_factors.get(violation_level, 0.0)
                original_score = scores_int_keys[uid]
                adjusted_score = original_score * (1 - penalty_factor)
                
                # Update the score using the original key type
                for key, value in adjusted_scores.items():
                    if str(key) == str(uid) or int(key) == uid:
                        adjusted_scores[key] = adjusted_score
                        break
                
                penalties_applied += 1
                
                logger.info(f"Applied {penalty_factor*100:.1f}% penalty to UID {uid}: "
                           f"{original_score:.3f} -> {adjusted_score:.3f}")
        
        if penalties_applied > 0:
            logger.info(f"Applied penalties to {penalties_applied} miner scores")
        else:
            logger.debug("No active penalties found for score adjustment")
        
        return adjusted_scores
    
    def get_penalty_summary(self) -> Dict:
        """
        Get summary of current penalty system status.
        
        Returns:
            Dict containing penalty system summary
        """
        return {
            'active_penalties': len(self.penalty_records),
            'total_violations': sum(self.violation_counts.values()),
            'network_stats': self.network_stats,
            'penalty_records': dict(self.penalty_records),
            'violation_counts': dict(self.violation_counts)
        }
