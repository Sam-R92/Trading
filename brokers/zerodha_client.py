"""Zerodha (Kite Connect) broker client implementation."""

from typing import Dict, List, Optional
from .base_broker import BaseBroker

try:
    from kiteconnect import KiteConnect
    KITECONNECT_AVAILABLE = True
except ImportError:
    KITECONNECT_AVAILABLE = False
    KiteConnect = None


class ZerodhaClient(BaseBroker):
    """Zerodha broker client using Kite Connect API."""
    
    def __init__(self, api_key: str, api_secret: str, access_token: str):
        """Initialize Zerodha client."""
        if not KITECONNECT_AVAILABLE:
            raise ImportError("kiteconnect package not installed. Run: pip install kiteconnect")
        
        super().__init__(api_key, api_secret, access_token)
        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)
    
    def place_order(
        self,
        instrument_key: str,
        quantity: int,
        transaction_type: str,
        order_type: str,
        product: str,
        price: Optional[float] = None,
        is_amo: bool = False,  # After Market Order flag
    ) -> Dict:
        """
        Place an order on Zerodha.
        
        Args:
            instrument_key: Trading symbol (e.g., 'NIFTY24DEC25900CE')
            quantity: Order quantity
            transaction_type: 'BUY' or 'SELL'
            order_type: 'MARKET' or 'LIMIT'
            product: 'MIS' (intraday) or 'NRML' (normal)
            price: Limit price (for LIMIT orders)
        """
        try:
            order_params = {
                'tradingsymbol': instrument_key,
                'exchange': 'NFO',
                'transaction_type': transaction_type,
                'quantity': quantity,
                'order_type': order_type,
                'product': product,
                'validity': 'DAY',
            }
            
            if order_type == 'LIMIT' and price:
                order_params['price'] = price
            
            order_id = self.kite.place_order(variety=self.kite.VARIETY_REGULAR, **order_params)
            
            return {
                'status': 'success',
                'data': {'order_id': order_id}
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_positions(self) -> Dict:
        """Get current positions."""
        try:
            positions = self.kite.positions()
            # Combine day and net positions
            all_positions = positions.get('day', []) + positions.get('net', [])
            
            # Normalize to common format
            normalized = []
            for pos in all_positions:
                normalized.append({
                    'tradingsymbol': pos.get('tradingsymbol'),
                    'quantity': pos.get('quantity', 0),
                    'average_price': pos.get('average_price', 0),
                    'last_price': pos.get('last_price', 0),
                    'pnl': pos.get('pnl', 0),
                    'unrealised': pos.get('unrealised', 0),
                    'realised': pos.get('realised', 0),
                    'instrument_token': str(pos.get('instrument_token', '')),
                    'exchange': pos.get('exchange', 'NFO'),
                    'product': pos.get('product', 'MIS'),
                })
            
            return {
                'status': 'success',
                'data': normalized
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'data': []
            }
    
    def get_holdings(self) -> Dict:
        """Get holdings."""
        try:
            holdings = self.kite.holdings()
            return {
                'status': 'success',
                'data': holdings
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'data': []
            }
    
    def get_funds_and_margin(self) -> Dict:
        """Get available funds and margin."""
        try:
            margins = self.kite.margins()
            equity = margins.get('equity', {})
            
            return {
                'status': 'success',
                'data': {
                    'equity': {
                        'available_margin': equity.get('available', {}).get('live_balance', 0),
                        'used_margin': equity.get('utilised', {}).get('debits', 0),
                    }
                }
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'data': {'equity': {'available_margin': 0, 'used_margin': 0}}
            }
    
    def get_market_quote(self, instrument_key: str) -> Dict:
        """Get market quote for instrument."""
        try:
            quote = self.kite.quote([f"NFO:{instrument_key}"])
            return {
                'status': 'success',
                'data': quote
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order."""
        try:
            self.kite.cancel_order(variety=self.kite.VARIETY_REGULAR, order_id=order_id)
            return {
                'status': 'success',
                'message': 'Order cancelled successfully'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
    ) -> Dict:
        """Modify an existing order."""
        try:
            params = {}
            if quantity:
                params['quantity'] = quantity
            if price:
                params['price'] = price
            if order_type:
                params['order_type'] = order_type
            
            self.kite.modify_order(variety=self.kite.VARIETY_REGULAR, order_id=order_id, **params)
            return {
                'status': 'success',
                'message': 'Order modified successfully'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_order_history(self, order_id: Optional[str] = None) -> Dict:
        """Get order history."""
        try:
            if order_id:
                orders = self.kite.order_history(order_id=order_id)
            else:
                orders = self.kite.orders()
            
            return {
                'status': 'success',
                'data': orders
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'data': []
            }
