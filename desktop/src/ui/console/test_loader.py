"""Unit tests for the loading system."""

import asyncio
import pytest
from unittest.mock import Mock, patch, AsyncMock

from tradeadviser_desktop.src.ui.console.loader import (
    LoadingManager,
    LoadingState,
    LoadingTask,
    LoadingIndicator,
    ConsoleLoaderIntegration,
)
from tradeadviser_desktop.src.ui.console.system_console import SystemConsole


class TestLoadingTask:
    """Test LoadingTask data class."""
    
    def test_task_creation(self):
        """Test creating a loading task."""
        task = LoadingTask(
            task_id="test_1",
            name="Test Task"
        )
        assert task.task_id == "test_1"
        assert task.name == "Test Task"
        assert task.status == LoadingState.IDLE
        assert task.progress == 0.0
    
    def test_task_str_idle(self):
        """Test string representation in idle state."""
        task = LoadingTask(task_id="t1", name="Test")
        assert str(task) == "○ Test"
    
    def test_task_str_loading(self):
        """Test string representation in loading state."""
        task = LoadingTask(
            task_id="t1",
            name="Test",
            status=LoadingState.LOADING,
            progress=50.0,
            message="Processing"
        )
        assert "⟳" in str(task)
        assert "50%" in str(task)
    
    def test_task_str_complete(self):
        """Test string representation in complete state."""
        task = LoadingTask(
            task_id="t1",
            name="Test",
            status=LoadingState.COMPLETE,
            progress=100.0
        )
        assert "✓" in str(task)


class TestLoadingIndicator:
    """Test LoadingIndicator utilities."""
    
    def test_get_spinner(self):
        """Test spinner frame generation."""
        spinner = LoadingIndicator.get_spinner(frame=0)
        assert isinstance(spinner, str)
        assert len(spinner) > 0
    
    def test_spinner_cycles(self):
        """Test spinner animation cycles."""
        frames = [LoadingIndicator.get_spinner(i) for i in range(20)]
        # Should have repeating pattern
        assert frames[0] == frames[10]
    
    def test_get_progress_bar(self):
        """Test progress bar generation."""
        bar = LoadingIndicator.get_progress_bar(progress=50)
        assert "[" in bar and "]" in bar
        assert "50%" in bar
    
    def test_progress_bar_full(self):
        """Test full progress bar."""
        bar = LoadingIndicator.get_progress_bar(progress=100)
        assert "100%" in bar
    
    def test_progress_bar_empty(self):
        """Test empty progress bar."""
        bar = LoadingIndicator.get_progress_bar(progress=0)
        assert "0%" in bar


class TestLoadingManager:
    """Test LoadingManager."""
    
    def test_manager_creation(self):
        """Test creating a loading manager."""
        manager = LoadingManager()
        assert manager.tasks == {}
        assert manager.workers == {}
    
    @pytest.mark.asyncio
    async def test_load_async_success(self):
        """Test successful async load."""
        manager = LoadingManager()
        
        async def dummy_task():
            await asyncio.sleep(0.01)
            return "result"
        
        result = await manager.load_async(
            task_id="test_1",
            name="Test Task",
            coro=dummy_task()
        )
        
        assert result == "result"
        task = manager.get_task("test_1")
        assert task.status == LoadingState.COMPLETE
        assert task.progress == 100.0
    
    @pytest.mark.asyncio
    async def test_load_async_error(self):
        """Test failed async load."""
        manager = LoadingManager()
        
        async def failing_task():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await manager.load_async(
                task_id="test_1",
                name="Test Task",
                coro=failing_task()
            )
        
        task = manager.get_task("test_1")
        assert task.status == LoadingState.ERROR
        assert "Test error" in task.error
    
    @pytest.mark.asyncio
    async def test_update_progress(self):
        """Test progress updates."""
        manager = LoadingManager()
        
        async def long_task():
            await asyncio.sleep(0.02)
        
        # Start task
        task_coro = manager.load_async(
            task_id="test_1",
            name="Test",
            coro=long_task()
        )
        
        # Update progress
        manager.update_progress("test_1", 50, "Halfway done")
        
        # Verify update
        task = manager.get_task("test_1")
        assert task.progress == 50.0
        assert task.message == "Halfway done"
        
        # Complete task
        await task_coro
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_tasks(self):
        """Test multiple tasks running concurrently."""
        manager = LoadingManager()
        
        async def task(n):
            await asyncio.sleep(0.01)
            return f"result_{n}"
        
        results = await asyncio.gather(
            manager.load_async(f"task_1", "Task 1", task(1)),
            manager.load_async(f"task_2", "Task 2", task(2)),
            manager.load_async(f"task_3", "Task 3", task(3)),
        )
        
        assert len(results) == 3
        assert all(t.status == LoadingState.COMPLETE for t in manager.tasks.values())
    
    def test_get_all_tasks(self):
        """Test retrieving all tasks."""
        manager = LoadingManager()
        manager.tasks["t1"] = LoadingTask("t1", "Task 1")
        manager.tasks["t2"] = LoadingTask("t2", "Task 2")
        
        all_tasks = manager.get_all_tasks()
        assert len(all_tasks) == 2
    
    def test_clear_tasks(self):
        """Test clearing completed tasks."""
        manager = LoadingManager()
        
        task1 = LoadingTask("t1", "Task 1", status=LoadingState.COMPLETE)
        task2 = LoadingTask("t2", "Task 2", status=LoadingState.LOADING)
        
        manager.tasks["t1"] = task1
        manager.tasks["t2"] = task2
        
        manager.clear_tasks()
        
        # Should only keep loading tasks
        assert "t1" not in manager.tasks
        assert "t2" in manager.tasks


