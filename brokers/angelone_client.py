"""Angel One (SmartAPI) broker client implementation."""

from typing import Dict, List, Optional
from .base_broker import BaseBroker

try:
    from smartapi import SmartConnect
    SMARTAPI_AVAILABLE = True
except ImportError:
    SMARTAPI_AVAILABLE = False
    SmartConnect = None


class AngelOneClient(BaseBroker):
    """Angel One broker client using SmartAPI."""
    
    def __init__(self, api_key: str, api_secret: str, access_token: str):
        """Initialize Angel One client."""
        if not SMARTAPI_AVAILABLE:
            raise ImportError("smartapi-python package not installed. Run: pip install smartapi-python")
        
        super().__init__(api_key, api_secret, access_token)
        self.smart_api = SmartConnect(api_key=api_key)
        # Note: For Angel One, you typically need to call generateSession with client code and password
        # This assumes access_token is the jwtToken received after login
        self.smart_api.setAccessToken(access_token)
    
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
        Place an order on Angel One.
        
        Args:
            instrument_key: Token or trading symbol
            quantity: Order quantity
            transaction_type: 'BUY' or 'SELL'
            order_type: 'MARKET' or 'LIMIT'
            product: 'INTRADAY' or 'DELIVERY'
            price: Limit price (for LIMIT orders)
        """
        try:
            order_params = {
                'variety': 'NORMAL',
                'tradingsymbol': instrument_key,
                'symboltoken': instrument_key,  # May need to be looked up
                'transactiontype': transaction_type,
                'exchange': 'NFO',
                'ordertype': order_type,
                'producttype': 'CARRYFORWARD' if product == 'NRML' else 'INTRADAY',
                'duration': 'DAY',
                'quantity': quantity,
            }
            
            if order_type == 'LIMIT' and price:
                order_params['price'] = price
            else:
                order_params['price'] = 0
            
            response = self.smart_api.placeOrder(order_params)
            
            return {
                'status': 'success' if response.get('status') else 'error',
                'data': response.get('data', {}),
                'message': response.get('message', '')
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def get_positions(self) -> Dict:
        """Get current positions."""
        try:
            response = self.smart_api.position()
            
            if response.get('status'):
                positions = response.get('data', [])
                
                # Normalize to common format
                normalized = []
                for pos in positions:
                    normalized.append({
                        'tradingsymbol': pos.get('tradingsymbol'),
                        'quantity': pos.get('netqty', 0),
                        'average_price': pos.get('avgprice', 0),
                        'last_price': pos.get('ltp', 0),
                        'pnl': pos.get('pnl', 0),
                        'unrealised': pos.get('unrealised', 0),
                        'realised': pos.get('realised', 0),
                        'instrument_token': pos.get('symboltoken', ''),
                        'exchange': pos.get('exchange', 'NFO'),
                        'product': pos.get('producttype', 'INTRADAY'),
                        'buyAvg': pos.get('totalbuyavgprice', 0),
                        'buyQty': pos.get('buyqty', 0),
                        'sellAvg': pos.get('totalsellavgprice', 0),
                        'sellQty': pos.get('sellqty', 0),
                    })
                
                return {
                    'status': 'success',
                    'data': normalized
                }
            else:
                return {
                    'status': 'error',
                    'message': response.get('message', 'Failed to fetch positions'),
                    'data': []
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
            response = self.smart_api.holding()
            return {
                'status': 'success' if response.get('status') else 'error',
                'data': response.get('data', []),
                'message': response.get('message', '')
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
            response = self.smart_api.rmsLimit()
            
            if response.get('status'):
                data = response.get('data', {})
                
                return {
                    'status': 'success',
                    'data': {
                        'equity': {
                            'available_margin': float(data.get('availablecash', 0)),
                            'used_margin': float(data.get('utilisedpayout', 0)),
                        }
                    }
                }
            else:
                return {
                    'status': 'error',
                    'message': response.get('message', 'Failed to fetch funds'),
                    'data': {'equity': {'available_margin': 0, 'used_margin': 0}}
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
            response = self.smart_api.ltpData('NFO', instrument_key, instrument_key)
            return {
                'status': 'success' if response.get('status') else 'error',
                'data': response.get('data', {}),
                'message': response.get('message', '')
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order."""
        try:
            response = self.smart_api.cancelOrder(order_id, variety='NORMAL')
            return {
                'status': 'success' if response.get('status') else 'error',
                'message': response.get('message', 'Order cancelled')
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
            params = {
                'variety': 'NORMAL',
                'orderid': order_id,
            }
            if quantity:
                params['quantity'] = quantity
            if price:
                params['price'] = price
            if order_type:
                params['ordertype'] = order_type
            
            response = self.smart_api.modifyOrder(params)
            return {
                'status': 'success' if response.get('status') else 'error',
                'message': response.get('message', 'Order modified')
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
                response = self.smart_api.orderBook()  # Angel One doesn't have individual order history
                orders = [o for o in response.get('data', []) if o.get('orderid') == order_id]
            else:
                response = self.smart_api.orderBook()
                orders = response.get('data', [])
            
            return {
                'status': 'success' if response.get('status') else 'error',
                'data': orders,
                'message': response.get('message', '')
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'data': []
            }
