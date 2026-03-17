"""Abstract base class for broker implementations."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class BaseBroker(ABC):
    """Abstract base class defining broker interface."""
    
    def __init__(self, api_key: str, api_secret: str, access_token: str):
        """Initialize broker with credentials."""
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
    
    @abstractmethod
    def place_order(
        self,
        instrument_key: str,
        quantity: int,
        transaction_type: str,
        order_type: str,
        product: str,
        price: Optional[float] = None,
    ) -> Dict:
        """Place an order."""
        pass
    
    @abstractmethod
    def get_positions(self) -> Dict:
        """Get current positions."""
        pass
    
    @abstractmethod
    def get_holdings(self) -> Dict:
        """Get holdings."""
        pass
    
    @abstractmethod
    def get_funds_and_margin(self) -> Dict:
        """Get available funds and margin."""
        pass
    
    @abstractmethod
    def get_market_quote(self, instrument_key: str) -> Dict:
        """Get market quote for instrument."""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order."""
        pass
    
    @abstractmethod
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        trigger_price: Optional[float] = None,
    ) -> Dict:
        """Modify an existing order."""
        pass
    
    @abstractmethod
    def get_order_history(self, order_id: Optional[str] = None) -> Dict:
        """Get order history."""
        pass
