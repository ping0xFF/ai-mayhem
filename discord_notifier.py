#!/usr/bin/env python3
"""
Discord notification service for AI Mayhem briefs.

Uses discord.py library for proper Discord API integration.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import discord

from nodes.config import DISCORD_WEBHOOK_URL

class DiscordNotifier:
    """Discord notification service."""
    
    def __init__(self) -> None:
        """Initialize Discord notifier."""
        self._webhook: Optional[discord.Webhook] = None
    
    def is_enabled(self) -> bool:
        """Check if Discord notifications are enabled."""
        return DISCORD_WEBHOOK_URL is not None
    
    async def send_brief_notification(
        self,
        title: str,
        brief_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Send a Discord notification with brief content.
        
        Args:
            title: Notification title
            brief_text: The generated brief content  
            metadata: Additional metadata to include
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            ConfigurationError: If Discord is not properly configured
            NotificationError: If sending notification fails
        """
        if not self.is_enabled():
            return False
        
        try:
            webhook = await self._get_webhook()
            embed = self._create_embed(title, brief_text, metadata)
            
            await webhook.send(
                content=f"🤖 **{title}**",
                embed=embed
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Discord notification failed: {str(e)}")
            return False
    
    async def _get_webhook(self) -> discord.Webhook:
        """Get Discord webhook instance."""
        if not DISCORD_WEBHOOK_URL:
            raise ValueError("Discord webhook URL not configured")
        
        if self._webhook is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
            self._webhook = discord.Webhook.from_url(
                DISCORD_WEBHOOK_URL,
                session=self._session
            )
        
        return self._webhook
        
    async def __aenter__(self):
        """Async context manager entry."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if hasattr(self, '_session'):
            await self._session.close()
    
    def _create_embed(
        self,
        title: str,
        brief_text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> discord.Embed:
        """Create Discord embed for the brief."""
        embed = discord.Embed(
            title=title,
            description=brief_text,
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        embed.set_footer(text="AI Mayhem")
        
        # Add metadata fields
        if metadata:
            for key, value in metadata.items():
                embed.add_field(
                    name=key.replace('_', ' ').title(),
                    value=str(value),
                    inline=True
                )
        
        return embed


async def send_discord_notification(title: str, brief_text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """
    Simple function to send Discord notification.
    
    Args:
        title: Notification title
        brief_text: The generated brief content
        metadata: Additional metadata to include
        
    Returns:
        True if successful, False otherwise
    """
    async with DiscordNotifier() as notifier:
        return await notifier.send_brief_notification(title, brief_text, metadata)


async def test_discord_notification() -> bool:
    """Test Discord notification functionality."""
    if not DISCORD_WEBHOOK_URL:
        print("❌ Discord webhook URL not configured")
        return False
    
    test_brief = """🔍 Base Chain Activity Summary

Recent wallet activity shows increased DEX trading volume with 15 transactions across 3 major liquidity pools.

Key Signals:
- Volume signal: 0.75 (elevated)  
- Activity signal: 0.82 (high)
- Pool concentration: Uniswap V3 ETH/USDC

Recommendation: Monitor for potential arbitrage opportunities."""
    
    metadata = {
        'provider': 'alchemy',
        'execution_time': '12.34s',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    try:
        success = await notifier.send_brief_notification(
            title="AI Mayhem Test Brief",
            brief_text=test_brief,
            metadata=metadata
        )
        
        logger.info("Discord test completed", success=success)
        return success
        
    except Exception as e:
        logger.error("Discord test failed", error=str(e))
        return False

