"""Quick launch profile manager for desktop configuration."""

import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any, List
import logging

logger = logging.getLogger(__name__)


class QuickLaunchProfileManager:
    """Manages quick launch profiles for broker configuration."""
    
    def __init__(self, session_manager, server_api_client):
        self.session_manager = session_manager
        self.server_api_client = server_api_client
        self.profiles_dir = Path.home() / ".sopotek" / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_file = self.profiles_dir / "profiles.json"
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self._load_profiles()
    
    def _load_profiles(self) -> None:
        """Load profiles from disk."""
        try:
            if self.profiles_file.exists():
                with open(self.profiles_file, "r") as f:
                    self.profiles = json.load(f)
                logger.info(f"Loaded {len(self.profiles)} profiles")
            else:
                self.profiles = {}
        except Exception as e:
            logger.error(f"Failed to load profiles: {e}")
            self.profiles = {}
    
    def _save_profiles(self) -> None:
        """Save profiles to disk."""
        try:
            with open(self.profiles_file, "w") as f:
                json.dump(self.profiles, f, indent=2)
            logger.info("Profiles saved to disk")
        except Exception as e:
            logger.error(f"Failed to save profiles: {e}")
    
    def create_profile(
        self,
        name: str,
        broker: str,
        broker_config: Dict[str, Any],
        mode: str = "LOCAL",
        description: str = ""
    ) -> Dict[str, Any]:
        """Create a new quick launch profile.
        
        Args:
            name: Profile name (e.g., "Alpaca Trading")
            broker: Broker type (alpaca, binance, coinbase, etc.)
            broker_config: Broker credentials and settings
            mode: Storage mode (LOCAL or REMOTE)
            description: Optional profile description
        
        Returns:
            Created profile dictionary
        """
        profile = {
            "name": name,
            "broker": broker,
            "config": broker_config,
            "mode": mode,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "last_used": None,
        }
        
        self.profiles[name] = profile
        self._save_profiles()
        
        logger.info(f"Created profile: {name} ({broker})")
        return profile
    
    def update_profile(
        self,
        name: str,
        broker_config: Optional[Dict[str, Any]] = None,
        mode: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update an existing profile.
        
        Args:
            name: Profile name to update
            broker_config: Updated broker configuration
            mode: Updated storage mode
            description: Updated description
        
        Returns:
            Updated profile or None if not found
        """
        if name not in self.profiles:
            logger.warning(f"Profile not found: {name}")
            return None
        
        profile = self.profiles[name]
        
        if broker_config is not None:
            profile["config"] = broker_config
        
        if mode is not None:
            profile["mode"] = mode
        
        if description is not None:
            profile["description"] = description
        
        profile["updated_at"] = datetime.now().isoformat()
        
        self._save_profiles()
        logger.info(f"Updated profile: {name}")
        return profile
    
    def delete_profile(self, name: str) -> bool:
        """Delete a profile.
        
        Args:
            name: Profile name to delete
        
        Returns:
            True if deleted, False if not found
        """
        if name in self.profiles:
            del self.profiles[name]
            self._save_profiles()
            logger.info(f"Deleted profile: {name}")
            return True
        
        logger.warning(f"Profile not found: {name}")
        return False
    
    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a profile by name.
        
        Args:
            name: Profile name
        
        Returns:
            Profile dictionary or None if not found
        """
        return self.profiles.get(name)
    
    def list_profiles(self) -> Dict[str, Dict[str, Any]]:
        """List all profiles.
        
        Returns:
            Dictionary of all profiles
        """
        return self.profiles.copy()
    
    def mark_profile_used(self, name: str) -> None:
        """Mark a profile as recently used.
        
        Args:
            name: Profile name
        """
        if name in self.profiles:
            self.profiles[name]["last_used"] = datetime.now().isoformat()
            self._save_profiles()
    
    async def sync_profile_to_server(self, profile_name: str) -> bool:
        """Sync a profile to the server (remote mode).
        
        Args:
            profile_name: Profile name to sync
        
        Returns:
            True if successful, False otherwise
        """
        profile = self.get_profile(profile_name)
        if not profile:
            logger.error(f"Profile not found: {profile_name}")
            return False
        
        try:
            # Send broker config to server
            result = await self.server_api_client.save_broker_config(
                name=profile_name,
                broker=profile["broker"],
                config=profile["config"],
                description=profile.get("description", "")
            )
            
            if result:
                profile["mode"] = "REMOTE"
                profile["synced_at"] = datetime.now().isoformat()
                self._save_profiles()
                logger.info(f"Synced profile to server: {profile_name}")
                return True
            else:
                logger.error(f"Failed to sync profile: {profile_name}")
                return False
        
        except Exception as e:
            logger.error(f"Error syncing profile: {e}")
            return False
    
    async def sync_profile_from_server(self, profile_name: str) -> bool:
        """Load a profile from the server (remote mode).
        
        Args:
            profile_name: Profile name to load from server
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Load broker config from server
            config = await self.server_api_client.get_broker_config(profile_name)
            
            if config:
                self.profiles[profile_name] = {
                    "name": profile_name,
                    "broker": config.get("broker", ""),
                    "config": config.get("config", {}),
                    "mode": "REMOTE",
                    "loaded_from_server": True,
                    "synced_at": datetime.now().isoformat(),
                }
                self._save_profiles()
                logger.info(f"Loaded profile from server: {profile_name}")
                return True
            else:
                logger.error(f"Profile not found on server: {profile_name}")
                return False
        
        except Exception as e:
            logger.error(f"Error loading profile from server: {e}")
            return False
    
    async def sync_all_profiles_to_server(self) -> Dict[str, bool]:
        """Sync all local profiles to the server.
        
        Returns:
            Dictionary mapping profile names to sync status
        """
        results = {}
        
        for profile_name in self.profiles.keys():
            results[profile_name] = await self.sync_profile_to_server(profile_name)
        
        return results
    
    async def pull_profiles_from_server(self) -> Dict[str, bool]:
        """Pull all profiles from the server.
        
        Returns:
            Dictionary mapping profile names to load status
        """
        try:
            # Get list of available profiles on server
            server_profiles = await self.server_api_client.list_broker_configs()
            
            if not server_profiles:
                logger.warning("No profiles available on server")
                return {}
            
            results = {}
            for profile_data in server_profiles:
                profile_name = profile_data.get("name")
                if profile_name:
                    results[profile_name] = await self.sync_profile_from_server(profile_name)
            
            return results
        
        except Exception as e:
            logger.error(f"Error pulling profiles from server: {e}")
            return {}
    
    def export_profile(self, profile_name: str, file_path: str) -> bool:
        """Export a profile to a file.
        
        Args:
            profile_name: Profile name to export
            file_path: Destination file path
        
        Returns:
            True if successful, False otherwise
        """
        profile = self.get_profile(profile_name)
        if not profile:
            logger.error(f"Profile not found: {profile_name}")
            return False
        
        try:
            with open(file_path, "w") as f:
                json.dump(profile, f, indent=2)
            logger.info(f"Exported profile: {profile_name} to {file_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error exporting profile: {e}")
            return False
    
    def import_profile(self, file_path: str, new_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Import a profile from a file.
        
        Args:
            file_path: Source file path
            new_name: Optional new name for the profile
        
        Returns:
            Imported profile dictionary or None if failed
        """
        try:
            with open(file_path, "r") as f:
                profile = json.load(f)
            
            profile_name = new_name or profile.get("name", "imported_profile")
            self.profiles[profile_name] = profile
            self._save_profiles()
            
            logger.info(f"Imported profile: {profile_name} from {file_path}")
            return profile
        
        except Exception as e:
            logger.error(f"Error importing profile: {e}")
            return None