class TestSystemConsole:
    """Test SystemConsole with loading features."""
    
    def test_console_creation(self):
        """Test creating a system console."""
        console = SystemConsole()
        assert console is not None
        assert hasattr(console, 'progress_bar')
        assert hasattr(console, 'status_label')
    
    def test_set_loading(self):
        """Test setting loading state."""
        console = SystemConsole()
        
        console.set_loading(True, "Loading...", 50)
        assert console.progress_bar.isVisible()
        assert console.progress_bar.value() == 50
        
        console.set_loading(False)
        assert not console.progress_bar.isVisible()
    
    def test_update_progress(self):
        """Test updating progress."""
        console = SystemConsole()
        console.set_loading(True, "Loading...")
        
        console.update_loading_progress(75)
        assert console.progress_bar.value() == 75
    
    def test_clear_loading(self):
        """Test clearing loading state."""
        console = SystemConsole()
        console.set_loading(True, "Loading...")
        console.clear_loading()
        
        assert not console.progress_bar.isVisible()


class TestConsoleLoaderIntegration:
    """Test ConsoleLoaderIntegration."""
    
    def test_integration_creation(self):
        """Test creating console loader integration."""
        console = SystemConsole()
        manager = LoadingManager()
        
        integration = ConsoleLoaderIntegration(console, manager)
        assert integration.console is console
        assert integration.loading_manager is manager
    
    def test_integration_signals_connected(self):
        """Test that signals are connected."""
        console = SystemConsole()
        manager = LoadingManager()
        
        # Should not raise
        integration = ConsoleLoaderIntegration(console, manager)
        assert integration is not None


class TestLoadingIntegration:
    """Integration tests for complete loading workflow."""
    
    @pytest.mark.asyncio
    async def test_full_load_workflow(self):
        """Test complete loading workflow."""
        console = SystemConsole()
        manager = LoadingManager()
        integration = ConsoleLoaderIntegration(console, manager)
        
        async def simulate_data_load():
            await asyncio.sleep(0.01)
            return {"data": "loaded"}
        
        # Start loading
        console.set_loading(True, "Loading data...")
        
        # Run async operation
        result = await manager.load_async(
            task_id="integration_test",
            name="Data Load",
            coro=simulate_data_load()
        )
        
        # Verify result
        assert result == {"data": "loaded"}
        
        # Clear loading
        console.clear_loading()
        assert not console.progress_bar.isVisible()
    
    @pytest.mark.asyncio
    async def test_error_workflow(self):
        """Test error handling workflow."""
        console = SystemConsole()
        manager = LoadingManager()
        
        async def failing_load():
            raise RuntimeError("Load failed")
        
        try:
            await manager.load_async(
                task_id="error_test",
                name="Failing Load",
                coro=failing_load()
            )
        except RuntimeError:
            pass
        
        task = manager.get_task("error_test")
        assert task.status == LoadingState.ERROR


# ============================================================================
# Performance tests (optional, for benchmarking)
# ============================================================================

@pytest.mark.asyncio
async def test_load_many_concurrent_tasks():
    """Test loading performance with many concurrent tasks."""
    manager = LoadingManager()
    
    async def quick_task(n):
        await asyncio.sleep(0.001)
        return n
    
    tasks = [
        manager.load_async(f"task_{i}", f"Task {i}", quick_task(i))
        for i in range(50)
    ]
    
    results = await asyncio.gather(*tasks)
    assert len(results) == 50
    assert all(t.status == LoadingState.COMPLETE for t in manager.tasks.values())


# ============================================================================
# Running tests
# ============================================================================

if __name__ == "__main__":
    # Run with: pytest sqs_desktop/src/ui/console/test_loader.py -v
    pytest.main([__file__, "-v"])
