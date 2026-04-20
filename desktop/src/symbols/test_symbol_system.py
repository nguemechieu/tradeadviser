"""Unit tests for the symbol caching and sync system."""

import unittest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

from src.symbols import (
    SymbolCache, SymbolMetadata, SymbolStorage,
    SymbolSyncManager, SyncPolicy, SymbolManager
)


class TestSymbolCache(unittest.TestCase):
    """Tests for SymbolCache."""
    
    def setUp(self):
        self.cache = SymbolCache()
    
    def test_add_symbol(self):
        """Test adding symbol to cache."""
        meta = SymbolMetadata(symbol='BTC', name='Bitcoin', asset_class='crypto')
        result = self.cache.add_symbol(meta)
        
        self.assertTrue(result)
        self.assertTrue(self.cache.has_symbol('BTC'))
        self.assertEqual(self.cache.get_symbol_count(), 1)
    
    def test_get_symbol(self):
        """Test retrieving symbol from cache."""
        meta = SymbolMetadata(symbol='ETH', name='Ethereum', asset_class='crypto')
        self.cache.add_symbol(meta)
        
        retrieved = self.cache.get_symbol('ETH')
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, 'Ethereum')
    
    def test_cache_hit_miss(self):
        """Test cache hit/miss tracking."""
        meta = SymbolMetadata(symbol='SOL', name='Solana', asset_class='crypto')
        self.cache.add_symbol(meta)
        
        # Hit
        self.cache.get_symbol('SOL')
        self.assertEqual(self.cache.metrics.cache_hit_count, 1)
        
        # Miss
        self.cache.get_symbol('NONEXISTENT')
        self.assertEqual(self.cache.metrics.cache_miss_count, 1)
        
        self.assertEqual(self.cache.metrics.hit_rate, 50.0)
    
    def test_filter_by_asset_class(self):
        """Test filtering by asset class."""
        self.cache.add_symbol(SymbolMetadata(symbol='BTC', asset_class='crypto'))
        self.cache.add_symbol(SymbolMetadata(symbol='ETH', asset_class='crypto'))
        self.cache.add_symbol(SymbolMetadata(symbol='AAPL', asset_class='stock'))
        
        crypto_symbols = self.cache.get_symbols_by_asset_class('crypto')
        self.assertEqual(len(crypto_symbols), 2)
        self.assertIn('BTC', crypto_symbols)
        self.assertIn('ETH', crypto_symbols)
    
    def test_search_symbols(self):
        """Test symbol search."""
        self.cache.add_symbol(SymbolMetadata(symbol='BTC', name='Bitcoin'))
        self.cache.add_symbol(SymbolMetadata(symbol='BCH', name='Bitcoin Cash'))
        self.cache.add_symbol(SymbolMetadata(symbol='ETH', name='Ethereum'))
        
        results = self.cache.search_symbols('Bitcoin')
        self.assertEqual(len(results), 2)
    
    def test_sync_tracking(self):
        """Test sync tracking."""
        self.assertIsNone(self.cache.get_last_sync_time('broker1'))
        
        self.cache.record_sync('broker1')
        
        last_sync = self.cache.get_last_sync_time('broker1')
        self.assertIsNotNone(last_sync)
    
    def test_should_sync(self):
        """Test sync interval logic."""
        # First time should always sync
        self.assertTrue(self.cache.should_sync_with_broker('broker1', min_interval_minutes=60))
        
        # Record a sync
        self.cache.record_sync('broker1')
        
        # Should not sync immediately
        self.assertFalse(self.cache.should_sync_with_broker('broker1', min_interval_minutes=60))
        
        # Should sync after interval expires
        self.cache._last_broker_check['broker1'] = datetime.utcnow() - timedelta(hours=2)
        self.assertTrue(self.cache.should_sync_with_broker('broker1', min_interval_minutes=60))


