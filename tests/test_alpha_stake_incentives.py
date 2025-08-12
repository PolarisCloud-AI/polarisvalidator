import unittest
import asyncio
import time
from unittest.mock import Mock, patch, MagicMock
import bittensor as bt
from bittensor.mock.wallet_mock import get_mock_hotkey, get_mock_coldkey
import numpy as np
import sys
import os

# Add the parent directory to the path to import neurons.utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neurons.utils.api_utils import (
    _sync_metagraph,
    _hotkey_to_uid_cache,
    _last_metagraph_sync,
    _metagraph_sync_interval,
    _metagraph,
    get_miner_uid_by_hotkey,
    analyze_alpha_stake_distribution,
    get_uid_alpha_stake_info,
    apply_alpha_stake_bonus
)


class TestAlphaStakeIncentives(unittest.TestCase):
    """Test cases for Alpha-stake based incentives functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset global variables before each test
        global _hotkey_to_uid_cache, _last_metagraph_sync, _metagraph
        _hotkey_to_uid_cache.clear()
        _last_metagraph_sync = 0
        _metagraph = None
        
        # Test parameters
        self.netuid = 49
        self.network = "finney"
        self.test_hotkeys = [
            "5F...abc1",  # Mock hotkey 1
            "5F...abc2",  # Mock hotkey 2
            "5F...abc3",  # Mock hotkey 3
            "5F...abc4",  # Mock hotkey 4
            "5F...abc5",  # Mock hotkey 5
        ]
        self.test_uids = [0, 1, 2, 3, 4]

    def tearDown(self):
        """Clean up after each test."""
        # Reset global variables
        global _hotkey_to_uid_cache, _last_metagraph_sync, _metagraph
        _hotkey_to_uid_cache.clear()
        _last_metagraph_sync = 0
        _metagraph = None

    @patch('bittensor.subtensor')
    def test_sync_metagraph_success(self, mock_subtensor):
        """Test successful metagraph synchronization."""
        # Mock the subtensor connection
        mock_subtensor_instance = Mock()
        mock_subtensor.return_value = mock_subtensor_instance
        
        # Mock the metagraph
        mock_metagraph = Mock()
        mock_metagraph.hotkeys = self.test_hotkeys
        mock_subtensor_instance.metagraph.return_value = mock_metagraph
        
        # Call the function
        _sync_metagraph(self.netuid, self.network)
        
        # Verify the function was called correctly
        mock_subtensor.assert_called_once_with(network=self.network)
        mock_subtensor_instance.metagraph.assert_called_once_with(netuid=self.netuid)
        
        # Verify global variables were updated
        global _hotkey_to_uid_cache, _last_metagraph_sync, _metagraph
        self.assertEqual(len(_hotkey_to_uid_cache), len(self.test_hotkeys))
        self.assertGreater(_last_metagraph_sync, 0)
        self.assertIsNotNone(_metagraph)

    @patch('bittensor.subtensor')
    def test_sync_metagraph_cache_refresh_interval(self, mock_subtensor):
        """Test that metagraph is refreshed when cache interval expires."""
        global _last_metagraph_sync
        
        # Mock the subtensor connection
        mock_subtensor_instance = Mock()
        mock_subtensor.return_value = mock_subtensor_instance
        
        # Mock the metagraph
        mock_metagraph = Mock()
        mock_metagraph.hotkeys = self.test_hotkeys
        mock_subtensor_instance.metagraph.return_value = mock_metagraph
        
        # First sync
        _sync_metagraph(self.netuid, self.network)
        first_sync_time = _last_metagraph_sync
        
        # Wait for cache to expire (simulate time passing)
        _last_metagraph_sync = time.time() - _metagraph_sync_interval - 1
        
        # Second sync should trigger refresh
        _sync_metagraph(self.netuid, self.network)
        second_sync_time = _last_metagraph_sync
        
        # Verify that sync was called twice
        self.assertEqual(mock_subtensor_instance.metagraph.call_count, 2)
        self.assertGreater(second_sync_time, first_sync_time)

    @patch('bittensor.subtensor')
    def test_sync_metagraph_error_handling(self, mock_subtensor):
        """Test error handling during metagraph synchronization."""
        # Mock the subtensor to raise an exception
        mock_subtensor.side_effect = Exception("Connection failed")
        
        # Call the function
        _sync_metagraph(self.netuid, self.network)
        
        # Verify global variables are reset on error
        global _hotkey_to_uid_cache, _metagraph
        self.assertEqual(len(_hotkey_to_uid_cache), 0)
        self.assertIsNone(_metagraph)

    @patch('bittensor.subtensor')
    def test_get_miner_uid_by_hotkey_success(self, mock_subtensor):
        """Test successful UID retrieval by hotkey."""
        # Mock the subtensor connection
        mock_subtensor_instance = Mock()
        mock_subtensor.return_value = mock_subtensor_instance
        
        # Mock the metagraph
        mock_metagraph = Mock()
        mock_metagraph.hotkeys = self.test_hotkeys
        mock_subtensor_instance.metagraph.return_value = mock_metagraph
        
        # Test hotkey lookup
        test_hotkey = self.test_hotkeys[2]  # Should map to UID 2
        result = get_miner_uid_by_hotkey(test_hotkey, self.netuid, self.network)
        
        self.assertEqual(result, 2)

    def test_get_miner_uid_by_hotkey_invalid_input(self):
        """Test UID retrieval with invalid hotkey input."""
        # Test with None hotkey
        result = get_miner_uid_by_hotkey(None, self.netuid, self.network)
        self.assertIsNone(result)
        
        # Test with empty string
        result = get_miner_uid_by_hotkey("", self.netuid, self.network)
        self.assertIsNone(result)
        
        # Test with non-string input
        result = get_miner_uid_by_hotkey(123, self.netuid, self.network)
        self.assertIsNone(result)

    @patch('bittensor.subtensor')
    def test_get_miner_uid_by_hotkey_force_refresh(self, mock_subtensor):
        """Test that force_refresh parameter triggers metagraph refresh."""
        # Mock the subtensor connection
        mock_subtensor_instance = Mock()
        mock_subtensor.return_value = mock_subtensor_instance
        
        # Mock the metagraph
        mock_metagraph = Mock()
        mock_metagraph.hotkeys = self.test_hotkeys
        mock_subtensor_instance.metagraph.return_value = mock_metagraph
        
        # First call without force refresh
        get_miner_uid_by_hotkey(self.test_hotkeys[0], self.netuid, self.network)
        first_call_count = mock_subtensor_instance.metagraph.call_count
        
        # Second call with force refresh
        get_miner_uid_by_hotkey(self.test_hotkeys[0], self.netuid, self.network, force_refresh=True)
        second_call_count = mock_subtensor_instance.metagraph.call_count
        
        # Verify that metagraph was called twice (once for each call)
        self.assertEqual(second_call_count, 2)

    def test_analyze_alpha_stake_distribution(self):
        """Test analysis of Alpha stake distribution across miners."""
        # Mock metagraph data with different stake levels
        mock_metagraph = Mock()
        mock_metagraph.neurons = [
            Mock(stake={"coldkey1": 1200, "coldkey2": 300}),  # UID 0: 1500 total
            Mock(stake={"coldkey3": 6000, "coldkey4": 1000}), # UID 1: 7000 total
            Mock(stake={"coldkey5": 800}),                     # UID 2: 800 total
            Mock(stake={"coldkey6": 3000, "coldkey7": 2000}), # UID 3: 5000 total
            Mock(stake={"coldkey8": 400}),                     # UID 4: 400 total
        ]
        
        # Mock hotkeys
        mock_metagraph.hotkeys = self.test_hotkeys
        
        # Test the analysis function
        result = analyze_alpha_stake_distribution(mock_metagraph)
        
        # Verify the analysis results
        self.assertEqual(result["total_miners"], 5)
        self.assertEqual(result["stake_tiers"]["high"], 2)      # UIDs 1, 3 (≥5000)
        self.assertEqual(result["stake_tiers"]["medium"], 1)    # UID 0 (≥1000)
        self.assertEqual(result["stake_tiers"]["low"], 2)       # UIDs 2, 4 (<1000)
        self.assertEqual(result["total_alpha_staked"], 14800)
        self.assertEqual(result["average_stake"], 2960)

    def test_get_uid_alpha_stake_info(self):
        """Test retrieval of Alpha stake information for a specific UID."""
        # Mock metagraph data
        mock_metagraph = Mock()
        mock_metagraph.neurons = [
            Mock(
                uid=2,
                stake={"coldkey1": 3000, "coldkey2": 2000},
                total_stake=5000,
                emission=0.15,
                rank=0.8,
                trust=0.9,
                hotkey=self.test_hotkeys[2],
                coldkey="test_coldkey"
            )
        ]
        mock_metagraph.hotkeys = self.test_hotkeys
        
        # Test the function
        result = get_uid_alpha_stake_info(2, mock_metagraph)
        
        # Verify the result
        self.assertEqual(result["uid"], 2)
        self.assertEqual(result["total_stake"], 5000)
        self.assertEqual(result["emission"], 0.15)
        self.assertEqual(result["rank"], 0.8)
        self.assertEqual(result["trust"], 0.9)
        self.assertEqual(result["hotkey"], self.test_hotkeys[2])
        self.assertEqual(result["coldkey"], "test_coldkey")
        self.assertEqual(result["stake_tier"], "high")

    def test_apply_alpha_stake_bonus(self):
        """Test application of Alpha stake bonuses to rewards."""
        # Test data
        base_rewards = {
            "miner_1": {"total_score": 100.0, "miner_uid": "123"},
            "miner_2": {"total_score": 200.0, "miner_uid": "456"},
            "miner_3": {"total_score": 150.0, "miner_uid": "789"},
        }
        
        # Mock UID stake information
        uid_stake_info = {
            "123": {"total_stake": 800, "stake_tier": "low"},      # No bonus
            "456": {"total_stake": 3000, "stake_tier": "medium"},  # 10% bonus
            "789": {"total_stake": 7000, "stake_tier": "high"},    # 20% bonus
        }
        
        # Apply bonuses
        result = apply_alpha_stake_bonus(base_rewards, uid_stake_info)
        
        # Verify the results
        self.assertEqual(result["miner_1"]["total_score"], 100.0)  # No change
        self.assertEqual(result["miner_2"]["total_score"], 220.0)  # 200 * 1.1
        self.assertEqual(result["miner_3"]["total_score"], 180.0)  # 150 * 1.2
        
        # Verify bonus information is added
        self.assertIn("alpha_stake_bonus", result["miner_2"])
        self.assertEqual(result["miner_2"]["alpha_stake_bonus"]["bonus_percentage"], 10)
        self.assertEqual(result["miner_2"]["alpha_stake_bonus"]["stake_amount"], 3000)

    def test_apply_alpha_stake_bonus_edge_cases(self):
        """Test edge cases for Alpha stake bonus application."""
        # Test with empty rewards
        result = apply_alpha_stake_bonus({}, {})
        self.assertEqual(result, {})
        
        # Test with None values
        result = apply_alpha_stake_bonus(None, {})
        self.assertEqual(result, {})
        
        # Test with missing UID information
        base_rewards = {"miner_1": {"total_score": 100.0, "miner_uid": "123"}}
        uid_stake_info = {}  # No stake info for UID 123
        
        result = apply_alpha_stake_bonus(base_rewards, uid_stake_info)
        self.assertEqual(result["miner_1"]["total_score"], 100.0)  # No change

    def test_stake_tier_classification(self):
        """Test classification of miners into stake tiers."""
        # Test different stake amounts
        test_cases = [
            (100, "low"),      # Below 1000
            (999, "low"),      # Below 1000
            (1000, "medium"),  # Exactly 1000
            (2500, "medium"),  # Between 1000 and 5000
            (4999, "medium"),  # Below 5000
            (5000, "high"),    # Exactly 5000
            (7500, "high"),    # Above 5000
            (10000, "high"),   # Well above 5000
        ]
        
        for stake_amount, expected_tier in test_cases:
            with self.subTest(stake_amount=stake_amount):
                # Mock metagraph with single neuron
                mock_metagraph = Mock()
                mock_metagraph.neurons = [
                    Mock(stake={"coldkey": stake_amount}, total_stake=stake_amount)
                ]
                mock_metagraph.hotkeys = ["test_hotkey"]
                
                # Get stake info
                result = get_uid_alpha_stake_info(0, mock_metagraph)
                self.assertEqual(result["stake_tier"], expected_tier)

    @patch('time.time')
    def test_cache_frequency_consistency(self, mock_time):
        """Test that cache frequency is consistent with api_utils.py."""
        global _last_metagraph_sync
        
        # Mock time to return a fixed timestamp
        mock_time.return_value = 1000.0
        
        # Verify the cache interval matches the one in api_utils.py
        from neurons.utils.api_utils import _metagraph_sync_interval
        self.assertEqual(_metagraph_sync_interval, 300)  # 5 minutes in seconds
        
        # Test that cache expires after the interval
        _last_metagraph_sync = 1000.0 - 301  # Just expired
        
        # Should trigger refresh
        with patch('bittensor.subtensor') as mock_subtensor:
            mock_subtensor_instance = Mock()
            mock_subtensor.return_value = mock_subtensor_instance
            mock_metagraph = Mock()
            mock_metagraph.hotkeys = self.test_hotkeys
            mock_subtensor_instance.metagraph.return_value = mock_metagraph
            
            _sync_metagraph(self.netuid, self.network)
            mock_subtensor_instance.metagraph.assert_called_once()


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
