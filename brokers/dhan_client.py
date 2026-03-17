"""Dhan broker client implementation."""

import requests
import logging
from typing import Dict, Optional, Any
from brokers.base_broker import BaseBroker

logger = logging.getLogger(__name__)


class DhanClient(BaseBroker):
    """Client for Dhan broker API."""
    
    def __init__(self, api_key: str, api_secret: str, access_token: str):
        """Initialize Dhan client."""
        super().__init__(api_key, api_secret, access_token)
        self.base_url = "https://api.dhan.co/v2"
        self.client_id = api_key
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "access-token": self.access_token,
            "Content-Type": "application/json",
        }
    
    def get_positions(self) -> Dict[str, Any]:
        """Get positions."""
        url = f"{self.base_url}/positions"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()
        
        # Dhan returns a list directly, normalize field names to match Upstox format
        if isinstance(data, list):
            normalized_positions = []
            
            for pos in data:
                # Debug: Print available fields for first position each call
                if not normalized_positions:
                    print(f"📊 Dhan position fields: {list(pos.keys())}")
                    print(f"   LTP field value: ltp={pos.get('ltp')}, lastPrice={pos.get('lastPrice')}, lastTradedPrice={pos.get('lastTradedPrice')}")
                    print(f"   Price fields: buyAvg={pos.get('buyAvg')}, costPrice={pos.get('costPrice')}, sellAvg={pos.get('sellAvg')}")
                    print(f"   Position type: positionType={pos.get('positionType')}, productType={pos.get('productType')}")
                    print(f"   🔍 Order identifiers: securityId={pos.get('securityId')}, tradingSymbol={pos.get('tradingSymbol')}")
                    print(f"   exchangeSegment={pos.get('exchangeSegment')}, netQty={pos.get('netQty')}, buyQty={pos.get('buyQty')}, sellQty={pos.get('sellQty')}")
                
                normalized = {
                    'tradingsymbol': pos.get('tradingSymbol', pos.get('securityId', 'N/A')),
                    'quantity': pos.get('netQty', pos.get('quantity', 0)),
                    'pnl': pos.get('realizedProfit', pos.get('unrealizedProfit', 0)),
                    'unrealised': pos.get('unrealizedProfit', 0),
                    'instrument_token': pos.get('securityId', ''),
                    'average_price': pos.get('buyPrice', pos.get('buyAvg', pos.get('costPrice', 0))),
                    'last_price': pos.get('ltp', pos.get('lastPrice', pos.get('lastTradedPrice', 0))),
                }
                # Add original data for reference (keeps buyPrice, netQty etc.)
                normalized.update(pos)
                normalized_positions.append(normalized)
            return {"data": normalized_positions}
        return data
    
    def get_holdings(self) -> Dict[str, Any]:
        """Get holdings."""
        url = f"{self.base_url}/holdings"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()
        # Dhan returns a list directly, wrap it in 'data' key for consistency
        if isinstance(data, list):
            return {"data": data}
        return data
    
    def get_funds_and_margin(self) -> Dict[str, Any]:
        """Get funds and margin."""
        url = f"{self.base_url}/fundlimit"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()
        
        # Dhan returns funds data directly, restructure to match expected format
        if isinstance(data, dict) and 'data' not in data:
            # Wrap in standard format with equity structure
            return {
                "data": {
                    "equity": {
                        "available_margin": data.get("availabelBalance", 0),
                        "used_margin": data.get("utilizedAmount", 0),
                    }
                }
            }
        return data
    
    def place_order(
        self,
        instrument_key: str,
        quantity: int,
        transaction_type: str,
        order_type: str,
        product: str,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        exchange_segment: Optional[str] = None,  # Allow passing exchange segment
        is_amo: bool = False,  # After Market Order flag
    ) -> Dict[str, Any]:
        """Place order."""
        url = f"{self.base_url}/orders"
        
        # Ensure quantity is integer
        quantity = int(quantity)
        
        # For SL-M orders, Dhan might require price = trigger_price
        if order_type == "SL-M" and trigger_price and not price:
            price = trigger_price
        
        # Map order types to Dhan API format
        # Based on error testing, Dhan might use "SL" not "STOP_LOSS"
        dhan_order_type_map = {
            "MARKET": "MARKET",
            "LIMIT": "LIMIT",
            "SL": "SL",           # Try "SL" instead of "STOP_LOSS"
            "SL-M": "SL-M"        # Try "SL-M" instead of "STOP_LOSS_MARKET"
        }
        dhan_order_type = dhan_order_type_map.get(order_type, order_type)
        
        # For STOP_LOSS orders, ensure trigger_price > price for SELL
        if dhan_order_type in ["SL", "STOP_LOSS"] and trigger_price:
            # Dhan format: For SELL stop loss, trigger > price (exit when market drops to trigger)
            if transaction_type == "SELL":
                price = trigger_price - 0.05  # Price below trigger for SELL
            elif not price:
                price = trigger_price + 0.05  # Price above trigger for BUY
        
        # Map product code to Dhan productType
        # I = Intraday, C = Carryforward/Normal
        product_type_map = {
            "I": "INTRADAY",
            "M": "INTRADAY",  # MIS -> INTRADAY
            "C": "NORMAL",     # CNC -> NORMAL
            "INTRADAY": "INTRADAY",
            "NORMAL": "NORMAL",
            "MTF": "MTF",
            "CO": "CO"
        }
        product_type = product_type_map.get(product, "INTRADAY")  # Default to INTRADAY
        
        # Use exchange segment from position or default to NSE_FNO
        if not exchange_segment:
            exchange_segment = "NSE_FNO"  # Default for F&O
        
        # Dhan API requires specific field names and values
        # For F&O: exchangeSegment = "NSE_FNO" (from position data)
        data = {
            "dhanClientId": self.client_id,
            "correlationId": "traderchamp",
            "transactionType": transaction_type,
            "exchangeSegment": exchange_segment,  # Use actual exchange segment
            "productType": product_type,  # Use mapped product type
            "orderType": dhan_order_type,  # Use STOP_LOSS format
            "validity": "DAY",
            "securityId": str(instrument_key),  # Ensure it's string
            "quantity": quantity,
            "disclosedQuantity": 0,
            "price": float(price) if price else 0.0,
            "triggerPrice": float(trigger_price) if trigger_price else 0.0,
            "afterMarketOrder": False
        }
        
        # Debug: Print order details for SL orders
        if order_type in ["SL", "SL-M"]:
            print(f"🔍 Dhan SL Order Data: orderType={order_type}, qty={quantity}, price={data['price']}, triggerPrice={data['triggerPrice']}, transactionType={transaction_type}")
            print(f"   Full request data: {data}")
            print(f"   🔍 Attempting to place STOP_LOSS order with securityId={instrument_key}")
        
        try:
            response = requests.post(url, json=data, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg = f"{e}"
            try:
                error_detail = e.response.json()
                # Include full request data in error for debugging
                error_msg = f"{e} - {error_detail} | Full request: {data}"
                
                # Add specific help for DH-905
                if error_detail.get('errorCode') == 'DH-905':
                    error_msg += f"\n   💡 DH-905 Troubleshooting:"
                    error_msg += f"\n      - SecurityId {instrument_key} might be invalid for orders"
                    error_msg += f"\n      - Try checking Dhan web/app if you can place manual SL for this contract"
                    error_msg += f"\n      - Quantity {quantity} might not match lot size requirements"
                
                # Add helpful message for Invalid Quantity error
                if 'Invalid Quantity' in str(error_detail):
                    error_msg += f"\n   💡 Tip: Dhan validates quantity against their lot size for this security."
                    error_msg += f"\n   Try multiples of lot size (e.g., 15, 30, 45 for BANKNIFTY or 25, 50, 75 for NIFTY)"
                
                # Add helpful message for not allowed error
                if 'not allowed' in str(error_detail).lower() or 'DH-906' in str(error_detail):
                    error_msg += f"\n   💡 Tip: Check if contract is expired or not yet active for trading."
                    error_msg += f"\n   Product type: MARGIN (F&O), Exchange: NSE_FNO"
            except:
                pass
            raise Exception(error_msg)
    
    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel order."""
        url = f"{self.base_url}/orders/{order_id}"
        response = requests.delete(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        order_type: Optional[str] = None,
        trigger_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Modify order."""
        url = f"{self.base_url}/orders/{order_id}"
        data = {}
        
        if quantity:
            data["quantity"] = quantity
        if price:
            data["price"] = price
        if order_type:
            data["orderType"] = order_type
        if trigger_price:
            data["triggerPrice"] = trigger_price
        
        response = requests.put(url, json=data, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def get_order_history(self, order_id: Optional[str] = None) -> Dict[str, Any]:
        """Get order history."""
        if order_id:
            url = f"{self.base_url}/orders/{order_id}"
        else:
            url = f"{self.base_url}/orders"
        
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()
        
        # Dhan returns a list directly, wrap it in 'data' key for consistency
        if isinstance(data, list):
            return {"data": data}
        return data
    
    def get_trade_history(self) -> Dict[str, Any]:
        """Get trade history (completed trades)."""
        url = f"{self.base_url}/trades"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()
        # Normalize response format
        if isinstance(data, list):
            return {"data": data}
        return data
    
    def get_market_quote(self, instrument_key: str) -> Dict[str, Any]:
        """Get market quote."""
        url = f"{self.base_url}/marketfeed/ltp"
        data = {"securityId": instrument_key}
        response = requests.post(url, json=data, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def get_profile(self) -> Dict[str, Any]:
        """Get user profile."""
        return {
            "data": {
                "user_name": "Dhan User",
                "email": "dhan@user.com",
                "client_id": self.client_id,
            }
        }
    
    def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        """Get option chain data for an index.
        
        Args:
            symbol: Index symbol like 'NIFTY', 'BANKNIFTY', 'SENSEX'
            expiry: Expiry date (optional)
        
        Returns:
            Dict with option chain data including strikes, OI, volume, prices
        """
        # Dhan uses security IDs for indices
        # NIFTY 50: 13, BANK NIFTY: 25, etc.
        index_security_ids = {
            'NIFTY': '13',
            'BANKNIFTY': '25',
            'SENSEX': '51'
        }
        
        security_id = index_security_ids.get(symbol, '13')
        
        # Dhan API endpoint for option chain
        url = f"{self.base_url}/optionchain"
        data = {
            "securityId": security_id,
            "expiryDate": expiry if expiry else ""
        }
        
        try:
            response = requests.post(url, json=data, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Option chain fetch failed: {e}")
            return {"status": "error", "message": str(e), "data": []}