class TestSymbolStorage(unittest.TestCase):
    """Tests for SymbolStorage."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.storage = SymbolStorage(storage_dir=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_save_and_load_symbols(self):
        """Test saving and loading symbols."""
        symbols = {
            'BTC': SymbolMetadata(symbol='BTC', name='Bitcoin'),
            'ETH': SymbolMetadata(symbol='ETH', name='Ethereum'),
        }
        
        # Save
        result = self.storage.save_symbols(symbols)
        self.assertTrue(result)
        
        # Load
        loaded = self.storage.load_symbols()
        self.assertEqual(len(loaded), 2)
        self.assertIn('BTC', loaded)
        self.assertEqual(loaded['BTC'].name, 'Bitcoin')
    
    def test_backup_creation(self):
        """Test backup creation."""
        symbols = {'BTC': SymbolMetadata(symbol='BTC')}
        self.storage.save_symbols(symbols)
        
        backup_path = self.storage.backup_symbols()
        self.assertIsNotNone(backup_path)
        self.assertTrue(backup_path.exists())
    
    def test_csv_export(self):
        """Test CSV export."""
        symbols = {
            'BTC': SymbolMetadata(symbol='BTC', name='Bitcoin', asset_class='crypto'),
            'AAPL': SymbolMetadata(symbol='AAPL', name='Apple', asset_class='stock'),
        }
        
        csv_path = Path(self.temp_dir) / 'symbols.csv'
        result = self.storage.export_to_csv(symbols, str(csv_path))
        
        self.assertTrue(result)
        self.assertTrue(csv_path.exists())


class TestSymbolSyncManager(unittest.TestCase):
    """Tests for SymbolSyncManager."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cache = SymbolCache()
        self.storage = SymbolStorage(storage_dir=self.temp_dir)
        self.sync_mgr = SymbolSyncManager(self.cache, self.storage)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_register_broker(self):
        """Test broker registration."""
        def fetcher():
            return []
        
        self.sync_mgr.register_broker('test_broker', fetcher)
        self.assertIn('test_broker', self.sync_mgr._broker_symbol_fetchers)
    
    def test_sync_result(self):
        """Test sync operation result."""
        # Register fetcher
        def fetcher():
            return [
                SymbolMetadata(symbol='BTC', name='Bitcoin'),
                SymbolMetadata(symbol='ETH', name='Ethereum'),
            ]
        
        self.sync_mgr.register_broker('test', fetcher)
        
        # Sync
        result = self.sync_mgr.sync_broker_symbols('test', force=True)
        
        self.assertTrue(result.success)
        self.assertEqual(result.symbols_added, 2)
    
    def test_symbol_comparison(self):
        """Test symbol comparison logic."""
        # Add initial symbols
        self.cache.add_symbol(SymbolMetadata(symbol='BTC', name='Bitcoin'))
        self.cache.add_symbol(SymbolMetadata(symbol='ETH', name='Ethereum'))
        
        # New symbols from broker (with updates and removals)
        new_symbols = [
            SymbolMetadata(symbol='BTC', name='Bitcoin'),  # Existing
            SymbolMetadata(symbol='SOL', name='Solana'),    # New
            SymbolMetadata(symbol='ADA', name='Cardano'),   # New
        ]
        
        result = self.sync_mgr._compare_and_update('test_broker', new_symbols)
        
        self.assertEqual(result.symbols_added, 2)
        self.assertEqual(result.symbols_removed, 1)  # ETH marked as delisted
    
    def test_sync_policy(self):
        """Test sync policy configuration."""
        policy = SyncPolicy(min_interval_minutes=30, force_full_sync_hours=12)
        self.sync_mgr.set_sync_policy(policy)
        
        self.assertEqual(self.sync_mgr.sync_policy.min_interval_minutes, 30)
        self.assertEqual(self.sync_mgr.sync_policy.force_full_sync_hours, 12)
    
    def test_sync_listeners(self):
        """Test sync event listeners."""
        events = []
        
        def listener(result):
            events.append(result)
        
        self.sync_mgr.subscribe(listener)
        
        def fetcher():
            return [SymbolMetadata(symbol='BTC', name='Bitcoin')]
        
        self.sync_mgr.register_broker('test', fetcher)
        self.sync_mgr.sync_broker_symbols('test', force=True)
        
        self.assertEqual(len(events), 1)
        self.assertTrue(events[0].success)


class TestSymbolManager(unittest.TestCase):
    """Tests for SymbolManager (high-level API)."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mgr = SymbolManager(storage_dir=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_initialize(self):
        """Test initialization."""
        result = self.mgr.initialize()
        self.assertTrue(result)
    
    def test_sync_flow(self):
        """Test complete sync flow."""
        self.mgr.initialize()
        
        def fetcher():
            return [
                SymbolMetadata(symbol='BTC', name='Bitcoin', asset_class='crypto', exchange='COINBASE'),
                SymbolMetadata(symbol='ETH', name='Ethereum', asset_class='crypto', exchange='COINBASE'),
                SymbolMetadata(symbol='SOL', name='Solana', asset_class='crypto', exchange='COINBASE'),
            ]
        
        self.mgr.register_broker_fetcher('test_broker', fetcher)
        
        # Sync
        success = self.mgr.sync_broker('test_broker', force=True)
        self.assertTrue(success)
        
        # Verify symbols
        self.assertEqual(self.mgr.get_symbol_count(), 3)
        self.assertTrue(self.mgr.has_symbol('BTC'))
        
        # Query
        symbols = self.mgr.get_symbols_by_asset_class('crypto')
        self.assertEqual(len(symbols), 3)
        
        self.mgr.shutdown()
    
    def test_statistics(self):
        """Test statistics retrieval."""
        self.mgr.initialize()
        
        def fetcher():
            return [SymbolMetadata(symbol='TEST', name='Test')]
        
        self.mgr.register_broker_fetcher('test', fetcher)
        self.mgr.sync_broker('test', force=True)
        
        stats = self.mgr.get_sync_stats()
        self.assertEqual(stats['cache_size'], 1)
        self.assertEqual(stats['total_syncs'], 1)
        self.assertEqual(stats['successful_syncs'], 1)
        
        self.mgr.shutdown()


if __name__ == '__main__':
    unittest.main()
