"""Upstox broker client implementation."""

import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from brokers.base_broker import BaseBroker

logger = logging.getLogger(__name__)


class UpstoxClient(BaseBroker):
    """
    Upstox API Client for trading operations.
    
    Provides comprehensive trading functionality including:
    - Order placement, modification, and cancellation
    - Position and holdings management
    - Market data retrieval (LTP, quotes, historical candles)
    - Account information and margin details
    
    API Versions:
        - V3: Used for order placement (enhanced slicing support)
        - V2: Used for positions, market data, and other operations
    
    Attributes:
        base_url: V3 API endpoint (https://api-hft.upstox.com/v3)
        base_url_v2: V2 API endpoint (https://api.upstox.com/v2)
        access_token: OAuth2 access token for authentication
    """

    def __init__(self, api_key: str, api_secret: str, access_token: str):
        """
        Initialize Upstox API client.
        
        Args:
            api_key: Upstox API key from developer console
            api_secret: Upstox API secret
            access_token: OAuth2 access token (valid for 24 hours)
            
        Note:
            - Access token must be generated via OAuth2 flow
            - Token expires daily and requires regeneration
            - Inherits from BaseBroker for common interface
            
        Example:
            >>> client = UpstoxClient(
            ...     api_key='your_api_key',
            ...     api_secret='your_secret',
            ...     access_token='your_access_token'
            ... )
        """
        super().__init__(api_key, api_secret, access_token)
        self.base_url = "https://api-hft.upstox.com/v3"
        self.base_url_v2 = "https://api.upstox.com/v2"

    def _get_headers(self) -> Dict[str, str]:
        """
        Get HTTP request headers with authorization token.
        
        Returns:
            Dict containing Authorization header with Bearer token and Accept header.
            
        Note:
            - All Upstox API calls require this authorization header
            - Token expires after 24 hours and needs regeneration
        """
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def get_positions(self) -> Dict[str, Any]:
        """
        Fetch all current open positions from Upstox.
        
        Returns:
            Dict with position data including:
            - tradingsymbol: Symbol name
            - quantity: Position size (positive=long, negative=short)
            - average_price: Entry price
            - last_price: Current market price
            - pnl: Profit/Loss amount
            
        API Endpoint:
            GET /portfolio/short-term-positions
            
        Note:
            - Uses v2 API for positions
            - Normalizes average_price field across different response formats
            - Returns only intraday positions (not delivery)
        """
        url = f"{self.base_url_v2}/portfolio/short-term-positions"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        data = response.json()
        
        # Normalize Upstox position data to include average_price
        if data.get('status') == 'success' and 'data' in data:
            positions = []
            for pos in data.get('data', []):
                # Upstox uses 'average_price' but sometimes it's nested or missing
                # Add it at top level for easier access
                if 'average_price' not in pos or pos.get('average_price') == 0:
                    # Try to get from buy_price or other fields
                    pos['average_price'] = (pos.get('buy_price') or 
                                          pos.get('average_buy_price') or 
                                          pos.get('day_buy_price') or 
                                          pos.get('buy_avg') or 0)
                positions.append(pos)
            data['data'] = positions
        
        return data

    def get_holdings(self) -> Dict[str, Any]:
        """
        Fetch long-term holdings (delivery positions).
        
        Returns:
            Dict with holdings data including stocks held for delivery.
            
        API Endpoint:
            GET /portfolio/long-term-holdings
            
        Note:
            - Different from positions (which are intraday)
            - Holdings are carried forward overnight
        """
        url = f"{self.base_url_v2}/portfolio/long-term-holdings"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_funds_and_margin(self) -> Dict[str, Any]:
        """
        Get available funds and margin details.
        
        Returns:
            Dict containing:
            - available_margin: Cash available for trading
            - used_margin: Margin blocked in open positions
            - collateral: Total collateral value
            
        API Endpoint:
            GET /user/get-funds-and-margin
            
        Note:
            - Shows real-time margin availability
            - Used to prevent over-trading beyond available funds
        """
        url = f"{self.base_url_v2}/user/get-funds-and-margin"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def place_order(
        self,
        instrument_key: str,
        quantity: int,
        transaction_type: str,
        order_type: str,
        product: str,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        is_amo: bool = False,
    ) -> Dict[str, Any]:
        """
        Place a new order on Upstox.
        
        Args:
            instrument_key: Upstox instrument token (e.g., 'NSE_FO|12345')
            quantity: Number of shares/contracts to trade
            transaction_type: 'BUY' or 'SELL'
            order_type: 'MARKET', 'LIMIT', 'SL' (Stop Loss), 'SL-M' (Stop Loss Market)
            product: 'I' (Intraday) or 'D' (Delivery)
            price: Limit price (required for LIMIT orders)
            trigger_price: Trigger price (required for SL/SL-M orders)
            is_amo: After Market Order flag (for orders outside market hours)
            
        Returns:
            Dict with order confirmation containing order_id(s)
            
        API Endpoint:
            POST /order/place (v3 API)
            
        Note:
            - Uses v3 API for order placement
            - Auto-slicing enabled for freeze quantity handling
            - Returns multiple order_ids if order is sliced
            - For F&O: Use 'SL' (not 'SL-M') to ensure execution
        """
        url = f"{self.base_url}/order/place"
        
        # Upstox v3 API parameters
        data = {
            "quantity": quantity,
            "product": "D" if product == "D" else "I",  # D=Delivery, I=Intraday
            "validity": "DAY",
            "price": float(price) if price else 0.0,
            "tag": "traderchamp",
            "instrument_token": instrument_key,
            "order_type": order_type,
            "transaction_type": transaction_type,
            "disclosed_quantity": 0,
            "trigger_price": float(trigger_price) if trigger_price else 0.0,
            "is_amo": is_amo,  # Use parameter value
            "slice": True  # Enable auto-slicing for freeze quantity
        }

        try:
            print(f"📤 Upstox Order Request: {data}")  # Debug: Show exact request
            response = requests.post(url, json=data, headers=self._get_headers())
            response.raise_for_status()
            result = response.json()
            print(f"📥 Upstox Order Response: {result}")  # Debug: Show response
            
            # v3 API returns {"status": "success", "data": {"order_ids": [...]}}
            if result.get('status') == 'success' and result.get('data', {}).get('order_ids'):
                # Return in v2 format for compatibility
                return {
                    'status': 'success',
                    'data': {
                        'order_id': result['data']['order_ids'][0],  # First order ID
                        'order_ids': result['data']['order_ids']  # All IDs if sliced
                    }
                }
            return result
        except requests.exceptions.HTTPError as e:
            error_msg = f"{e}"
            try:
                error_detail = e.response.json()
                error_msg = f"{e} - {error_detail} | Sent: instrument_token={data['instrument_token']}, qty={data['quantity']}"
            except:
                pass
            raise Exception(error_msg)

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a pending order.
        
        Args:
            order_id: Unique order identifier from place_order response
            
        Returns:
            Dict with cancellation confirmation
            
        API Endpoint:
            DELETE /order/cancel
            
        Note:
            - Can only cancel orders with status 'pending', 'open', or 'trigger pending'
            - Cannot cancel 'complete' or 'rejected' orders
            - Upstox expects order_id as form data (not JSON)
        """
        url = f"{self.base_url_v2}/order/cancel"
        # Upstox expects order_id as form data, not JSON
        data = {"order_id": order_id}
        response = requests.delete(url, data=data, headers=self._get_headers())
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
        """
        Modify an existing pending order.
        
        Args:
            order_id: Order ID to modify
            quantity: New quantity (optional - keeps old if not provided)
            price: New limit price (optional)
            order_type: New order type (optional)
            trigger_price: New trigger price for SL orders (optional)
            
        Returns:
            Dict with modification confirmation
            
        API Endpoint:
            PUT /order/modify
            
        Note:
            - Can only modify pending orders
            - Provide only fields you want to change
            - Critical for updating SL order quantities when position increases
        """
        url = f"{self.base_url_v2}/order/modify"
        data = {"order_id": order_id}
        
        if quantity:
            data["quantity"] = quantity
        if price:
            data["price"] = price
        if order_type:
            data["order_type"] = order_type
        if trigger_price:
            data["trigger_price"] = trigger_price
        
        response = requests.put(url, json=data, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_order_history(self, order_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get order history/status.
        
        Args:
            order_id: Specific order ID (optional - fetches all if not provided)
            
        Returns:
            Dict with order details including:
            - order_id: Unique identifier
            - status: 'pending', 'complete', 'rejected', 'cancelled', 'trigger pending'
            - tradingsymbol: Instrument name
            - quantity: Order size
            - price: Limit/trigger price
            
        API Endpoint:
            GET /order/history (for specific order)
            GET /order/retrieve-all (for all orders)
            
        Note:
            - Use this to check if SL orders exist before placing new ones
            - Critical for preventing duplicate SL orders
        """
        if order_id:
            url = f"{self.base_url_v2}/order/history?order_id={order_id}"
        else:
            url = f"{self.base_url_v2}/order/retrieve-all"
        
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def get_trade_history(self) -> Dict[str, Any]:
        """
        Get today's executed trades (filled orders).
        
        Returns:
            Dict with trade execution details
            
        API Endpoint:
            GET /order/trades/get-trades-for-day
            
        Note:
            - Shows actual fills (not pending orders)
            - Used for calculating realized P&L
        """
        url = f"{self.base_url_v2}/order/trades/get-trades-for-day"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_market_quote(self, instrument_key: str) -> Dict[str, Any]:
        """
        Get detailed market quote for an instrument.
        
        Args:
            instrument_key: Upstox instrument token
            
        Returns:
            Dict with market data:
            - ltp: Last traded price
            - volume: Traded volume
            - ohlc: Open, High, Low, Close prices
            
        API Endpoint:
            GET /market-quote/quotes
            
        Note:
            - Used for real-time price checks before placing SL orders
            - More detailed than get_ltp()
        """
        url = f"{self.base_url_v2}/market-quote/quotes?instrument_key={instrument_key}"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()

    def get_profile(self) -> Dict[str, Any]:
        """
        Get user profile and account information.
        
        Returns:
            Dict with user details:
            - user_name: Account holder name
            - email: Email address
            - user_id: Unique user identifier
            
        API Endpoint:
            GET /user/profile
            
        Note:
            - Used for account verification
            - Called during app initialization
        """
        url = f"{self.base_url_v2}/user/profile"
        response = requests.get(url, headers=self._get_headers())
        response.raise_for_status()
        return response.json()
    
    def search_instrument(self, symbol: str) -> Dict[str, Any]:
        """
        Search for instrument by trading symbol.
        
        Args:
            symbol: Trading symbol to search (e.g., 'NIFTY25D162525800CE', 'RELIANCE')
            
        Returns:
            Dict containing matching instruments with:
            - instrument_key: Upstox instrument identifier
            - tradingsymbol: Display name
            - exchange: Trading exchange (NSE/BSE/NFO)
            
        API Endpoint:
            GET /market-quote/search
            
        Note:
            - Used for instrument discovery before placing orders
            - Returns multiple matches if symbol is ambiguous
            - V2 API endpoint
        """
        url = f"{self.base_url_v2}/market-quote/search?query={symbol}"
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Instrument search failed: {e}")
            return {"status": "error", "data": []}
    
    def get_ltp(self, instrument_key: str) -> Dict[str, Any]:
        """
        Get Last Traded Price for an instrument.
        
        Args:
            instrument_key: Upstox instrument identifier (e.g., 'NSE_INDEX|Nifty 50')
            
        Returns:
            Dict with LTP data:
            {'status': 'success', 'data': {instrument_key: {'last_price': 18500.25}}}
            
        API Endpoint:
            GET /market-quote/ltp
            
        Note:
            - Faster than get_market_quote() for price-only checks
            - Used for Auto SL trigger price calculation
            - Returns last traded price, not bid/ask
        """
        url = f"{self.base_url_v2}/market-quote/ltp?instrument_key={instrument_key}"
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"LTP fetch failed for {instrument_key}: {e}")
            return {"status": "error", "data": {}}
    
    def get_historical_candles(self, instrument_key: str, interval: str = "day", from_date: str = None, to_date: str = None) -> Dict[str, Any]:
        """
        Get historical candle/OHLC data for backtesting and analysis.
        
        Args:
            instrument_key: Upstox instrument identifier
            interval: Candle timeframe - '1minute', '5minute', '30minute', 'day', 'week', 'month'
            from_date: Start date in ISO format 'YYYY-MM-DD' (defaults to 7 days ago)
            to_date: End date in ISO format 'YYYY-MM-DD' (defaults to today)
            
        Returns:
            Dict with candle data:
            {
                'status': 'success', 
                'data': {
                    'candles': [
                        [timestamp, open, high, low, close, volume, oi],
                        ...
                    ]
                }
            }
            
        API Endpoint:
            GET /historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}
            
        Note:
            - Candles ordered newest to oldest
            - Timestamp is ISO 8601 format
            - OI (Open Interest) available for F&O instruments only
            - Limited to last 365 days of data
        """
        from datetime import datetime, timedelta
        
        # Default to last 7 days if not specified
        if not to_date:
            to_date = datetime.now().strftime('%Y-%m-%d')
        if not from_date:
            from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        url = f"{self.base_url_v2}/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}"
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"Historical data fetch failed: {e}")
            return {"status": "error", "data": {"candles": []}}
    
    def get_option_chain(self, symbol: str, expiry: Optional[str] = None) -> Dict[str, Any]:
        """
        Get option chain data for indices.
        
        Args:
            symbol: Index symbol ('NIFTY', 'BANKNIFTY', 'SENSEX')
            expiry: Expiry date 'YYYY-MM-DD' (optional - uses nearest expiry)
            
        Returns:
            Dict with option chain including strikes, OI, volume, Greeks
            
        API Endpoint:
            NOT DIRECTLY AVAILABLE - Upstox lacks dedicated option chain endpoint
            
        Note:
            - Upstox API does not provide a direct option chain endpoint
            - Alternative approaches:
              1. Use NSE website scraping for option chain data
              2. Fetch individual option contracts via market-quote/ltp
              3. Use pre-downloaded CSV of option instruments
            - Currently returns error to trigger fallback to sample/cached data
            
        Workaround:
            For actual implementation, consider:
            - Using Upstox instrument master CSV to identify all options
            - Batch-fetching LTP for each strike via get_ltp()
            - Constructing option chain from individual quotes
        """
        # Upstox doesn't have a direct option chain API endpoint
        # We need to use the historical option chain or market-quote/ltp endpoints
        # For now, return error to trigger fallback to sample data
        
        logger.info(f"Upstox option chain API not directly available for {symbol}")
        
        # Alternative: Use NSE's option chain (if implementing web scraping)
        # Or use Upstox market data API to fetch individual option contracts
        
        return {
            "status": "error", 
            "message": "Upstox API does not provide direct option chain endpoint. Use NSE website or individual market quotes.",
            "data": []
        }
