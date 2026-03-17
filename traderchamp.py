"""Traderchamp - Multi-Broker Trading Tool.

Fast trading with Dhan and Upstox brokers.
"""

import os
import sys
import logging
from typing import Dict, Optional, List
from dotenv import load_dotenv
from brokers.upstox_client import UpstoxClient
from brokers.dhan_client import DhanClient

# Optional broker imports - only available if dependencies installed
try:
    from brokers.zerodha_client import ZerodhaClient
    ZERODHA_AVAILABLE = True
except ImportError:
    ZERODHA_AVAILABLE = False
    ZerodhaClient = None

try:
    from brokers.angelone_client import AngelOneClient
    ANGELONE_AVAILABLE = True
except ImportError:
    ANGELONE_AVAILABLE = False
    AngelOneClient = None
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import gzip
import csv
from pathlib import Path
import threading
import requests
import csv
from io import StringIO

# Setup logging
logging.getLogger().setLevel(logging.WARNING)


class Traderchamp:
    """Main trading application."""
    
    def __init__(self):
        """Initialize Traderchamp."""
        load_dotenv()
        self.current_broker = None
        self.current_client = None
        self.account_name = None
        
        # Multi-account support
        self.active_brokers = {}  # {broker_name: client}
        self.multi_account_mode = False
        
        # Instrument cache
        self.dhan_instruments = {}  # Cache for Dhan security IDs
        self.upstox_instruments = {}  # Cache for Upstox tokens
        self.instrument_lot_sizes = {}  # Cache: "broker_INDEX_EXPIRY_STRIKE_TYPE" -> actual lot size
        
        # Stop Loss tracking
        self.active_stop_losses = {}  # {position_key: {config, current_sl, highest_price}}
        self.stop_loss_monitor_thread = None
        self.stop_loss_monitor_active = False
        
        # Index configurations with lot sizes and contract limits
        self.indices = {
            "1": {
                "name": "NIFTY", 
                "symbol": "NSE_FO|NIFTY", 
                "lot_size": 65,  # Changed from 75 to 65 (Jan 2026 series)
                "min_lots": 1,
                "max_lots": 13,  # 845 contracts max (65*13=845)
                "freeze_qty": 845
            },
            "2": {
                "name": "BANKNIFTY", 
                "symbol": "NSE_FO|BANKNIFTY", 
                "lot_size": 30,  # Changed from 35 to 30 (Jan 2026 series)
                "min_lots": 1,
                "max_lots": 30,  # 900 contracts max (30*30=900)
                "freeze_qty": 900
            },
            "3": {
                "name": "SENSEX", 
                "symbol": "BSE_FO|SENSEX", 
                "lot_size": 20,  # No change for Jan 2026
                "min_lots": 1,
                "max_lots": 45,  # 900 contracts max (20*45=900)
                "freeze_qty": 900
            },
            "4": {
                "name": "FINNIFTY", 
                "symbol": "NSE_FO|FINNIFTY", 
                "lot_size": 60,  # Changed from 65 to 60 (Jan 2026 series)
                "min_lots": 1,
                "max_lots": 15,  # 900 contracts max (60*15=900)
                "freeze_qty": 900
            },
            "5": {
                "name": "MIDCPNIFTY", 
                "symbol": "NSE_FO|MIDCPNIFTY", 
                "lot_size": 120,  # Changed from 140 to 120 (Jan 2026 series)
                "min_lots": 1,
                "max_lots": 7,  # 840 contracts max (120*7=840)
                "freeze_qty": 840
            },
        }
        
        # Instrument master data
        # Get correct data directory for frozen mode
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = Path(app_dir) / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.upstox_master_file = self.data_dir / "upstox_instruments.csv"
        self.dhan_master_file = self.data_dir / "dhan_instruments.csv"
        self.upstox_master = None
        self.dhan_master = None
    
    def select_broker(self):
        """Select and initialize broker(s)."""
        print("\n" + "="*60)
        print("🔧 SELECT TRADING MODE")
        print("="*60)
        print("1. Single Account (Upstox)")
        print("2. Single Account (Dhan)")
        print("3. 🚀 MULTI-ACCOUNT (Both Upstox + Dhan in parallel)")
        print("="*60)
        
        choice = input("\nSelect mode (1-3): ").strip()
        
        if choice == "1":
            self.multi_account_mode = False
            self.current_broker = "upstox"
            self._init_upstox()
        elif choice == "2":
            self.multi_account_mode = False
            self.current_broker = "dhan"
            self._init_dhan()
        elif choice == "3":
            self.multi_account_mode = True
            return self._init_multi_account()
        else:
            print("❌ Invalid choice")
            return False
        
        return True
    
    def _init_upstox(self):
        """Initialize Upstox client."""
        api_key = os.getenv("UPSTOX_API_KEY")
        api_secret = os.getenv("UPSTOX_API_SECRET")
        access_token = os.getenv("UPSTOX_ACCESS_TOKEN")
        self.account_name = os.getenv("UPSTOX_ACCOUNT_NAME", "Upstox User")
        
        if not all([api_key, api_secret, access_token]):
            print("❌ Upstox credentials missing in .env file")
            return
        
        self.current_client = UpstoxClient(api_key, api_secret, access_token)
        print(f"✅ Connected to Upstox as {self.account_name}")
    
    def _init_dhan(self):
        """Initialize Dhan client."""
        client_id = os.getenv("DHAN_CLIENT_ID")
        access_token = os.getenv("DHAN_ACCESS_TOKEN")
        self.account_name = os.getenv("DHAN_ACCOUNT_NAME", "Dhan User")
        
        if not all([client_id, access_token]):
            print("❌ Dhan credentials missing in .env file")
            return
        
        self.current_client = DhanClient(client_id, "", access_token)
        print(f"✅ Connected to Dhan as {self.account_name}")
    
    def _init_multi_account(self):
        """Initialize multiple broker accounts for parallel trading (up to 5 brokers)."""
        print("\n🚀 Initializing Multi-Account Mode...")
        print("="*60)
        
        success_count = 0
        
        # 1. Initialize Upstox
        api_key = os.getenv("UPSTOX_API_KEY")
        api_secret = os.getenv("UPSTOX_API_SECRET")
        access_token = os.getenv("UPSTOX_ACCESS_TOKEN")
        upstox_name = os.getenv("UPSTOX_ACCOUNT_NAME", "Upstox User")
        
        if all([api_key, api_secret, access_token]):
            try:
                upstox_client = UpstoxClient(api_key, api_secret, access_token)
                self.active_brokers['upstox'] = {
                    'client': upstox_client,
                    'name': upstox_name
                }
                print(f"✅ Upstox account setup: {upstox_name}")
                success_count += 1
            except Exception as e:
                print(f"❌ Upstox failed: {e}")
        else:
            print("⚠️  Upstox credentials missing")
        
        # 2. Initialize Dhan
        client_id = os.getenv("DHAN_CLIENT_ID")
        dhan_token = os.getenv("DHAN_ACCESS_TOKEN")
        dhan_name = os.getenv("DHAN_ACCOUNT_NAME", "Dhan User")
        
        if all([client_id, dhan_token]):
            try:
                dhan_client = DhanClient(client_id, "", dhan_token)
                self.active_brokers['dhan'] = {
                    'client': dhan_client,
                    'name': dhan_name
                }
                print(f"✅ Dhan account setup: {dhan_name}")
                success_count += 1
            except Exception as e:
                print(f"❌ Dhan failed: {e}")
        else:
            print("⚠️  Dhan credentials missing")
        
        # 3. Initialize Zerodha
        zerodha_api_key = os.getenv("ZERODHA_API_KEY")
        zerodha_api_secret = os.getenv("ZERODHA_API_SECRET")
        zerodha_token = os.getenv("ZERODHA_ACCESS_TOKEN")
        zerodha_name = os.getenv("ZERODHA_ACCOUNT_NAME", "Zerodha User")
        
        if all([zerodha_api_key, zerodha_token]):
            if not ZERODHA_AVAILABLE:
                print("⚠️  Zerodha credentials found but kiteconnect not installed")
                print("   Run: pip install kiteconnect")
            else:
                try:
                    zerodha_client = ZerodhaClient(zerodha_api_key, zerodha_api_secret or "", zerodha_token)
                    self.active_brokers['zerodha'] = {
                        'client': zerodha_client,
                        'name': zerodha_name
                    }
                    print(f"✅ Zerodha account setup: {zerodha_name}")
                    success_count += 1
                except Exception as e:
                    print(f"❌ Zerodha failed: {e}")
        
        # 4. Initialize Angel One
        angel_api_key = os.getenv("ANGELONE_API_KEY")
        angel_api_secret = os.getenv("ANGELONE_API_SECRET")
        angel_token = os.getenv("ANGELONE_ACCESS_TOKEN")
        angel_name = os.getenv("ANGELONE_ACCOUNT_NAME", "Angel One User")
        
        if all([angel_api_key, angel_token]):
            if not ANGELONE_AVAILABLE:
                print("⚠️  Angel One credentials found but smartapi-python not installed")
                print("   Run: pip install smartapi-python")
            else:
                try:
                    angel_client = AngelOneClient(angel_api_key, angel_api_secret or "", angel_token)
                    self.active_brokers['angelone'] = {
                        'client': angel_client,
                        'name': angel_name
                    }
                    print(f"✅ Angel One account setup: {angel_name}")
                    success_count += 1
                except Exception as e:
                    print(f"❌ Angel One failed: {e}")
        
        print("="*60)
        
        if success_count == 0:
            print("❌ No brokers connected")
            return False
        
        print(f"✅ Multi-Account Mode Active: {success_count} broker(s) ready")
        return True
    
    def download_instrument_masters(self):
        """Download instrument master files from brokers if outdated."""
        print("\n🔄 Checking instrument masters...")
        
        # Check if files need update (older than 7 days)
        def needs_update(file_path):
            if not file_path.exists():
                return True
            file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
            return file_age.days >= 7
        
        # Download Upstox instruments
        if needs_update(self.upstox_master_file):
            try:
                print("  📥 Downloading Upstox instruments...")
                url = "https://assets.upstox.com/market-quote/instruments/exchange/complete.csv.gz"
                response = requests.get(url, timeout=30, stream=True)
                response.raise_for_status()
                
                # Decompress and save
                import io
                with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as f_in:
                    with open(self.upstox_master_file, 'wb') as f_out:
                        f_out.write(f_in.read())
                
                print("  ✅ Upstox instruments updated")
            except Exception as e:
                print(f"  ⚠️  Upstox download failed: {e}")
        else:
            print("  ✅ Upstox instruments up to date")
        
        # Download Dhan instruments
        if needs_update(self.dhan_master_file):
            try:
                print("  📥 Downloading Dhan instruments...")
                url = "https://images.dhan.co/api-data/api-scrip-master.csv"
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                with open(self.dhan_master_file, 'wb') as f:
                    f.write(response.content)
                
                print("  ✅ Dhan instruments updated")
            except Exception as e:
                print(f"  ⚠️  Dhan download failed: {e}")
        else:
            print("  ✅ Dhan instruments up to date")
    
    def load_instrument_masters(self):
        """Load instrument masters into memory for fast lookup."""
        if self.upstox_master is None and self.upstox_master_file.exists():
            print("  📖 Loading Upstox instruments...")
            self.upstox_master = {}
            try:
                with open(self.upstox_master_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Load index options (OPTIDX) and currency options (OPTCUR)
                        instrument_type = row.get('instrument_type', '')
                        if instrument_type in ['OPTIDX', 'OPTCUR'] and row.get('exchange') in ['NSE_FO', 'BSE_FO', 'NCD_FO']:
                            symbol = row.get('tradingsymbol', '')  # Note: lowercase 'tradingsymbol'
                            token = row.get('instrument_key', '')
                            if symbol and token:
                                self.upstox_master[symbol] = token
                print(f"  ✅ Loaded {len(self.upstox_master)} Upstox options")
            except Exception as e:
                print(f"  ⚠️  Failed to load Upstox master: {e}")
        
        if self.dhan_master is None and self.dhan_master_file.exists():
            print("  📖 Loading Dhan instruments...")
            self.dhan_master = {}
            try:
                with open(self.dhan_master_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    
                    # Debug: Print column names from first row
                    first_row = True
                    
                    for row in reader:
                        if first_row:
                            print(f"  📋 CSV Columns: {', '.join(row.keys())}")
                            first_row = False
                        
                        # Filter for NSE options
                        if row.get('SEM_INSTRUMENT_NAME') == 'OPTIDX' and row.get('SEM_EXM_EXCH_ID') == 'NSE':
                            # Try different column names for the trading symbol
                            # The actual trading symbol is in format "NIFTY 23 DEC 26050 CALL"
                            symbol = (row.get('SEM_CUSTOM_SYMBOL') or 
                                     row.get('SEM_TRADING_SYMBOL_NAME') or 
                                     row.get('SEM_TRADING_SYMBOL') or 
                                     row.get('TRADING_SYMBOL') or '')
                            
                            security_id = row.get('SEM_SMST_SECURITY_ID', '')
                            lot_size = row.get('SEM_LOT_UNITS', '').strip()
                            expiry_date = row.get('SEM_EXPIRY_DATE', '')  # DD/MM/YYYY HH:MM format
                            
                            if symbol and security_id:
                                # Parse lot size - handle various formats
                                try:
                                    lot_size_int = int(float(lot_size)) if lot_size else 0
                                except ValueError:
                                    lot_size_int = 0
                                
                                # Store using the display symbol format
                                self.dhan_master[symbol] = {
                                    'security_id': security_id,
                                    'lot_size': lot_size_int,
                                    'expiry_date': expiry_date,
                                    'exchange': row.get('SEM_EXM_EXCH_ID', 'NSE')
                                }
                print(f"  ✅ Loaded {len(self.dhan_master)} Dhan options")
            except Exception as e:
                print(f"  ⚠️  Failed to load Dhan master: {e}")
    
    def lookup_instrument(self, broker_name, index_name, expiry, strike, option_type):
        """Lookup instrument from master files.
        
        Returns: (instrument_key, lot_size) or (None, None)
        """
        # Handle both upstox and upstox2 (multiple Upstox accounts)
        if broker_name in ['upstox', 'upstox2']:
            if self.upstox_master is None:
                return None, None
            
            # Upstox format differs for monthly vs weekly expiries:
            # Monthly: NIFTY25DEC25950CE (no day)
            # Weekly: NIFTY2601062465 0PE (includes day: YYMMDD)
            try:
                expiry_date = datetime.strptime(expiry, "%d%b%y")
                year = expiry_date.strftime("%y")  # 25
                month_abb = expiry_date.strftime("%b").upper()  # DEC
                day = expiry_date.strftime("%d")  # 30
                month = expiry_date.strftime("%m")  # 12
                
                # Try MONTHLY format first (no day): NIFTY25DEC25950CE
                symbol_monthly = f"{index_name}{year}{month_abb}{strike}{option_type}"
                print(f"  🔍 Upstox (monthly): {symbol_monthly}")
                
                if symbol_monthly in self.upstox_master:
                    token = self.upstox_master[symbol_monthly]
                    print(f"  ✅ Upstox match: {symbol_monthly} → {token}")
                    return token, None
                
                # Try WEEKLY format (with day): NIFTY26010624650PE (YYMMDD format)
                symbol_weekly = f"{index_name}{year}{month}{day}{strike}{option_type}"
                print(f"  🔍 Upstox (weekly): {symbol_weekly}")
                
                if symbol_weekly in self.upstox_master:
                    token = self.upstox_master[symbol_weekly]
                    print(f"  ✅ Upstox match: {symbol_weekly} → {token}")
                    return token, None
                
                # Fuzzy search as fallback
                print(f"  🔍 Fuzzy searching Upstox CSV...")
                
                # Try to find ANY symbol matching the criteria
                for sym, token in self.upstox_master.items():
                    if (sym.startswith(f"{index_name}{year}") and
                        str(strike) in sym and 
                        sym.endswith(option_type)):
                        # Additional check: month abbreviation should be in symbol for monthly
                        if month_abb in sym.upper():
                            print(f"  ✅ Upstox fuzzy match: {sym} → {token}")
                            return token, None
                
                return None, None
            except Exception as e:
                print(f"  ⚠️  Upstox lookup error: {e}")
                return None, None
        
        elif broker_name == 'dhan':
            if self.dhan_master is None:
                return None, None
            
            # Dhan CSV format: NIFTY 16 DEC 26050 PUT (not NIFTY-Dec2025-26050-PE)
            try:
                expiry_date = datetime.strptime(expiry, "%d%b%y")
                day_no_zero = expiry_date.strftime("%d").lstrip('0')  # 23
                day_with_zero = expiry_date.strftime("%d")  # 23
                month = expiry_date.strftime("%b").upper()  # DEC (uppercase)
                year = expiry_date.strftime("%Y")   # 2025
                
                # Convert CE/PE to CALL/PUT
                option_name = "CALL" if option_type == "CE" else "PUT"
                
                # Try multiple format variations
                symbol_formats = [
                    f"{index_name} {day_no_zero} {month} {strike} {option_name}",  # "NIFTY 23 DEC 27000 PUT"
                    f"{index_name} {day_with_zero} {month} {strike} {option_name}",  # "NIFTY 23 DEC 27000 PUT"
                    f"{index_name} {day_no_zero} {month.title()} {strike} {option_name}",  # "NIFTY 23 Dec 27000 PUT"
                    f"{index_name} {day_with_zero} {month.title()} {strike} {option_name}",  # "NIFTY 23 Dec 27000 PUT"
                ]
                
                print(f"  🔍 Looking for: {symbol_formats[0]} (or variations)")
                
                # Try all format variations
                for symbol in symbol_formats:
                    if symbol in self.dhan_master:
                        data = self.dhan_master[symbol]
                        
                        # Validate expiry date
                        contract_expiry = data.get('expiry_date', '')
                        if contract_expiry:
                            try:
                                # Parse date - handle both DD/MM/YYYY HH:MM and YYYY-MM-DD formats
                                date_str = contract_expiry.split()[0] if ' ' in contract_expiry else contract_expiry
                                
                                # Try YYYY-MM-DD format first
                                try:
                                    contract_expiry_dt = datetime.strptime(date_str, "%Y-%m-%d")
                                except ValueError:
                                    # Try DD/MM/YYYY format
                                    contract_expiry_dt = datetime.strptime(date_str, "%d/%m/%Y")
                                
                                today = datetime.now()
                                
                                # Check if expiry matches what user selected
                                if contract_expiry_dt.date() != expiry_date.date():
                                    print(f"  ⚠️  Found {symbol} (ID: {data['security_id']}) but expiry mismatch:")
                                    print(f"      CSV has: {contract_expiry_dt.strftime('%d-%b-%y')} ({contract_expiry_dt.date()})")
                                    print(f"      You selected: {expiry} ({expiry_date.date()})")
                                    continue  # Try next format or search
                                else:
                                    # Expiry matches!
                                    if contract_expiry_dt.date() < today.date():
                                        print(f"  ⚠️  Contract expired on {contract_expiry_dt.strftime('%d-%b-%Y')}")
                                        return None, None
                                    
                                    print(f"  ✅ Exact match: {symbol} (ID: {data['security_id']}, Lot: {data['lot_size']})")
                                    return data['security_id'], data['lot_size']
                            except Exception as date_err:
                                print(f"  ⚠️  Date validation error: {date_err} (raw: {contract_expiry})")
                                # Continue to next format or search
                        else:
                            # No expiry date in CSV - return what we found
                            print(f"  ✅ Found {symbol} (ID: {data['security_id']}, Lot: {data['lot_size']}) - no expiry validation")
                            return data['security_id'], data['lot_size']
                
                # Symbol not found or expiry mismatch - try alternate search by matching expiry date
                print(f"  🔍 Searching for {index_name} strike {strike} {option_type} expiring on {expiry_date.strftime('%d-%b-%y')}...")
                matches = []
                
                option_name = "CALL" if option_type == "CE" else "PUT"
                
                for sym, data in self.dhan_master.items():
                    # Check if symbol matches pattern: "NIFTY * * STRIKE PUT/CALL"
                    if sym.startswith(index_name) and option_name in sym and str(strike) in sym:
                        contract_expiry = data.get('expiry_date', '')
                        if contract_expiry:
                            try:
                                date_str = contract_expiry.split()[0] if ' ' in contract_expiry else contract_expiry
                                
                                # Try both date formats
                                try:
                                    contract_expiry_dt = datetime.strptime(date_str, "%Y-%m-%d")
                                except ValueError:
                                    contract_expiry_dt = datetime.strptime(date_str, "%d/%m/%Y")
                                
                                if contract_expiry_dt.date() == expiry_date.date():
                                    matches.append({
                                        'symbol': sym,
                                        'security_id': data['security_id'],
                                        'lot_size': data['lot_size'],
                                        'expiry': contract_expiry_dt
                                    })
                            except:
                                continue
                
                if matches:
                    # If multiple matches, show them and pick the first one
                    if len(matches) > 1:
                        print(f"  ⚠️  Found {len(matches)} matching contracts:")
                        for m in matches:
                            print(f"      {m['symbol']} (ID: {m['security_id']}, Lot: {m['lot_size']})")
                    
                    selected = matches[0]
                    print(f"  ✅ Using: {selected['symbol']} (ID: {selected['security_id']}, Lot: {selected['lot_size']})")
                    return selected['security_id'], selected['lot_size']
                
                return None, None
            except Exception as e:
                print(f"  ⚠️  Dhan lookup error: {e}")
                return None, None
        
        return None, None
    
    def get_current_expiries(self, index_name=None):
        """Get next 4-5 upcoming expiries from Dhan master file or calculate.
        
        Args:
            index_name: Optional index name to filter expiries (e.g., 'NIFTY', 'SENSEX')
        """
        expiries = []
        
        # Try to get actual expiries from Dhan master if loaded
        if self.dhan_master:
            today = datetime.now()
            unique_expiries = set()
            
            # Determine which index to search for (CSV format: "NIFTY 16 DEC 26000 PUT")
            search_prefix = f"{index_name} " if index_name else "NIFTY "
            
            # Extract all future expiry dates from Dhan master
            for symbol, data in self.dhan_master.items():
                if symbol.startswith(search_prefix):  # Look at specific index contracts
                    expiry_str = data.get('expiry_date', '')
                    if expiry_str:
                        try:
                            # Parse date
                            date_str = expiry_str.split()[0] if ' ' in expiry_str else expiry_str
                            try:
                                expiry_dt = datetime.strptime(date_str, "%Y-%m-%d")
                            except ValueError:
                                expiry_dt = datetime.strptime(date_str, "%d/%m/%Y")
                            
                            # Include today and future dates (allow trading until 3:30 PM)
                            if expiry_dt.date() >= today.date():
                                unique_expiries.add(expiry_dt.date())
                        except:
                            continue
            
            # Sort and take first 5 upcoming expiries
            if unique_expiries:
                sorted_expiries = sorted(list(unique_expiries))[:5]
                expiries = [exp.strftime("%d%b%y").upper() for exp in sorted_expiries]
                
                if expiries:
                    return expiries
        
        # Fallback: Calculate expiries based on exchange and index
        # Effective Sep 1, 2025:
        # - NIFTY/BANKNIFTY/FINNIFTY (NSE): Tuesday expiries
        # - SENSEX (BSE): Thursday expiries
        today = datetime.now()
        
        # Determine expiry day based on index
        if index_name == 'SENSEX':
            expiry_weekday = 3  # Thursday
        else:
            expiry_weekday = 1  # Tuesday (NIFTY, BANKNIFTY, FINNIFTY)
        
        # Find next expiry day (include today if it's the expiry day)
        days_ahead = expiry_weekday - today.weekday()
        if days_ahead < 0:  # If expiry day already passed this week
            days_ahead += 7
        
        # Start from today if today is expiry day, otherwise next expiry
        if days_ahead == 0:
            next_expiry = today
        else:
            next_expiry = today + timedelta(days=days_ahead)
        
        # Generate next 5 weekly expiries
        for i in range(5):
            expiry = next_expiry + timedelta(weeks=i)
            expiries.append(expiry.strftime("%d%b%y").upper())
        
        return expiries
    
    def build_instrument_key(self, index_symbol, expiry, strike, option_type):
        """Build instrument key for option contract."""
        base = index_symbol.split("|")[1]
        instrument = f"{index_symbol}|{base}{expiry}{strike}{option_type}"
        return instrument
    
    def format_instrument_key_for_broker(self, broker_name, index_name, expiry, strike, option_type, index_info=None):
        """Format instrument key according to broker requirements.
        
        Args:
            broker_name: 'upstox' or 'dhan'
            index_name: 'NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY'
            expiry: Date in format '18DEC25'
            index_info: Dict with index configuration including lot_size
            strike: Strike price '26000'
            option_type: 'CE' or 'PE'
        """
        # Check cache first
        cache_key = f"{index_name}_{expiry}_{strike}_{option_type}"
        
        # Handle both upstox and upstox2 (multiple Upstox accounts)
        if broker_name in ['upstox', 'upstox2']:
            # Check cache
            if cache_key in self.upstox_instruments:
                return self.upstox_instruments[cache_key]
            
            # Try automatic lookup from master file
            instrument_key, _ = self.lookup_instrument(broker_name, index_name, expiry, strike, option_type)
            if instrument_key:
                print(f"  ✅ Upstox: Found {instrument_key}")
                self.upstox_instruments[cache_key] = instrument_key
                # NOTE: Don't store Upstox lot_size - use default index lot size instead
                # Upstox CSV lot_size field can be unreliable
                return instrument_key
            
            # Fallback to manual entry (skip in GUI mode)
            try:
                expiry_date = datetime.strptime(expiry, "%d%b%y")
                day = expiry_date.strftime("%d")
                month = expiry_date.strftime("%b")
                year = expiry_date.strftime("%Y")
                
                symbol = f"{index_name} {day} {month} {year} {strike} {option_type}"
                
                print(f"\n⚠️  Upstox: Instrument not found in master file")
                print(f"    Symbol: {symbol}")
                print(f"    Download: https://assets.upstox.com/market-quote/instruments/exchange/complete.csv.gz")
                print(f"    Skipping manual entry in GUI mode - instrument lookup failed")
                
                # Skip input() in GUI mode - return None immediately
                return None
            except Exception as e:
                print(f"⚠️  Upstox format error: {e}")
                return None
        
        elif broker_name == 'dhan':
            # Check cache
            if cache_key in self.dhan_instruments:
                return self.dhan_instruments[cache_key]
            
            # Try automatic lookup from master file
            instrument_key, lot_size = self.lookup_instrument(broker_name, index_name, expiry, strike, option_type)
            if instrument_key:
                print(f"  ✅ Dhan: Found {instrument_key} (CSV Lot: {lot_size})")
                self.dhan_instruments[cache_key] = instrument_key
                # NOTE: Don't store CSV lot size - it can be unreliable
                # Always use default index lot size from self.indices
                # if lot_size:
                #     self.instrument_lot_sizes[f"dhan_{cache_key}"] = lot_size
                return instrument_key
            
            # Fallback to manual entry (skip in GUI mode)
            try:
                expiry_date = datetime.strptime(expiry, "%d%b%y")
                day = expiry_date.strftime("%d").lstrip('0') or expiry_date.strftime("%d")
                month = expiry_date.strftime("%b").upper()  # DEC
                option_name = "CALL" if option_type == "CE" else "PUT"
                
                # Dhan CSV format: "NIFTY 23 DEC 27000 PUT"
                trading_symbol = f"{index_name} {day} {month} {strike} {option_name}"
                
                print(f"\n⚠️  Dhan: Instrument not found in master file")
                print(f"    Expected symbol: {trading_symbol}")
                print(f"    Check CSV for exact match at: https://images.dhan.co/api-data/api-scrip-master.csv")
                print(f"    Tip: Search for '{index_name} {day} {month}' in CSV")
                print(f"    Skipping manual entry in GUI mode - instrument lookup failed")
                
                # Skip input() in GUI mode - return None immediately
                return None
            except Exception as e:
                print(f"⚠️  Dhan format error: {e}")
                return None
        
        return None
    
    def _get_dhan_security_id(self, trading_symbol):
        """Get Dhan numeric security ID for a trading symbol."""
        # Check cache first
        if trading_symbol in self.dhan_instruments:
            return self.dhan_instruments[trading_symbol]
        
        # Try to fetch from Dhan's instrument master (simplified)
        # In production, download and cache the full CSV file
        # For now, return None to indicate lookup needed
        return None
    
    def get_instrument_keys_for_brokers(self, index_name, expiry, strike, option_type, index_info=None):
        """Get instrument keys formatted for all active brokers."""
        keys = {}
        
        if self.multi_account_mode:
            for broker_name in self.active_brokers.keys():
                key = self.format_instrument_key_for_broker(
                    broker_name, index_name, expiry, strike, option_type, index_info
                )
                if key:
                    keys[broker_name] = key
                # Don't print skip message here - will show in summary
        else:
            if self.current_broker:
                key = self.format_instrument_key_for_broker(
                    self.current_broker, index_name, expiry, strike, option_type, index_info
                )
                if key:
                    keys[self.current_broker] = key
        
        return keys
    
    def quick_order(self):
        """Quick order placement with 7-step interface."""
        if not self.multi_account_mode and not self.current_client:
            print("❌ No broker selected")
            return
        
        if self.multi_account_mode and not self.active_brokers:
            print("❌ No active brokers")
            return
        
        print("\n" + "="*60)
        print("⚡ QUICK ORDER")
        print("="*60)
        
        # Step 1: Select Index
        print("\n1️⃣ Select Index:")
        for key, value in self.indices.items():
            print(f"   {key}. {value['name']} (Lot: {value['lot_size']})")
        index_choice = input("Choose (1-4): ").strip()
        
        if index_choice not in self.indices:
            print("❌ Invalid choice")
            return
        
        index = self.indices[index_choice]
        print(f"✅ {index['name']}")
        
        # Step 2: Select Expiry (index-specific)
        print("\n2️⃣ Select Expiry:")
        expiries = self.get_current_expiries(index['name'])
        for i, exp in enumerate(expiries, 1):
            print(f"   {i}. {exp}")
        expiry_choice = int(input(f"Choose (1-{len(expiries)}): ")) - 1
        expiry = expiries[expiry_choice]
        print(f"✅ {expiry}")
        
        # Step 3: Strike Price
        strike = input("\n3️⃣ Strike Price: ").strip()
        print(f"✅ {strike}")
        
        # Step 4: CE/PE
        print("\n4️⃣ Option Type:")
        print("   1. CE (Call)")
        print("   2. PE (Put)")
        opt_choice = input("Choose (1-2): ").strip()
        option_type = "CE" if opt_choice == "1" else "PE"
        print(f"✅ {option_type}")
        
        # Step 5: BUY/SELL
        print("\n5️⃣ Transaction:")
        print("   1. BUY")
        print("   2. SELL")
        trans_choice = input("Choose (1-2): ").strip()
        transaction_type = "BUY" if trans_choice == "1" else "SELL"
        print(f"✅ {transaction_type}")
        
        # Step 6: Quantity with validation
        print(f"\n6️⃣ Quantity:")
        print(f"   Default Lot Size: {index['lot_size']} contracts per lot")
        print(f"   Range: {index['min_lots']}-{index['max_lots']} lots ({index['min_lots'] * index['lot_size']}-{index['freeze_qty']} contracts)")
        qty_input = input("Number of lots: ").strip()
        qty = int(qty_input)
        
        # Validate quantity
        if qty < index['min_lots']:
            print(f"❌ Minimum {index['min_lots']} lot required")
            return
        if qty > index['max_lots']:
            print(f"❌ Maximum {index['max_lots']} lots allowed (freeze quantity: {index['freeze_qty']} contracts)")
            return
        
        # Store lot count for later use
        self.current_lot_count = qty
        
        # Calculate contracts from lots (will be overridden per broker if needed)
        quantity = qty * index['lot_size']
        print(f"✅ {qty} lot(s) = {quantity} contracts (default calculation)")
        
        # Step 7: Order Type
        print("\n7️⃣ Order Type:")
        print("   1. MARKET")
        print("   2. LIMIT")
        order_choice = input("Choose (1-2) [1]: ").strip() or "1"
        order_type = "MARKET" if order_choice == "1" else "LIMIT"
        
        price = None
        if order_type == "LIMIT":
            price = float(input("Limit price: "))
        
        # Step 8: Product Type
        print("\n8️⃣ Product Type:")
        print("   1. Intraday (MIS)")
        print("   2. Delivery (NRML)")
        prod_choice = input("Choose (1-2) [1]: ").strip() or "1"
        product = "I" if prod_choice == "1" else "D"
        
        # Build symbol info
        symbol_info = f"{index['name']} {expiry} {strike} {option_type}"
        
        # Auto-format instrument keys for each broker
        instrument_keys = self.get_instrument_keys_for_brokers(
            index['name'], expiry, strike, option_type, index
        )
        
        if not instrument_keys:
            print("❌ No valid instrument keys provided. Order cancelled.")
            return
        
        # Summary
        print("\n" + "="*60)
        print("📋 ORDER SUMMARY")
        print("="*60)
        
        if self.multi_account_mode:
            print(f"Mode: 🚀 MULTI-ACCOUNT")
            active_brokers = [b.upper() for b in instrument_keys.keys()]
            skipped_brokers = [b.upper() for b in self.active_brokers.keys() if b not in instrument_keys]
            
            if active_brokers:
                print(f"Active: {', '.join(active_brokers)}")
                for broker, key in instrument_keys.items():
                    print(f"  {broker.upper()}: {key}")
            
            if skipped_brokers:
                print(f"⚠️  Skipped: {', '.join(skipped_brokers)}")
        else:
            print(f"Broker: {self.current_broker.upper()}")
            print(f"Account: {self.account_name}")
            print(f"Instrument: {instrument_keys.get(self.current_broker)}")
        
        print(f"Symbol: {symbol_info}")
        print(f"Action: {transaction_type} {quantity} contracts")
        print(f"Type: {order_type}" + (f" @ ₹{price}" if price else ""))
        print(f"Product: {'Intraday' if product == 'I' else 'Delivery'}")
        print("="*60)
        
        confirm = input("\n⚠️  Execute order? (y/n): ").strip().lower()
        
        if confirm in ['y', 'yes']:
            if self.multi_account_mode:
                self._execute_parallel_order(
                    instrument_keys, quantity, transaction_type, 
                    order_type, product, price
                )
            else:
                try:
                    print("\n🚀 Placing order...")
                    broker_key = instrument_keys.get(self.current_broker)
                    if not broker_key:
                        print(f"❌ No instrument key for {self.current_broker}")
                        return
                    
                    result = self.current_client.place_order(
                        instrument_key=broker_key,
                        quantity=quantity,
                        transaction_type=transaction_type,
                        order_type=order_type,
                        product=product,
                        price=price,
                    )
                    
                    # Check for success - handle different response formats
                    order_id = None
                    if result:
                        # Dhan format: {orderId, orderStatus}
                        if 'orderId' in result:
                            order_id = result.get('orderId')
                            status = result.get('orderStatus', 'UNKNOWN')
                            print(f"✅ Order placed successfully!")
                            print(f"   Order ID: {order_id}")
                            print(f"   Status: {status}")
                        # Upstox format: {data: {order_id}}
                        elif 'data' in result:
                            order_id = result.get('data', {}).get('order_id', 'N/A')
                            print(f"✅ Order placed successfully! Order ID: {order_id}")
                    else:
                        print(f"⚠️  Order response: {result}")
                except Exception as e:
                    print(f"❌ ERROR: {e}")
        else:
            print("❌ Order cancelled")
    
    def _execute_parallel_order(self, instrument_keys, quantity, transaction_type, 
                                 order_type, product, price):
        """Execute order on all active brokers in parallel."""
        print("\n🚀 Executing parallel orders...")
        print("="*60)
        
        def place_order_for_broker(broker_name, broker_info):
            """Place order for a single broker."""
            try:
                # Get broker-specific instrument key
                broker_key = instrument_keys.get(broker_name)
                if not broker_key:
                    return {
                        'broker': broker_name,
                        'account': broker_info['name'],
                        'success': False,
                        'error': 'No instrument key provided'
                    }
                
                client = broker_info['client']
                account_name = broker_info['name']
                
                # Use the quantity that was calculated with default index lot size
                # Don't trust CSV lot_size fields - they can be unreliable
                order_quantity = int(quantity)
                print(f"  {broker_name.upper()}: Sending {order_quantity} contracts")
                
                result = client.place_order(
                    instrument_key=broker_key,
                    quantity=order_quantity,
                    transaction_type=transaction_type,
                    order_type=order_type,
                    product=product,
                    price=price,
                )
                
                # Check for success - handle different response formats
                if result:
                    order_id = None
                    status = None
                    
                    # Dhan format: {orderId, orderStatus}
                    if 'orderId' in result:
                        order_id = result.get('orderId')
                        status = result.get('orderStatus', 'UNKNOWN')
                    # Upstox format: {data: {order_id}}
                    elif 'data' in result:
                        order_id = result.get('data', {}).get('order_id', 'N/A')
                    
                    if order_id:
                        return {
                            'broker': broker_name,
                            'account': account_name,
                            'success': True,
                            'order_id': order_id,
                            'status': status
                        }
                
                return {
                    'broker': broker_name,
                    'account': account_name,
                    'success': False,
                    'error': str(result) if result else 'No response'
                }
            except Exception as e:
                return {
                    'broker': broker_name,
                    'account': account_name,
                    'success': False,
                    'error': str(e)
                }
        
        # Execute orders in parallel
        results = []
        
        # Show what will be sent
        print("\n📊 Order Details:")
        for broker_name in instrument_keys.keys():
            print(f"  {broker_name.upper()}: {instrument_keys[broker_name]} | Qty: {int(quantity)}")
        print()
        
        with ThreadPoolExecutor(max_workers=len(self.active_brokers)) as executor:
            futures = {
                executor.submit(place_order_for_broker, broker_name, broker_info): broker_name
                for broker_name, broker_info in self.active_brokers.items()
            }
            
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                
                if result['success']:
                    status_msg = f" | Status: {result['status']}" if result.get('status') else ""
                    print(f"✅ {result['broker'].upper()} ({result['account']}): Order ID {result['order_id']}{status_msg}")
                else:
                    print(f"❌ {result['broker'].upper()} ({result['account']}): {result['error']}")
        
        print("="*60)
        success_count = sum(1 for r in results if r['success'])
        print(f"\n📊 Result: {success_count}/{len(results)} orders executed successfully")
        
        # Return order results for stop loss activation
        order_results = {}
        for result in results:
            if result['success']:
                broker_name = result['broker']
                order_results[broker_name] = {
                    'order_id': result['order_id'],
                    'instrument_key': instrument_keys.get(broker_name)
                }
        return order_results
    
    def _activate_stop_loss(self, stop_loss_config, order_results, order_type, entry_price):
        """Activate stop loss after order execution."""
        print("\n" + "="*60)
        print("🛡️  ACTIVATING STOP LOSS")
        print("="*60)
        
        sl_type = stop_loss_config['type']
        
        if sl_type == 'auto':
            # Auto trailing stop loss
            trail_percent = stop_loss_config['trail_percent']
            
            # For MARKET orders, we need to wait for execution and get actual entry price
            if order_type == "MARKET":
                print("⏳ Fetching actual entry price...")
                import time
                time.sleep(2)  # Wait for order to execute
                
                # Get positions to find entry price
                entry_price = self._get_entry_price_from_positions(stop_loss_config['instrument_keys'])
                if not entry_price:
                    print("⚠️  Could not fetch entry price. Please set stop loss manually.")
                    return
            
            # Calculate initial stop loss
            initial_sl = entry_price * (1 - trail_percent / 100)
            
            # Store in active stop losses
            for broker_name, order_info in order_results.items():
                position_key = f"{broker_name}_{order_info['instrument_key']}"
                self.active_stop_losses[position_key] = {
                    'broker': broker_name,
                    'instrument_key': order_info['instrument_key'],
                    'symbol_info': stop_loss_config['symbol_info'],
                    'quantity': stop_loss_config['quantity'],
                    'product': stop_loss_config['product'],
                    'entry_price': entry_price,
                    'trail_percent': trail_percent,
                    'current_sl': initial_sl,
                    'highest_price': entry_price,
                    'sl_order_id': None
                }
            
            print(f"✅ Auto Trailing Stop Loss Activated")
            print(f"   Entry Price: ₹{entry_price:.2f}")
            print(f"   Initial Stop Loss: ₹{initial_sl:.2f} ({trail_percent}% trail)")
            print(f"   Monitoring {len(order_results)} position(s)")
            
            # Start monitoring thread if not already running
            if not self.stop_loss_monitor_active:
                self._start_stop_loss_monitor()
        
        elif sl_type == 'manual':
            # Manual stop loss - place SL order immediately
            sl_price = stop_loss_config['stop_loss_price']
            print(f"📝 Placing Stop Loss orders at ₹{sl_price}...")
            
            for broker_name, order_info in order_results.items():
                try:
                    client = self.active_brokers.get(broker_name, {}).get('client') if self.multi_account_mode else self.current_client
                    
                    if client:
                        # Place stop loss order
                        sl_result = client.place_order(
                            instrument_key=order_info['instrument_key'],
                            quantity=stop_loss_config['quantity'],
                            transaction_type="SELL",
                            order_type="SL",  # Stop Loss order
                            product=stop_loss_config['product'],
                            price=sl_price * 0.99,  # Limit price slightly below trigger
                        )
                        
                        sl_order_id = None
                        if sl_result:
                            if 'orderId' in sl_result:
                                sl_order_id = sl_result.get('orderId')
                            elif 'data' in sl_result:
                                sl_order_id = sl_result.get('data', {}).get('order_id')
                        
                        if sl_order_id:
                            print(f"   ✅ {broker_name.upper()}: SL Order ID {sl_order_id}")
                        else:
                            print(f"   ⚠️  {broker_name.upper()}: SL order placement unclear")
                except Exception as e:
                    print(f"   ❌ {broker_name.upper()}: {e}")
        
        elif sl_type == 'manual_pending':
            print("📝 Stop loss will be set manually after reviewing position")
        
        print("="*60)
    
    def _get_entry_price_from_positions(self, instrument_keys):
        """Get entry price from current positions."""
        try:
            if self.multi_account_mode:
                # Check first active broker
                for broker_name, broker_info in self.active_brokers.items():
                    if broker_name in instrument_keys:
                        client = broker_info['client']
                        positions = client.get_positions()
                        positions_data = positions.get('data', [])
                        
                        for pos in positions_data:
                            pos_key = pos.get('instrument_token') or pos.get('securityId')
                            if str(pos_key) == str(instrument_keys[broker_name]):
                                avg_price = pos.get('average_price') or pos.get('buy_avg') or pos.get('buyAvg')
                                if avg_price:
                                    return float(avg_price)
            else:
                positions = self.current_client.get_positions()
                positions_data = positions.get('data', [])
                
                for pos in positions_data:
                    pos_key = pos.get('instrument_token') or pos.get('securityId')
                    if str(pos_key) == str(list(instrument_keys.values())[0]):
                        avg_price = pos.get('average_price') or pos.get('buy_avg') or pos.get('buyAvg')
                        if avg_price:
                            return float(avg_price)
        except:
            pass
        return None
    
    def _start_stop_loss_monitor(self):
        """Start background thread to monitor trailing stop losses."""
        if self.stop_loss_monitor_active:
            return
        
        self.stop_loss_monitor_active = True
        self.stop_loss_monitor_thread = threading.Thread(target=self._monitor_stop_losses, daemon=True)
        self.stop_loss_monitor_thread.start()
        print("\n🔄 Stop Loss Monitor started in background")
    
    def _monitor_stop_losses(self):
        """Background thread to monitor and update trailing stop losses."""
        import time
        
        while self.stop_loss_monitor_active and self.active_stop_losses:
            try:
                for position_key, sl_config in list(self.active_stop_losses.items()):
                    # Get current price
                    current_price = self._get_current_price(sl_config['broker'], sl_config['instrument_key'])
                    
                    if not current_price:
                        continue
                    
                    # Update highest price
                    if current_price > sl_config['highest_price']:
                        sl_config['highest_price'] = current_price
                        
                        # Calculate new trailing stop loss
                        new_sl = current_price * (1 - sl_config['trail_percent'] / 100)
                        
                        if new_sl > sl_config['current_sl']:
                            sl_config['current_sl'] = new_sl
                            print(f"\n📈 {sl_config['symbol_info']}: Price ₹{current_price:.2f} → Stop Loss updated to ₹{new_sl:.2f}")
                    
                    # Check if stop loss is hit
                    if current_price <= sl_config['current_sl']:
                        print(f"\n🛑 STOP LOSS HIT: {sl_config['symbol_info']} at ₹{current_price:.2f}")
                        self._execute_stop_loss_exit(position_key, sl_config)
                        del self.active_stop_losses[position_key]
                
                # Sleep for 5 seconds between checks
                time.sleep(5)
            
            except Exception as e:
                print(f"\n⚠️  Stop Loss Monitor Error: {e}")
                time.sleep(10)
        
        self.stop_loss_monitor_active = False
        print("\n🔴 Stop Loss Monitor stopped")
    
    def _get_current_price(self, broker_name, instrument_key):
        """Get current market price for an instrument."""
        try:
            client = self.active_brokers.get(broker_name, {}).get('client') if self.multi_account_mode else self.current_client
            
            if not client or not hasattr(client, 'get_market_quote'):
                return None
            
            quote = client.get_market_quote(instrument_key)
            
            # Extract price from quote response
            if quote and 'data' in quote:
                data = quote['data']
                if isinstance(data, dict):
                    # Try different price fields
                    ltp = data.get('ltp') or data.get('last_price') or data.get('lastPrice')
                    if ltp:
                        return float(ltp)
            
            return None
        except:
            return None
    
    def _execute_stop_loss_exit(self, position_key, sl_config):
        """Execute stop loss exit order."""
        try:
            broker_name = sl_config['broker']
            client = self.active_brokers.get(broker_name, {}).get('client') if self.multi_account_mode else self.current_client
            
            if not client:
                return
            
            result = client.place_order(
                instrument_key=sl_config['instrument_key'],
                quantity=sl_config['quantity'],
                transaction_type="SELL",
                order_type="MARKET",
                product=sl_config['product'],
                price=0,
            )
            
            order_id = None
            if result:
                if 'orderId' in result:
                    order_id = result.get('orderId')
                elif 'data' in result:
                    order_id = result.get('data', {}).get('order_id')
            
            if order_id:
                print(f"✅ Stop Loss Exit Order Placed: ID {order_id}")
            else:
                print(f"⚠️  Stop Loss exit status unclear: {result}")
        
        except Exception as e:
            print(f"❌ Stop Loss Exit Error: {e}")
    
    def view_positions(self):
        """View current positions."""
        if not self.multi_account_mode and not self.current_client:
            print("❌ No broker selected")
            return
        
        if self.multi_account_mode:
            self._view_multi_account_positions()
            return
        
        print("\n" + "="*60)
        print("💼 POSITIONS")
        print("="*60)
        
        try:
            positions = self.current_client.get_positions()
            positions_data = positions.get('data', [])
            
            if not positions_data:
                print("✅ No open positions")
                return
            
            total_pnl = 0
            print(f"\nFound {len(positions_data)} position(s):\n")
            
            for i, pos in enumerate(positions_data, 1):
                symbol = pos.get('tradingsymbol', 'N/A')
                qty = pos.get('quantity', 0)
                pnl = pos.get('pnl', 0) or pos.get('unrealised', 0) or 0
                
                if qty != 0:
                    pnl_symbol = "🟢" if float(pnl) >= 0 else "🔴"
                    total_pnl += float(pnl)
                    print(f"{i}. {symbol}")
                    print(f"   Qty: {qty} | P&L: {pnl_symbol} ₹{float(pnl):,.2f}")
            
            if total_pnl != 0:
                print(f"\n{'─'*60}")
                print(f"Total P&L: {'🟢' if total_pnl >= 0 else '🔴'} ₹{total_pnl:,.2f}")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _get_trade_metrics(self, client):
        """Calculate today's trading metrics."""
        try:
            orders = client.get_order_history()
            orders_data = orders.get('data', [])
            
            if not orders_data:
                return {'trades': 0, 'roi': 0, 'avg_holding': 'N/A'}
            
            # Count completed trades today
            from datetime import datetime
            today = datetime.now().date()
            
            completed_trades = []
            for order in orders_data:
                order_status = order.get('status', '').upper()
                if order_status in ['COMPLETE', 'TRADED', 'EXECUTED']:
                    # Check if order is from today
                    order_time_str = order.get('order_timestamp', order.get('created_at', ''))
                    if order_time_str:
                        try:
                            # Parse timestamp (handles different formats)
                            if 'T' in str(order_time_str):
                                order_date = datetime.fromisoformat(str(order_time_str).replace('Z', '+00:00')).date()
                            else:
                                order_date = datetime.strptime(str(order_time_str)[:10], '%Y-%m-%d').date()
                            
                            if order_date == today:
                                completed_trades.append(order)
                        except:
                            pass
            
            trades_count = len(completed_trades)
            
            # Calculate ROI from positions
            positions = client.get_positions()
            positions_data = positions.get('data', [])
            
            total_pnl = sum(float(p.get('pnl', 0) or p.get('unrealised', 0) or 0) for p in positions_data)
            
            # Get capital used
            funds = client.get_funds_and_margin()
            used_margin = float(funds.get('data', {}).get('equity', {}).get('used_margin', 1))
            
            roi = (total_pnl / used_margin * 100) if used_margin > 0 else 0
            
            # Calculate average holding time (simplified)
            holding_times = []
            for pos in positions_data:
                if pos.get('quantity', 0) != 0:
                    # Estimate holding time based on order timestamps
                    # This is a simplified calculation
                    holding_times.append(1)  # Placeholder
            
            avg_holding = f"{len(holding_times)}+ active" if holding_times else "N/A"
            
            return {
                'trades': trades_count,
                'roi': roi,
                'avg_holding': avg_holding
            }
        except Exception as e:
            return {'trades': 0, 'roi': 0, 'avg_holding': 'N/A'}
    
    def _view_multi_account_positions(self):
        """View positions across all active brokers."""
        print("\n" + "="*60)
        print("💼 MULTI-ACCOUNT POSITIONS")
        print("="*60)
        
        total_pnl_all = 0
        
        for broker_name, broker_info in self.active_brokers.items():
            print(f"\n🔸 {broker_name.upper()} ({broker_info['name']})")
            print("─" * 60)
            
            try:
                client = broker_info['client']
                positions = client.get_positions()
                positions_data = positions.get('data', [])
                
                if not positions_data or all(p.get('quantity', 0) == 0 for p in positions_data):
                    print("   No open positions")
                    continue
                
                broker_pnl = 0
                position_count = 0
                
                for pos in positions_data:
                    qty = pos.get('quantity', 0)
                    if qty != 0:
                        position_count += 1
                        symbol = pos.get('tradingsymbol', 'N/A')
                        pnl = pos.get('pnl', 0) or pos.get('unrealised', 0) or 0
                        pnl_symbol = "🟢" if float(pnl) >= 0 else "🔴"
                        broker_pnl += float(pnl)
                        
                        # Get order time
                        order_time = pos.get('order_timestamp') or pos.get('created_at') or pos.get('buy_date') or 'N/A'
                        if order_time != 'N/A':
                            try:
                                if 'T' in str(order_time):
                                    dt = datetime.fromisoformat(str(order_time).replace('Z', '+00:00'))
                                    order_time = dt.strftime('%H:%M:%S')
                                else:
                                    order_time = str(order_time).split()[1] if len(str(order_time).split()) > 1 else str(order_time)[:8]
                            except:
                                pass
                        
                        print(f"   {symbol}")
                        print(f"   Qty: {qty} | P&L: {pnl_symbol} ₹{float(pnl):,.2f} | Entry: {order_time}")
                
                if position_count > 0:
                    print(f"   ───────────────────────────")
                    pnl_symbol = "🟢" if broker_pnl >= 0 else "🔴"
                    print(f"   {broker_name.upper()} Total: {pnl_symbol} ₹{broker_pnl:,.2f}")
                    total_pnl_all += broker_pnl
            
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        if total_pnl_all != 0:
            print(f"\n{'═'*60}")
            pnl_symbol = "🟢" if total_pnl_all >= 0 else "🔴"
            print(f"COMBINED P&L: {pnl_symbol} ₹{total_pnl_all:,.2f}")
            print(f"{'═'*60}")
    
    def increase_position(self):
        """Increase quantity on existing position."""
        if not self.multi_account_mode and not self.current_client:
            print("❌ No broker selected")
            return
        
        if self.multi_account_mode:
            self._increase_multi_account_positions()
            return
        
        print("\n" + "="*60)
        print("📈 INCREASE POSITION")
        print("="*60)
        
        try:
            # Get positions
            positions = self.current_client.get_positions()
            positions_data = positions.get('data', [])
            open_positions = [p for p in positions_data if p.get('quantity', 0) != 0]
            
            if not open_positions:
                print("✅ No open positions")
                return
            
            # Display positions
            print("\nSelect position to increase:\n")
            for i, pos in enumerate(open_positions, 1):
                symbol = pos.get('tradingsymbol', 'N/A')
                qty = pos.get('quantity', 0)
                ltp = pos.get('last_price', 0)
                pnl = pos.get('pnl', 0)
                pnl_color = '🟢' if pnl >= 0 else '🔴'
                print(f"{i}. {symbol} | Qty: {qty} | LTP: ₹{ltp:.2f} | P&L: {pnl_color} ₹{pnl:.2f}")
            
            choice = int(input("\nSelect position (number): ")) - 1
            if choice < 0 or choice >= len(open_positions):
                print("❌ Invalid selection")
                return
            
            selected = open_positions[choice]
            instrument_key = selected.get('instrument_token', '')
            current_qty = abs(selected.get('quantity', 0))
            
            print(f"\nSelected: {selected.get('tradingsymbol', 'N/A')}")
            print(f"Current Qty: {current_qty}")
            
            add_qty = int(input("\nEnter quantity to add: "))
            
            if add_qty <= 0:
                print("❌ Invalid quantity")
                return
            
            # Determine transaction type (BUY if long, SELL if short)
            transaction_type = "BUY" if selected.get('quantity', 0) > 0 else "SELL"
            
            confirm = input(f"\n⚠️  {transaction_type} {add_qty} more contracts? (y/n): ").strip().lower()
            
            if confirm in ['y', 'yes']:
                entry_time = datetime.now()
                
                result = self.current_client.place_order(
                    instrument_key=instrument_key,
                    quantity=add_qty,
                    transaction_type=transaction_type,
                    order_type="MARKET",
                    product="I",
                )
                
                exit_time = datetime.now()
                execution_ms = (exit_time - entry_time).total_seconds() * 1000
                time_str = exit_time.strftime('%H:%M:%S')
                
                if result:
                    new_total = current_qty + add_qty
                    print(f"✅ Order placed at {time_str} ({execution_ms:.0f}ms)")
                    print(f"   Added: {add_qty} | New Total: {new_total}")
                else:
                    print("❌ Order failed")
            else:
                print("❌ Cancelled")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _increase_multi_account_positions(self):
        """Increase positions across multiple broker accounts."""
        try:
            # Collect positions from all brokers
            all_positions = []
            for broker_key, broker_info in self.active_brokers.items():
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    positions_response = client.get_positions()
                    positions = positions_response.get('data', [])
                    for pos in positions:
                        qty = pos.get('quantity', 0)
                        if qty != 0:
                            pos['broker_name'] = account_name
                            pos['client'] = client
                            all_positions.append(pos)
                except Exception as e:
                    print(f"❌ Error fetching positions from {account_name}: {e}")
            
            if not all_positions:
                print("\n⚠️  No open positions found")
                return
            
            print("\n" + "="*60)
            print("📈 INCREASE POSITION (Multi-Account)")
            print("="*60)
            
            # Display positions
            print(f"\n{'No.':<5}{'Broker':<15}{'Symbol':<30}{'Qty':<10}{'LTP':<12}{'P&L':<15}")
            print("="*90)
            
            for i, pos in enumerate(all_positions, 1):
                symbol = pos.get('tradingsymbol', 'N/A')
                qty = pos.get('quantity', 0)
                ltp = pos.get('last_price', 0)
                pnl = pos.get('pnl', 0)
                broker_name = pos.get('broker_name', 'N/A')
                pnl_color = '🟢' if pnl >= 0 else '🔴'
                print(f"{i:<5}{broker_name:<15}{symbol:<30}{qty:<10}₹{ltp:<11.2f}{pnl_color} ₹{pnl:.2f}")
            
            # Percentage increase options
            print("\n" + "="*60)
            print("Increase Options:")
            print("  1 = 25% of each position")
            print("  2 = 50% of each position")
            print("  3 = 75% of each position")
            print("  4 = 100% of each position (double position)")
            print("  5 = Custom quantity for all")
            
            choice = input("\nChoose increase % (1-5): ").strip()
            
            try:
                # Calculate quantities for each position based on choice
                positions_to_increase = []
                
                for pos in all_positions:
                    current_qty = abs(pos.get('quantity', 0))
                    
                    if choice == '1':
                        add_qty = int(current_qty * 0.25)
                    elif choice == '2':
                        add_qty = int(current_qty * 0.5)
                    elif choice == '3':
                        add_qty = int(current_qty * 0.75)
                    elif choice == '4':
                        add_qty = current_qty  # 100% = double
                    elif choice == '5':
                        print(f"\n{pos.get('broker_name')} - {pos.get('tradingsymbol', 'N/A')} (Current: {current_qty})")
                        add_qty = int(input("  Enter quantity to add: "))
                    else:
                        print("❌ Invalid choice")
                        return
                    
                    if add_qty > 0:
                        positions_to_increase.append({
                            'pos': pos,
                            'current_qty': current_qty,
                            'add_qty': add_qty
                        })
                
                if not positions_to_increase:
                    print("❌ No valid quantities")
                    return
                
                # Show summary
                print("\n" + "="*60)
                print("Summary:")
                for item in positions_to_increase:
                    pos = item['pos']
                    print(f"  {pos.get('broker_name')}: {pos.get('tradingsymbol', 'N/A')}")
                    print(f"    Current: {item['current_qty']} → Add: {item['add_qty']} = New Total: {item['current_qty'] + item['add_qty']}")
                
                confirm = input(f"\n⚠️  Increase {len(positions_to_increase)} position(s)? (y/n): ").strip().lower()
                
                if confirm in ['y', 'yes']:
                    print("\n🔄 Increasing positions in parallel...")
                    
                    def increase_single_position(item):
                        """Increase a single position."""
                        try:
                            pos = item['pos']
                            add_qty = item['add_qty']
                            entry_time = datetime.now()
                            
                            client = pos.get('client')
                            transaction_type = "BUY" if pos.get('quantity', 0) > 0 else "SELL"
                            
                            result = client.place_order(
                                instrument_key=pos.get('instrument_token', ''),
                                quantity=add_qty,
                                transaction_type=transaction_type,
                                order_type="MARKET",
                                product="I",
                            )
                            
                            exit_time = datetime.now()
                            execution_ms = (exit_time - entry_time).total_seconds() * 1000
                            time_str = exit_time.strftime('%H:%M:%S')
                            
                            if result:
                                return {
                                    'success': True,
                                    'broker': pos.get('broker_name'),
                                    'symbol': pos.get('tradingsymbol'),
                                    'added': add_qty,
                                    'total': item['current_qty'] + add_qty,
                                    'time': time_str,
                                    'ms': execution_ms
                                }
                            return {'success': False, 'broker': pos.get('broker_name')}
                        except Exception as e:
                            return {'success': False, 'broker': pos.get('broker_name'), 'error': str(e)}
                    
                    # Execute all increases in parallel
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    
                    results = []
                    with ThreadPoolExecutor(max_workers=len(positions_to_increase)) as executor:
                        futures = {executor.submit(increase_single_position, item): item for item in positions_to_increase}
                        
                        for future in as_completed(futures):
                            result = future.result()
                            results.append(result)
                            if result['success']:
                                print(f"✅ {result['broker']}: {result['symbol']} - Added {result['added']}, Total: {result['total']} at {result['time']} ({result['ms']:.0f}ms)")
                            else:
                                print(f"❌ {result['broker']}: Failed - {result.get('error', 'Unknown error')}")
                    
                    success = sum(1 for r in results if r['success'])
                    print(f"\n✅ Increased {success}/{len(positions_to_increase)} position(s)")
                    
                    # Show timing analysis
                    if success > 1:
                        successful_times = [r['ms'] for r in results if r['success']]
                        max_diff = max(successful_times) - min(successful_times)
                        print(f"⏱️  Max execution difference: {max_diff:.0f}ms")
                else:
                    print("❌ Cancelled")
            
            except ValueError:
                print("❌ Invalid input")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def exit_order(self):
        """Exit position completely."""
        if not self.multi_account_mode and not self.current_client:
            print("❌ No broker selected")
            return
        
        if self.multi_account_mode:
            self._exit_multi_account_positions()
            return
        
        print("\n" + "="*60)
        print("🚪 EXIT POSITION")
        print("="*60)
        
        try:
            # Get positions
            positions = self.current_client.get_positions()
            positions_data = positions.get('data', [])
            open_positions = [p for p in positions_data if p.get('quantity', 0) != 0]
            
            if not open_positions:
                print("✅ No open positions")
                return
            
            # Display positions
            print("\nSelect position to exit:\n")
            for i, pos in enumerate(open_positions, 1):
                symbol = pos.get('tradingsymbol', 'N/A')
                qty = pos.get('quantity', 0)
                pnl = pos.get('pnl', 0) or pos.get('unrealised', 0) or 0
                pnl_symbol = "🟢" if float(pnl) >= 0 else "🔴"
                print(f"{i}. {symbol} | Qty: {qty} | {pnl_symbol} ₹{float(pnl):,.2f}")
            print(f"{len(open_positions) + 1}. Exit ALL positions")
            
            choice = input("\nSelect position (or 'all'): ").strip()
            
            if choice == str(len(open_positions) + 1) or choice.lower() == 'all':
                # Exit all
                confirm = input(f"\n⚠️  Exit ALL {len(open_positions)} position(s)? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    success = 0
                    for pos in open_positions:
                        try:
                            qty = pos.get('quantity', 0)
                            transaction_type = "SELL" if qty > 0 else "BUY"
                            
                            self.current_client.place_order(
                                instrument_key=pos.get('instrument_token', ''),
                                quantity=abs(qty),
                                transaction_type=transaction_type,
                                order_type="MARKET",
                                product="I",
                            )
                            success += 1
                        except:
                            pass
                    
                    print(f"\n✅ Exit orders placed for {success}/{len(open_positions)} positions")
            else:
                # Exit specific position
                idx = int(choice) - 1
                if 0 <= idx < len(open_positions):
                    selected = open_positions[idx]
                    qty = selected.get('quantity', 0)
                    transaction_type = "SELL" if qty > 0 else "BUY"
                    
                    print(f"\nExiting: {selected.get('tradingsymbol', 'N/A')}")
                    print(f"Quantity: {abs(qty)}")
                    
                    confirm = input(f"\n⚠️  Confirm exit? (y/n): ").strip().lower()
                    
                    if confirm in ['y', 'yes']:
                        result = self.current_client.place_order(
                            instrument_key=selected.get('instrument_token', ''),
                            quantity=abs(qty),
                            transaction_type=transaction_type,
                            order_type="MARKET",
                            product="I",
                        )
                        
                        if result:
                            print("✅ Exit order placed!")
                        else:
                            print("❌ Order failed")
                    else:
                        print("❌ Cancelled")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _exit_multi_account_positions(self):
        """Exit positions across multiple broker accounts."""
        try:
            # Collect positions from all brokers
            all_positions = []
            for broker_key, broker_info in self.active_brokers.items():
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    positions_response = client.get_positions()
                    positions = positions_response.get('data', [])
                    for pos in positions:
                        # Only include active positions (non-zero quantity)
                        qty = pos.get('quantity', 0)
                        if qty != 0:
                            pos['broker_name'] = account_name
                            pos['client'] = client
                            all_positions.append(pos)
                except Exception as e:
                    print(f"❌ Error fetching positions from {account_name}: {e}")
            
            if not all_positions:
                print("\n⚠️  No open positions found")
                return
            
            # Display positions
            print(f"\n{'No.':<5}{'Broker':<15}{'Symbol':<30}{'Qty':<10}{'LTP':<12}{'P&L':<15}{'Entry Time':<12}")
            print("="*105)
            
            for i, pos in enumerate(all_positions, 1):
                symbol = pos.get('tradingsymbol', 'N/A')
                qty = pos.get('quantity', 0)
                ltp = pos.get('last_price', 0)
                pnl = pos.get('pnl', 0)
                broker_name = pos.get('broker_name', 'N/A')
                
                # Get order time
                order_time = pos.get('order_timestamp') or pos.get('created_at') or pos.get('buy_date') or 'N/A'
                if order_time != 'N/A':
                    try:
                        if 'T' in str(order_time):
                            dt = datetime.fromisoformat(str(order_time).replace('Z', '+00:00'))
                            order_time = dt.strftime('%H:%M:%S')
                        else:
                            order_time = str(order_time).split()[1] if len(str(order_time).split()) > 1 else str(order_time)[:8]
                    except:
                        pass
                
                pnl_color = '🟢' if pnl >= 0 else '🔴'
                print(f"{i:<5}{broker_name:<15}{symbol:<30}{qty:<10}₹{ltp:<11.2f}{pnl_color} ₹{pnl:<13.2f}{order_time:<12}")
            
            # Exit options
            print("\n" + "="*60)
            print("Options:")
            print("  0 = Exit ALL positions (all brokers)")
            print("  Enter position number to exit specific position")
            print("  Enter = Cancel")
            
            choice = input("\nChoice: ").strip()
            
            if not choice:
                return
            
            if choice == '0':
                # Exit all positions
                confirm = input(f"\n⚠️  Exit ALL {len(all_positions)} positions? (y/n): ").strip().lower()
                
                if confirm in ['y', 'yes']:
                    print("\n🔄 Exiting all positions in parallel...")
                    
                    def exit_single_position(pos):
                        """Exit a single position."""
                        try:
                            entry_time = datetime.now()
                            qty = pos.get('quantity', 0)
                            transaction_type = "SELL" if qty > 0 else "BUY"
                            client = pos.get('client')
                            broker_name = pos.get('broker_name')
                            symbol = pos.get('tradingsymbol')
                            
                            result = client.place_order(
                                instrument_key=pos.get('instrument_token', ''),
                                quantity=abs(qty),
                                transaction_type=transaction_type,
                                order_type="MARKET",
                                product="I",
                            )
                            
                            exit_time = datetime.now()
                            execution_ms = (exit_time - entry_time).total_seconds() * 1000
                            time_str = exit_time.strftime('%H:%M:%S')
                            
                            if result:
                                return {'success': True, 'broker': broker_name, 'symbol': symbol, 'time': time_str, 'ms': execution_ms}
                            return {'success': False, 'broker': broker_name, 'symbol': symbol}
                        except Exception as e:
                            return {'success': False, 'broker': pos.get('broker_name'), 'error': str(e)}
                    
                    # Execute all exits in parallel
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    
                    results = []
                    with ThreadPoolExecutor(max_workers=len(all_positions)) as executor:
                        futures = {executor.submit(exit_single_position, pos): pos for pos in all_positions}
                        
                        for future in as_completed(futures):
                            result = future.result()
                            results.append(result)
                            if result['success']:
                                print(f"✅ {result['broker']}: {result['symbol']} exited at {result['time']} ({result['ms']:.0f}ms)")
                            else:
                                print(f"❌ {result['broker']}: Failed - {result.get('error', 'Unknown error')}")
                    
                    success = sum(1 for r in results if r['success'])
                    print(f"\n✅ Exit orders placed for {success}/{len(all_positions)} positions")
                    
                    # Show timing analysis
                    if success > 1:
                        successful_times = [r['ms'] for r in results if r['success']]
                        max_diff = max(successful_times) - min(successful_times)
                        print(f"⏱️  Max execution difference: {max_diff:.0f}ms")
            else:
                # Exit specific position
                idx = int(choice) - 1
                if 0 <= idx < len(all_positions):
                    selected = all_positions[idx]
                    qty = selected.get('quantity', 0)
                    transaction_type = "SELL" if qty > 0 else "BUY"
                    
                    print(f"\nExiting: {selected.get('tradingsymbol', 'N/A')} ({selected.get('broker_name')})")
                    print(f"Quantity: {abs(qty)}")
                    
                    confirm = input(f"\n⚠️  Confirm exit? (y/n): ").strip().lower()
                    
                    if confirm in ['y', 'yes']:
                        client = selected.get('client')
                        entry_time = datetime.now()
                        
                        result = client.place_order(
                            instrument_key=selected.get('instrument_token', ''),
                            quantity=abs(qty),
                            transaction_type=transaction_type,
                            order_type="MARKET",
                            product="I",
                        )
                        
                        exit_time = datetime.now()
                        execution_ms = (exit_time - entry_time).total_seconds() * 1000
                        time_str = exit_time.strftime('%H:%M:%S')
                        
                        if result:
                            print(f"✅ Exit order placed at {time_str} ({execution_ms:.0f}ms)")
                        else:
                            print("❌ Order failed")
                    else:
                        print("❌ Cancelled")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def partial_exit(self):
        """Partially exit position."""
        if not self.multi_account_mode and not self.current_client:
            print("❌ No broker selected")
            return
        
        if self.multi_account_mode:
            self._partial_exit_multi_account()
            return
        
        print("\n" + "="*60)
        print("🚪 PARTIAL EXIT")
        print("="*60)
        
        try:
            # Get positions
            positions = self.current_client.get_positions()
            positions_data = positions.get('data', [])
            open_positions = [p for p in positions_data if p.get('quantity', 0) != 0]
            
            if not open_positions:
                print("✅ No open positions")
                return
            
            # Display positions
            print("\nSelect position for partial exit:\n")
            for i, pos in enumerate(open_positions, 1):
                symbol = pos.get('tradingsymbol', 'N/A')
                qty = pos.get('quantity', 0)
                ltp = pos.get('last_price', 0)
                pnl = pos.get('pnl', 0)
                pnl_color = '🟢' if pnl >= 0 else '🔴'
                print(f"{i}. {symbol} | Qty: {qty} | LTP: ₹{ltp:.2f} | P&L: {pnl_color} ₹{pnl:.2f}")
            
            choice = int(input("\nSelect position (number): ")) - 1
            if choice < 0 or choice >= len(open_positions):
                print("❌ Invalid selection")
                return
            
            selected = open_positions[choice]
            qty = selected.get('quantity', 0)
            
            print(f"\nSelected: {selected.get('tradingsymbol', 'N/A')}")
            print(f"Current Qty: {abs(qty)}")
            
            # Exit percentage selection
            print("\nHow much to exit?")
            print("  1 = 25% ({} contracts)".format(int(abs(qty) * 0.25)))
            print("  2 = 50% ({} contracts)".format(int(abs(qty) * 0.5)))
            print("  3 = 75% ({} contracts)".format(int(abs(qty) * 0.75)))
            print("  4 = Custom quantity")
            
            exit_choice = input("Choose (1-4): ").strip()
            
            if exit_choice == '1':
                exit_qty = int(abs(qty) * 0.25)
            elif exit_choice == '2':
                exit_qty = int(abs(qty) * 0.5)
            elif exit_choice == '3':
                exit_qty = int(abs(qty) * 0.75)
            elif exit_choice == '4':
                exit_qty = int(input("Enter quantity to exit: "))
            else:
                print("❌ Invalid choice")
                return
            
            if exit_qty <= 0 or exit_qty > abs(qty):
                print(f"❌ Invalid quantity. Must be between 1 and {abs(qty)}")
                return
            
            transaction_type = "SELL" if qty > 0 else "BUY"
            
            confirm = input(f"\n⚠️  Exit {exit_qty} contracts ({exit_qty/abs(qty)*100:.0f}%)? (y/n): ").strip().lower()
            
            if confirm in ['y', 'yes']:
                entry_time = datetime.now()
                
                result = self.current_client.place_order(
                    instrument_key=selected.get('instrument_token', ''),
                    quantity=exit_qty,
                    transaction_type=transaction_type,
                    order_type="MARKET",
                    product="I",
                )
                
                exit_time = datetime.now()
                execution_ms = (exit_time - entry_time).total_seconds() * 1000
                time_str = exit_time.strftime('%H:%M:%S')
                
                if result:
                    remaining = abs(qty) - exit_qty
                    print(f"✅ Partial exit successful at {time_str} ({execution_ms:.0f}ms)")
                    print(f"   Exited: {exit_qty} | Remaining: {remaining}")
                else:
                    print("❌ Order failed")
            else:
                print("❌ Cancelled")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _partial_exit_multi_account(self):
        """Partially exit positions across multiple broker accounts."""
        try:
            # Collect positions from all brokers
            all_positions = []
            for broker_key, broker_info in self.active_brokers.items():
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    positions_response = client.get_positions()
                    positions = positions_response.get('data', [])
                    for pos in positions:
                        # Only include active positions (non-zero quantity)
                        qty = pos.get('quantity', 0)
                        if qty != 0:
                            pos['broker_name'] = account_name
                            pos['client'] = client
                            all_positions.append(pos)
                except Exception as e:
                    print(f"❌ Error fetching positions from {account_name}: {e}")
            
            if not all_positions:
                print("\n⚠️  No open positions found")
                return
            
            print("\n" + "="*60)
            print("🚪 PARTIAL EXIT (Multi-Account)")
            print("="*60)
            
            # Display positions
            print(f"\n{'No.':<5}{'Broker':<15}{'Symbol':<30}{'Qty':<10}{'LTP':<12}{'P&L':<15}{'Entry Time':<12}")
            print("="*105)
            
            for i, pos in enumerate(all_positions, 1):
                symbol = pos.get('tradingsymbol', 'N/A')
                qty = pos.get('quantity', 0)
                ltp = pos.get('last_price', 0)
                pnl = pos.get('pnl', 0)
                broker_name = pos.get('broker_name', 'N/A')
                
                # Get order time
                order_time = pos.get('order_timestamp') or pos.get('created_at') or pos.get('buy_date') or 'N/A'
                if order_time != 'N/A':
                    try:
                        if 'T' in str(order_time):
                            dt = datetime.fromisoformat(str(order_time).replace('Z', '+00:00'))
                            order_time = dt.strftime('%H:%M:%S')
                        else:
                            order_time = str(order_time).split()[1] if len(str(order_time).split()) > 1 else str(order_time)[:8]
                    except:
                        pass
                
                pnl_color = '🟢' if pnl >= 0 else '🔴'
                print(f"{i:<5}{broker_name:<15}{symbol:<30}{qty:<10}₹{ltp:<11.2f}{pnl_color} ₹{pnl:<13.2f}{order_time:<12}")
            
            # Exit options
            print("\n" + "="*60)
            print("Partial Exit Options:")
            print("  1 = 25% of position")
            print("  2 = 50% of position")
            print("  3 = 75% of position")
            print("  4 = Custom quantity")
            print("  Enter position number to select, then choose exit %")
            
            choice = input("\nSelect position (number): ").strip()
            
            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(all_positions):
                    print("❌ Invalid selection")
                    return
                
                selected = all_positions[idx]
                qty = selected.get('quantity', 0)
                
                print(f"\nSelected: {selected.get('tradingsymbol', 'N/A')} ({selected.get('broker_name')})")
                print(f"Current Qty: {abs(qty)}")
                
                # Exit percentage selection
                print("\nHow much to exit?")
                print("  1 = 25% ({} contracts)".format(int(abs(qty) * 0.25)))
                print("  2 = 50% ({} contracts)".format(int(abs(qty) * 0.5)))
                print("  3 = 75% ({} contracts)".format(int(abs(qty) * 0.75)))
                print("  4 = Custom quantity")
                
                exit_choice = input("Choose (1-4): ").strip()
                
                if exit_choice == '1':
                    exit_qty = int(abs(qty) * 0.25)
                elif exit_choice == '2':
                    exit_qty = int(abs(qty) * 0.5)
                elif exit_choice == '3':
                    exit_qty = int(abs(qty) * 0.75)
                elif exit_choice == '4':
                    exit_qty = int(input("Enter quantity to exit: "))
                else:
                    print("❌ Invalid choice")
                    return
                
                if exit_qty <= 0 or exit_qty > abs(qty):
                    print(f"❌ Invalid quantity. Must be between 1 and {abs(qty)}")
                    return
                
                transaction_type = "SELL" if qty > 0 else "BUY"
                
                confirm = input(f"\n⚠️  Exit {exit_qty} contracts ({exit_qty/abs(qty)*100:.0f}%)? (y/n): ").strip().lower()
                
                if confirm in ['y', 'yes']:
                    client = selected.get('client')
                    entry_time = datetime.now()
                    
                    result = client.place_order(
                        instrument_key=selected.get('instrument_token', ''),
                        quantity=exit_qty,
                        transaction_type=transaction_type,
                        order_type="MARKET",
                        product="I",
                    )
                    
                    exit_time = datetime.now()
                    execution_ms = (exit_time - entry_time).total_seconds() * 1000
                    time_str = exit_time.strftime('%H:%M:%S')
                    
                    if result:
                        remaining = abs(qty) - exit_qty
                        print(f"✅ Partial exit successful at {time_str} ({execution_ms:.0f}ms)")
                        print(f"   Exited: {exit_qty} | Remaining: {remaining}")
                    else:
                        print("❌ Order failed")
                else:
                    print("❌ Cancelled")
            
            except ValueError:
                print("❌ Invalid input")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def cancel_position(self):
        """Cancel pending/open orders (not executed positions)."""
        if not self.multi_account_mode and not self.current_client:
            print("❌ No broker selected")
            return
        
        if self.multi_account_mode:
            self._cancel_multi_account_orders()
            return
        
        print("\n" + "="*60)
        print("❌ CANCEL PENDING ORDERS")
        print("="*60)
        
        try:
            # Get order history to find pending orders
            orders_response = self.current_client.get_order_history()
            orders = orders_response.get('data', [])
            
            # Filter for pending/open orders
            pending_orders = []
            for order in orders:
                status = order.get('status', '').upper()
                # Status can be: OPEN, PENDING, TRIGGER_PENDING, etc.
                if status in ['OPEN', 'PENDING', 'TRIGGER_PENDING', 'PENDING_NEW', 'VALIDATION_PENDING']:
                    pending_orders.append(order)
            
            if not pending_orders:
                print("✅ No pending orders to cancel")
                return
            
            # Display pending orders
            print(f"\nFound {len(pending_orders)} pending order(s):\n")
            for i, order in enumerate(pending_orders, 1):
                symbol = order.get('tradingsymbol', order.get('trading_symbol', 'N/A'))
                qty = order.get('quantity', 0)
                order_type = order.get('order_type', 'N/A')
                transaction = order.get('transaction_type', 'N/A')
                price = order.get('price', 0)
                trigger_price = order.get('trigger_price', 0)
                order_id = order.get('order_id', 'N/A')
                
                print(f"{i}. {symbol}")
                print(f"   Type: {transaction} {order_type} | Qty: {qty}")
                if trigger_price and trigger_price > 0:
                    print(f"   🛡️  Stop Loss Trigger: ₹{trigger_price:.2f} | Limit: ₹{price:.2f}")
                else:
                    print(f"   Price: ₹{price:.2f}")
                print(f"   Order ID: {order_id}")
                print()
            
            print(f"{len(pending_orders) + 1}. Cancel ALL pending orders")
            
            choice = input("\nSelect order to cancel (number): ").strip()
            
            if choice == str(len(pending_orders) + 1):
                # Cancel all
                confirm = input(f"\n⚠️  Cancel ALL {len(pending_orders)} pending order(s)? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    success = 0
                    for order in pending_orders:
                        try:
                            order_id = order.get('order_id', '')
                            if order_id:
                                self.current_client.cancel_order(order_id)
                                success += 1
                        except Exception as e:
                            print(f"   ⚠️  Failed to cancel order {order_id}: {e}")
                    
                    print(f"\n✅ Cancelled {success}/{len(pending_orders)} order(s)")
                else:
                    print("❌ Cancelled")
            else:
                # Cancel specific order
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(pending_orders):
                        selected = pending_orders[idx]
                        order_id = selected.get('order_id', '')
                        symbol = selected.get('tradingsymbol', selected.get('trading_symbol', 'N/A'))
                        
                        confirm = input(f"\n⚠️  Cancel order for {symbol}? (y/n): ").strip().lower()
                        
                        if confirm in ['y', 'yes']:
                            result = self.current_client.cancel_order(order_id)
                            print("✅ Order cancelled successfully!")
                        else:
                            print("❌ Cancelled")
                    else:
                        print("❌ Invalid selection")
                except ValueError:
                    print("❌ Invalid input")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _cancel_multi_account_orders(self):
        """Cancel pending orders across all brokers."""
        print("\n" + "="*60)
        print("❌ CANCEL PENDING ORDERS (Multi-Account)")
        print("="*60)
        
        all_pending = {}
        
        for broker_name, broker_info in self.active_brokers.items():
            try:
                client = broker_info['client']
                orders_response = client.get_order_history()
                orders = orders_response.get('data', [])
                
                pending = [o for o in orders if o.get('status', '').upper() in 
                          ['OPEN', 'PENDING', 'TRIGGER_PENDING', 'PENDING_NEW', 'VALIDATION_PENDING']]
                
                if pending:
                    all_pending[broker_name] = {'client': client, 'orders': pending, 'name': broker_info['name']}
            except Exception as e:
                print(f"⚠️  {broker_name.upper()}: Error fetching orders - {e}")
        
        if not all_pending:
            print("✅ No pending orders across all accounts")
            return
        
        # Display all pending orders grouped by broker
        order_list = []
        for broker_name, data in all_pending.items():
            print(f"\n🔸 {broker_name.upper()} ({data['name']})")
            print("─" * 60)
            for order in data['orders']:
                symbol = order.get('tradingsymbol', order.get('trading_symbol', 'N/A'))
                qty = order.get('quantity', 0)
                order_type = order.get('order_type', 'N/A')
                transaction = order.get('transaction_type', 'N/A')
                order_id = order.get('order_id', 'N/A')
                
                order_list.append({'broker': broker_name, 'client': data['client'], 'order': order})
                print(f"{len(order_list)}. {symbol} | {transaction} {order_type} | Qty: {qty}")
                print(f"   Order ID: {order_id}")
        
        print(f"\n{len(order_list) + 1}. Cancel ALL pending orders across all accounts")
        
        choice = input("\nSelect order to cancel (number): ").strip()
        
        if choice == str(len(order_list) + 1):
            # Cancel all
            confirm = input(f"\n⚠️  Cancel ALL {len(order_list)} pending order(s)? (y/n): ").strip().lower()
            if confirm in ['y', 'yes']:
                success = 0
                for item in order_list:
                    try:
                        order_id = item['order'].get('order_id', '')
                        if order_id:
                            item['client'].cancel_order(order_id)
                            success += 1
                    except Exception as e:
                        print(f"   ⚠️  Failed: {e}")
                
                print(f"\n✅ Cancelled {success}/{len(order_list)} order(s)")
            else:
                print("❌ Cancelled")
        else:
            # Cancel specific order
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(order_list):
                    item = order_list[idx]
                    order = item['order']
                    order_id = order.get('order_id', '')
                    symbol = order.get('tradingsymbol', order.get('trading_symbol', 'N/A'))
                    
                    confirm = input(f"\n⚠️  Cancel order for {symbol}? (y/n): ").strip().lower()
                    
                    if confirm in ['y', 'yes']:
                        item['client'].cancel_order(order_id)
                        print("✅ Order cancelled successfully!")
                    else:
                        print("❌ Cancelled")
                else:
                    print("❌ Invalid selection")
            except ValueError:
                print("❌ Invalid input")
            except Exception as e:
                print(f"❌ Error: {e}")
    
    def view_closed_positions(self):
        """View closed/completed positions and trades."""
        if not self.multi_account_mode and not self.current_client:
            print("❌ No broker selected")
            return
        
        print("\n" + "="*60)
        print("📜 CLOSED POSITIONS / TRADE HISTORY")
        print("="*60)
        
        if self.multi_account_mode:
            self._view_multi_account_trades()
        else:
            self._view_single_account_trades()
    
    def _view_single_account_trades(self):
        """View trades for single account."""
        try:
            trades_response = self.current_client.get_trade_history()
            trades = trades_response.get('data', [])
            
            if not trades:
                print("✅ No trades found for today")
                return
            
            print(f"\nFound {len(trades)} trade(s):\n")
            
            # Group by symbol for better readability
            from collections import defaultdict
            grouped_trades = defaultdict(list)
            
            for trade in trades:
                # Handle different broker field names
                symbol = (trade.get('tradingsymbol') or 
                         trade.get('trading_symbol') or 
                         trade.get('securityId') or 
                         trade.get('tradingSymbol') or 'N/A')
                
                qty = trade.get('quantity') or trade.get('tradedQuantity') or trade.get('traded_quantity') or 0
                
                # Upstox uses 'average_price', Dhan uses 'tradedPrice' or 'averagePrice'
                price = (trade.get('average_price') or 
                        trade.get('price') or 
                        trade.get('trade_price') or 
                        trade.get('tradedPrice') or 
                        trade.get('averagePrice') or 
                        trade.get('traded_price') or 0)
                
                side = (trade.get('transaction_type') or 
                       trade.get('transactionType') or 
                       trade.get('side') or 'N/A')
                
                if symbol != 'N/A' and qty > 0:
                    # Get and format timestamp - Dhan uses different field names
                    timestamp = (trade.get('trade_timestamp') or 
                                trade.get('order_timestamp') or 
                                trade.get('created_at') or 
                                trade.get('createTime') or 
                                trade.get('transactionTime') or 
                                trade.get('tradeTime') or 
                                trade.get('exchangeTime') or 
                                trade.get('updateTime') or 'N/A')
                    time_str = 'N/A'
                    if timestamp != 'N/A':
                        try:
                            if 'T' in str(timestamp):
                                dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
                                time_str = dt.strftime('%H:%M:%S')
                            else:
                                time_str = str(timestamp).split()[1] if len(str(timestamp).split()) > 1 else str(timestamp)[:8]
                        except:
                            pass
                    
                    grouped_trades[symbol].append({
                        'qty': qty,
                        'price': price,
                        'side': side,
                        'time': time_str
                    })
            
            for symbol, symbol_trades in grouped_trades.items():
                print(f"📊 {symbol}")
                total_buy_qty = sum(t['qty'] for t in symbol_trades if t['side'] == 'BUY')
                total_sell_qty = sum(t['qty'] for t in symbol_trades if t['side'] == 'SELL')
                
                # Get entry and exit times
                buy_times = [t['time'] for t in symbol_trades if t['side'] == 'BUY' and t['time'] != 'N/A']
                sell_times = [t['time'] for t in symbol_trades if t['side'] == 'SELL' and t['time'] != 'N/A']
                entry_time = buy_times[0] if buy_times else 'N/A'
                exit_time = sell_times[-1] if sell_times else 'N/A'
                
                for trade in symbol_trades:
                    print(f"   {trade['side']} {trade['qty']} @ ₹{float(trade['price']):,.2f} at {trade['time']}")
                
                print(f"   Entry: {entry_time} | Exit: {exit_time}")
                
                net_qty = total_buy_qty - total_sell_qty
                if net_qty != 0:
                    print(f"   Net: {abs(net_qty)} {'LONG' if net_qty > 0 else 'SHORT'}")
                else:
                    print(f"   ✅ Position Closed")
                print()
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _view_multi_account_trades(self):
        """View trades across all accounts."""
        all_trades = []
        
        for broker_name, broker_info in self.active_brokers.items():
            print(f"\n🔸 {broker_name.upper()} ({broker_info['name']})")
            print("─" * 60)
            
            try:
                client = broker_info['client']
                trades_response = client.get_trade_history()
                trades = trades_response.get('data', [])
                
                if not trades:
                    print("   No trades found")
                    continue
                
                # Group by symbol
                from collections import defaultdict
                grouped_trades = defaultdict(list)
                
                for trade in trades:
                    # Handle different broker field names
                    symbol = (trade.get('tradingsymbol') or 
                             trade.get('trading_symbol') or 
                             trade.get('securityId') or 
                             trade.get('tradingSymbol') or None)
                    
                    qty = trade.get('quantity') or trade.get('tradedQuantity') or trade.get('traded_quantity') or 0
                    
                    # Upstox uses 'average_price', Dhan uses 'tradedPrice' or 'averagePrice'
                    price = (trade.get('average_price') or 
                            trade.get('price') or 
                            trade.get('trade_price') or 
                            trade.get('tradedPrice') or 
                            trade.get('averagePrice') or 
                            trade.get('traded_price') or 0)
                    
                    side = (trade.get('transaction_type') or 
                           trade.get('transactionType') or 
                           trade.get('side') or None)
                    
                    if symbol and qty > 0:
                        # Get and format timestamp - Dhan uses different field names
                        timestamp = (trade.get('trade_timestamp') or 
                                    trade.get('order_timestamp') or 
                                    trade.get('created_at') or 
                                    trade.get('createTime') or 
                                    trade.get('transactionTime') or 
                                    trade.get('tradeTime') or 
                                    trade.get('exchangeTime') or 
                                    trade.get('updateTime') or 'N/A')
                        time_str = 'N/A'
                        if timestamp != 'N/A':
                            try:
                                if 'T' in str(timestamp):
                                    dt = datetime.fromisoformat(str(timestamp).replace('Z', '+00:00'))
                                    time_str = dt.strftime('%H:%M:%S')
                                else:
                                    time_str = str(timestamp).split()[1] if len(str(timestamp).split()) > 1 else str(timestamp)[:8]
                            except:
                                pass
                        
                        grouped_trades[symbol].append({
                            'qty': qty,
                            'price': price,
                            'side': side,
                            'time': time_str
                        })
                        
                        all_trades.append({
                            'broker': broker_name,
                            'symbol': symbol,
                            'trade': trade
                        })
                
                if not grouped_trades:
                    print("   No valid trades found")
                    continue
                
                print(f"   {len(grouped_trades)} unique symbol(s):\n")
                
                for symbol, symbol_trades in grouped_trades.items():
                    total_buy_qty = sum(t['qty'] for t in symbol_trades if t['side'] == 'BUY')
                    total_sell_qty = sum(t['qty'] for t in symbol_trades if t['side'] == 'SELL')
                    
                    # Get entry and exit times
                    buy_times = [t['time'] for t in symbol_trades if t['side'] == 'BUY' and t['time'] != 'N/A']
                    sell_times = [t['time'] for t in symbol_trades if t['side'] == 'SELL' and t['time'] != 'N/A']
                    entry_time = buy_times[0] if buy_times else 'N/A'
                    exit_time = sell_times[-1] if sell_times else 'N/A'
                    
                    print(f"   📊 {symbol}")
                    print(f"      BUY: {total_buy_qty} | SELL: {total_sell_qty}")
                    print(f"      Entry: {entry_time} | Exit: {exit_time}")
                    
                    # Calculate average prices
                    buy_trades = [t for t in symbol_trades if t['side'] == 'BUY']
                    sell_trades = [t for t in symbol_trades if t['side'] == 'SELL']
                    
                    avg_buy = 0
                    avg_sell = 0
                    
                    if buy_trades:
                        total_buy_value = sum(t['price'] * t['qty'] for t in buy_trades)
                        total_buy_qty = sum(t['qty'] for t in buy_trades)
                        if total_buy_qty > 0 and total_buy_value > 0:
                            avg_buy = total_buy_value / total_buy_qty
                            print(f"      Avg Buy: ₹{avg_buy:,.2f}")
                        else:
                            print(f"      Avg Buy: ₹0.00")
                    
                    if sell_trades:
                        total_sell_value = sum(t['price'] * t['qty'] for t in sell_trades)
                        total_sell_qty = sum(t['qty'] for t in sell_trades)
                        if total_sell_qty > 0 and total_sell_value > 0:
                            avg_sell = total_sell_value / total_sell_qty
                            print(f"      Avg Sell: ₹{avg_sell:,.2f}")
                        else:
                            print(f"      Avg Sell: ₹0.00")
                    
                    net_qty = total_buy_qty - total_sell_qty
                    if net_qty != 0:
                        print(f"      Net: {abs(net_qty)} {'LONG' if net_qty > 0 else 'SHORT'}")
                    else:
                        print(f"      ✅ Closed")
                    print()
            
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        if all_trades:
            print(f"\n{'═'*60}")
            print(f"Total trades across all accounts: {len(all_trades)}")
            print(f"{'═'*60}")
    
    def view_portfolio(self):
        """View portfolio summary."""
        if not self.multi_account_mode and not self.current_client:
            print("❌ No broker selected")
            return
        
        if self.multi_account_mode:
            self._view_multi_account_portfolio()
            return
        
        print("\n" + "="*60)
        print("📊 PORTFOLIO")
        print("="*60)
        
        try:
            # Get funds
            funds = self.current_client.get_funds_and_margin()
            equity = funds.get('data', {}).get('equity', {})
            
            available = equity.get('available_margin', 0)
            used = equity.get('used_margin', 0)
            
            print(f"\n💰 Funds:")
            print(f"   Available: ₹{float(available):,.2f}")
            print(f"   Used: ₹{float(used):,.2f}")
            
            # Get positions for P&L
            positions = self.current_client.get_positions()
            positions_data = positions.get('data', [])
            
            total_pnl = sum(float(p.get('pnl', 0) or p.get('unrealised', 0) or 0) 
                          for p in positions_data)
            
            if total_pnl != 0:
                pnl_symbol = "🟢" if total_pnl >= 0 else "🔴"
                print(f"\n📈 Today's P&L: {pnl_symbol} ₹{total_pnl:,.2f}")
            
            # Get holdings
            holdings = self.current_client.get_holdings()
            holdings_data = holdings.get('data', [])
            print(f"\n📦 Holdings: {len(holdings_data)}")
            print(f"💼 Positions: {len([p for p in positions_data if p.get('quantity', 0) != 0])}")
            
            # Trading metrics
            print(f"\n{'─'*60}")
            print("📊 TODAY'S TRADING METRICS")
            print(f"{'─'*60}")
            
            metrics = self._get_trade_metrics(self.current_client)
            print(f"📈 Total Trades: {metrics['trades']}")
            
            if metrics['roi'] != 0:
                roi_symbol = "🟢" if metrics['roi'] >= 0 else "🔴"
                print(f"💹 ROI: {roi_symbol} {metrics['roi']:.2f}%")
            else:
                print(f"💹 ROI: 0.00%")
            
            print(f"⏱️  Avg Holding: {metrics['avg_holding']}")
            
            # Margin utilization
            if float(used) > 0 and float(available) > 0:
                total_funds = float(available) + float(used)
                utilization = (float(used) / total_funds * 100)
                util_bar = "█" * int(utilization / 10) + "░" * (10 - int(utilization / 10))
                print(f"\n📊 Margin Utilization: [{util_bar}] {utilization:.1f}%")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _view_multi_account_portfolio(self):
        """View combined portfolio across all brokers."""
        print("\n" + "="*60)
        print("📊 MULTI-ACCOUNT PORTFOLIO")
        print("="*60)
        
        total_available = 0
        total_used = 0
        total_pnl = 0
        total_positions = 0
        
        for broker_name, broker_info in self.active_brokers.items():
            print(f"\n🔸 {broker_name.upper()} ({broker_info['name']})")
            print("─" * 60)
            
            try:
                client = broker_info['client']
                
                # Get funds
                funds = client.get_funds_and_margin()
                equity = funds.get('data', {}).get('equity', {})
                
                available = equity.get('available_margin', 0)
                used = equity.get('used_margin', 0)
                
                total_available += float(available)
                total_used += float(used)
                
                print(f"   Available: ₹{float(available):,.2f}")
                print(f"   Used: ₹{float(used):,.2f}")
                
                # Get positions
                positions = client.get_positions()
                positions_data = positions.get('data', [])
                
                broker_pnl = sum(float(p.get('pnl', 0) or p.get('unrealised', 0) or 0) 
                               for p in positions_data)
                broker_positions = len([p for p in positions_data if p.get('quantity', 0) != 0])
                
                total_pnl += broker_pnl
                total_positions += broker_positions
                
                if broker_pnl != 0:
                    pnl_symbol = "🟢" if broker_pnl >= 0 else "🔴"
                    print(f"   P&L: {pnl_symbol} ₹{broker_pnl:,.2f}")
                
                print(f"   Positions: {broker_positions}")
            
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        print(f"\n{'═'*60}")
        print(f"COMBINED SUMMARY")
        print(f"{'═'*60}")
        print(f"💰 Total Available: ₹{total_available:,.2f}")
        print(f"💰 Total Used: ₹{total_used:,.2f}")
        if total_pnl != 0:
            pnl_symbol = "🟢" if total_pnl >= 0 else "🔴"
            print(f"📈 Combined P&L: {pnl_symbol} ₹{total_pnl:,.2f}")
        print(f"💼 Total Positions: {total_positions}")
        
        # Combined trading metrics
        print(f"\n{'─'*60}")
        print("📊 TODAY'S COMBINED METRICS")
        print(f"{'─'*60}")
        
        total_trades = 0
        combined_roi = 0
        
        for broker_name, broker_info in self.active_brokers.items():
            try:
                metrics = self._get_trade_metrics(broker_info['client'])
                total_trades += metrics['trades']
            except:
                pass
        
        print(f"📈 Total Trades (All Accounts): {total_trades}")
        
        # Combined ROI
        if total_used > 0:
            combined_roi = (total_pnl / total_used * 100)
            roi_symbol = "🟢" if combined_roi >= 0 else "🔴"
            print(f"💹 Combined ROI: {roi_symbol} {combined_roi:.2f}%")
        else:
            print(f"💹 Combined ROI: 0.00%")
        
        # Combined margin utilization
        if total_used > 0 and total_available > 0:
            total_funds = total_available + total_used
            utilization = (total_used / total_funds * 100)
            util_bar = "█" * int(utilization / 10) + "░" * (10 - int(utilization / 10))
            print(f"\n📊 Combined Margin: [{util_bar}] {utilization:.1f}%")
        
        print(f"{'═'*60}")
    
    def add_modify_stop_loss(self):
        """Interactive stop loss addition/modification with +/- controls for all positions."""
        if not self.multi_account_mode and not self.current_client:
            print("❌ No broker selected")
            return
        
        print("\n" + "="*60)
        print("🛡️  ADD/MODIFY STOP LOSS")
        print("="*60)
        
        # Get all open positions
        all_positions = []
        
        if self.multi_account_mode:
            for broker_key, broker_info in self.active_brokers.items():
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    positions_response = client.get_positions()
                    positions = positions_response.get('data', [])
                    for pos in positions:
                        qty = pos.get('quantity', 0)
                        if qty > 0:  # Only LONG positions can have stop loss
                            pos['broker_name'] = account_name
                            pos['broker_key'] = broker_key
                            pos['client'] = client
                            all_positions.append(pos)
                except Exception as e:
                    print(f"❌ Error fetching positions from {broker_info['name']}: {e}")
        else:
            try:
                positions_response = self.current_client.get_positions()
                positions = positions_response.get('data', [])
                for pos in positions:
                    qty = pos.get('quantity', 0)
                    if qty > 0:
                        pos['broker_name'] = 'Current'
                        pos['broker_key'] = 'current'
                        pos['client'] = self.current_client
                        all_positions.append(pos)
            except Exception as e:
                print(f"❌ Error fetching positions: {e}")
                return
        
        if not all_positions:
            print("\n⚠️  No long positions found")
            print("💡 Stop loss can only be set on BUY positions")
            return
        
        # Display all positions
        print(f"\n{'No.':<5}{'Broker':<15}{'Symbol':<30}{'Qty':<10}{'Entry':<12}{'LTP':<12}{'P&L':<15}")
        print("="*100)
        
        for i, pos in enumerate(all_positions, 1):
            symbol = pos.get('tradingsymbol', 'N/A')
            qty = pos.get('quantity', 0)
            ltp = pos.get('last_price', 0)
            avg_price = pos.get('average_price') or pos.get('buy_avg') or pos.get('buyAvg') or ltp
            pnl = pos.get('pnl', 0)
            broker_name = pos.get('broker_name', 'N/A')
            pnl_color = '🟢' if pnl >= 0 else '🔴'
            print(f"{i:<5}{broker_name:<15}{symbol:<30}{qty:<10}₹{avg_price:<11.2f}₹{ltp:<11.2f}{pnl_color} ₹{pnl:.2f}")
        
        # Calculate initial stop loss for all positions (5% below entry)
        sl_configs = []
        for pos in all_positions:
            avg_price = pos.get('average_price') or pos.get('buy_avg') or pos.get('buyAvg') or pos.get('last_price', 0)
            default_sl = avg_price * 0.95
            sl_configs.append({
                'position': pos,
                'entry_price': avg_price,
                'current_sl': default_sl,
                'ltp': pos.get('last_price', 0)
            })
        
        print(f"\n{'='*60}")
        print(f"🛡️  STOP LOSS CONFIGURATION (ALL POSITIONS)")
        print(f"{'='*60}")
        print("💡 Same SL % will apply to all positions")
        
        # Interactive +/- control
        sl_percent = 5.0  # Default 5% below entry
        
        while True:
            # Calculate SL for each position based on current percentage
            print(f"\n{'─'*60}")
            print(f"Stop Loss Distance: {sl_percent:.2f}% below entry")
            print(f"{'─'*60}")
            
            # Show SL for each position
            total_potential_loss = 0
            print(f"\n{'Broker':<15}{'Symbol':<30}{'Entry':<12}{'SL Price':<12}{'Loss':<12}")
            print("="*80)
            
            for config in sl_configs:
                pos = config['position']
                entry = config['entry_price']
                sl_price = entry * (1 - sl_percent / 100)
                qty = pos.get('quantity', 0)
                potential_loss = (entry - sl_price) * qty
                total_potential_loss += potential_loss
                
                broker_name = pos.get('broker_name', 'N/A')
                symbol = pos.get('tradingsymbol', 'N/A')
                print(f"{broker_name:<15}{symbol:<30}₹{entry:<11.2f}₹{sl_price:<11.2f}₹{potential_loss:.2f}")
            
            print("="*80)
            print(f"Total Potential Loss: ₹{total_potential_loss:,.2f}")
            print("="*80)
            
            print("\nControls:")
            print("  + = Increase SL % by 0.5%")
            print("  - = Decrease SL % by 0.5%")
            print("  ++ = Increase SL % by 1%")
            print("  -- = Decrease SL % by 1%")
            print("  [number] = Set exact SL %")
            print("  's' = Save and place SL orders for ALL positions")
            print("  'x' = Cancel")
            
            cmd = input("\nCommand: ").strip().lower()
            
            if cmd == '+':
                sl_percent += 0.5
                print(f"✅ SL % increased to {sl_percent:.2f}%")
            elif cmd == '-':
                sl_percent = max(0.5, sl_percent - 0.5)
                print(f"✅ SL % decreased to {sl_percent:.2f}%")
            elif cmd == '++':
                sl_percent += 1.0
                print(f"✅ SL % increased to {sl_percent:.2f}%")
            elif cmd == '--':
                sl_percent = max(0.5, sl_percent - 1.0)
                print(f"✅ SL % decreased to {sl_percent:.2f}%")
            elif cmd == 's':
                # Validate and confirm
                if sl_percent >= 100:
                    print("⚠️  Stop loss % too high!")
                    continue
                
                print(f"\n{'='*60}")
                print(f"SUMMARY: {len(all_positions)} Stop Loss Orders")
                print(f"{'='*60}")
                for config in sl_configs:
                    pos = config['position']
                    entry = config['entry_price']
                    sl_price = entry * (1 - sl_percent / 100)
                    broker_name = pos.get('broker_name', 'N/A')
                    symbol = pos.get('tradingsymbol', 'N/A')
                    print(f"{broker_name}: {symbol} → SL ₹{sl_price:.2f}")
                print(f"{'='*60}")
                
                confirm = input(f"\n⚠️  Place {len(all_positions)} SL orders? (y/n): ").strip().lower()
                
                if confirm in ['y', 'yes']:
                    from datetime import datetime
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    
                    def place_sl_order(config):
                        """Place SL order for a single position."""
                        try:
                            pos = config['position']
                            client = pos.get('client')
                            broker_name = pos.get('broker_name')
                            symbol = pos.get('tradingsymbol', 'N/A')
                            entry = config['entry_price']
                            sl_price = entry * (1 - sl_percent / 100)
                            qty = pos.get('quantity', 0)
                            
                            entry_time = datetime.now()
                            
                            result = client.place_order(
                                instrument_key=pos.get('instrument_token', ''),
                                quantity=qty,
                                transaction_type="SELL",
                                order_type="SL",
                                product="I",
                                price=sl_price * 0.99,  # Limit price slightly below trigger
                                trigger_price=sl_price
                            )
                            
                            exit_time = datetime.now()
                            execution_ms = (exit_time - entry_time).total_seconds() * 1000
                            
                            if result:
                                order_id = result.get('data', {}).get('order_id', 'N/A')
                                return {
                                    'success': True,
                                    'broker': broker_name,
                                    'symbol': symbol,
                                    'sl_price': sl_price,
                                    'order_id': order_id,
                                    'ms': execution_ms
                                }
                            return {'success': False, 'broker': broker_name, 'symbol': symbol}
                        except Exception as e:
                            return {
                                'success': False,
                                'broker': config['position'].get('broker_name'),
                                'symbol': config['position'].get('tradingsymbol', 'N/A'),
                                'error': str(e)
                            }
                    
                    # Execute all SL orders in parallel
                    results = []
                    with ThreadPoolExecutor(max_workers=len(sl_configs)) as executor:
                        futures = {executor.submit(place_sl_order, config): config for config in sl_configs}
                        
                        for future in as_completed(futures):
                            result = future.result()
                            results.append(result)
                            if result['success']:
                                print(f"✅ {result['broker']}: {result['symbol']} → SL ₹{result['sl_price']:.2f} ({result['ms']:.0f}ms)")
                                print(f"   Order ID: {result['order_id']}")
                            else:
                                print(f"❌ {result['broker']}: {result['symbol']} - {result.get('error', 'Failed')}")
                    
                    success = sum(1 for r in results if r['success'])
                    print(f"\n✅ Stop Loss orders placed: {success}/{len(sl_configs)}")
                    
                    # Show timing analysis
                    if success > 1:
                        successful_times = [r['ms'] for r in results if r['success']]
                        max_diff = max(successful_times) - min(successful_times)
                        print(f"⏱️  Max execution difference: {max_diff:.0f}ms")
                
                break
            elif cmd == 'x':
                print("❌ Cancelled")
                break
            else:
                # Try to parse as exact percentage
                try:
                    new_percent = float(cmd)
                    if new_percent >= 100:
                        print("⚠️  Stop loss % too high!")
                    elif new_percent <= 0:
                        print("⚠️  Stop loss % must be positive!")
                    else:
                        sl_percent = new_percent
                        print(f"✅ SL % set to {sl_percent:.2f}%")
                except ValueError:
                    print("❌ Invalid command")
    
    def manage_stop_losses(self):
        """View and manage active stop losses."""
        print("\n" + "="*60)
        print("🛡️  MANAGE STOP LOSSES")
        print("="*60)
        
        if not self.active_stop_losses:
            print("✅ No active stop losses")
            print("\n💡 Stop losses are activated when you:")
            print("   - Place a BUY order and select 'Auto Trailing' or 'Manual' stop loss")
            return
        
        print(f"\nActive Stop Losses: {len(self.active_stop_losses)}\n")
        
        sl_list = []
        for position_key, sl_config in self.active_stop_losses.items():
            sl_list.append((position_key, sl_config))
            idx = len(sl_list)
            
            print(f"{idx}. {sl_config['symbol_info']} ({sl_config['broker'].upper()})")
            print(f"   Entry: ₹{sl_config['entry_price']:.2f}")
            print(f"   🛡️  Current SL: ₹{sl_config['current_sl']:.2f}")
            print(f"   Highest: ₹{sl_config['highest_price']:.2f}")
            print(f"   Trail: {sl_config['trail_percent']}%")
            
            # Show SL order ID if exists
            if sl_config.get('sl_order_id'):
                print(f"   Order ID: {sl_config['sl_order_id']}")
            
            # Show current price if available
            current_price = self._get_current_price(sl_config['broker'], sl_config['instrument_key'])
            if current_price:
                pnl_percent = ((current_price - sl_config['entry_price']) / sl_config['entry_price'] * 100)
                pnl_symbol = "🟢" if pnl_percent >= 0 else "🔴"
                print(f"   Current Price: ₹{current_price:.2f} {pnl_symbol} {pnl_percent:+.2f}%")
            print()
        
        print("Actions:")
        print("  'r' - Remove stop loss")
        print("  'm' - Modify trail %")
        print("  'x' - Exit")
        
        choice = input("\nSelect action: ").strip().lower()
        
        if choice == 'r':
            sl_num = input("Remove which stop loss? (number): ").strip()
            try:
                idx = int(sl_num) - 1
                if 0 <= idx < len(sl_list):
                    position_key, sl_config = sl_list[idx]
                    confirm = input(f"Remove stop loss for {sl_config['symbol_info']}? (y/n): ").strip().lower()
                    if confirm in ['y', 'yes']:
                        del self.active_stop_losses[position_key]
                        print("✅ Stop loss removed")
                    else:
                        print("❌ Cancelled")
                else:
                    print("❌ Invalid number")
            except ValueError:
                print("❌ Invalid input")
        
        elif choice == 'm':
            sl_num = input("Modify which stop loss? (number): ").strip()
            try:
                idx = int(sl_num) - 1
                if 0 <= idx < len(sl_list):
                    position_key, sl_config = sl_list[idx]
                    new_trail = input(f"New trail % (current: {sl_config['trail_percent']}%): ").strip()
                    if new_trail:
                        sl_config['trail_percent'] = float(new_trail)
                        # Recalculate stop loss
                        sl_config['current_sl'] = sl_config['highest_price'] * (1 - sl_config['trail_percent'] / 100)
                        print(f"✅ Trail updated to {new_trail}% | New SL: ₹{sl_config['current_sl']:.2f}")
                else:
                    print("❌ Invalid number")
            except (ValueError, KeyError):
                print("❌ Invalid input")
    
    def generate_access_token(self):
        """Generate/refresh access token for brokers."""
        print("\n" + "="*60)
        print("🔑 GENERATE ACCESS TOKEN")
        print("="*60)
        print("1. Upstox")
        print("2. Dhan")
        print("="*60)
        
        choice = input("\nSelect broker (1-2): ").strip()
        
        if choice == "1":
            self._generate_upstox_token()
        elif choice == "2":
            self._generate_dhan_token()
        else:
            print("❌ Invalid choice")
    
    def _generate_upstox_token(self):
        """Generate Upstox access token via OAuth flow."""
        print("\n" + "="*60)
        print("🔑 UPSTOX TOKEN GENERATION")
        print("="*60)
        
        api_key = os.getenv("UPSTOX_API_KEY")
        api_secret = os.getenv("UPSTOX_API_SECRET")
        
        if not api_key or not api_secret:
            print("❌ API Key/Secret missing in .env file")
            print("\nAdd these to your .env file:")
            print("UPSTOX_API_KEY=your_api_key")
            print("UPSTOX_API_SECRET=your_api_secret")
            return
        
        # OAuth URL
        redirect_uri = "https://127.0.0.1:8080"
        auth_url = f"https://api.upstox.com/v2/login/authorization/dialog?client_id={api_key}&redirect_uri={redirect_uri}&response_type=code"
        
        print("\n📋 STEPS:")
        print("1. Open this URL in your browser:")
        print(f"\n{auth_url}\n")
        print("2. Login to Upstox")
        print("3. Authorize the application")
        print("4. Copy the 'code' parameter from the redirect URL")
        print("   (URL will be like: https://127.0.0.1:8080?code=XXXXXX)")
        
        auth_code = input("\n5. Paste the authorization code here: ").strip()
        
        if not auth_code:
            print("❌ No code provided")
            return
        
        # Exchange code for access token
        print("\n🔄 Exchanging code for access token...")
        
        try:
            token_url = "https://api.upstox.com/v2/login/authorization/token"
            data = {
                "code": auth_code,
                "client_id": api_key,
                "client_secret": api_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }
            
            response = requests.post(token_url, data=data, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            access_token = result.get('access_token')
            
            if access_token:
                print("\n✅ Token generated successfully!")
                print(f"\nAccess Token: {access_token}")
                print("\n📝 Add this to your .env file:")
                print(f"UPSTOX_ACCESS_TOKEN={access_token}")
                
                # Ask if user wants to save automatically
                save = input("\n💾 Auto-save to .env file? (y/n): ").strip().lower()
                if save in ['y', 'yes']:
                    self._update_env_file('UPSTOX_ACCESS_TOKEN', access_token)
                    print("✅ Saved to .env file!")
            else:
                print("❌ Failed to get access token")
                print(f"Response: {result}")
        
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _generate_dhan_token(self):
        """Instructions for generating Dhan access token."""
        print("\n" + "="*60)
        print("🔑 DHAN TOKEN GENERATION")
        print("="*60)
        
        print("\n📋 STEPS:")
        print("1. Go to: https://api.dhan.co/")
        print("2. Login with your Dhan credentials")
        print("3. Navigate to 'API Keys' or 'Access Token' section")
        print("4. Generate new access token")
        print("5. Copy the access token")
        
        access_token = input("\n6. Paste the access token here: ").strip()
        
        if not access_token:
            print("❌ No token provided")
            return
        
        print("\n✅ Token received!")
        print(f"\nAccess Token: {access_token}")
        print("\n📝 Add this to your .env file:")
        print(f"DHAN_ACCESS_TOKEN={access_token}")
        
        # Ask if user wants to save automatically
        save = input("\n💾 Auto-save to .env file? (y/n): ").strip().lower()
        if save in ['y', 'yes']:
            self._update_env_file('DHAN_ACCESS_TOKEN', access_token)
            print("✅ Saved to .env file!")
    
    def _update_env_file(self, key, value):
        """Update or add a key-value pair in .env file."""
        env_path = Path('.env')
        
        if env_path.exists():
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            # Check if key exists
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={value}\n"
                    found = True
                    break
            
            # If not found, append
            if not found:
                lines.append(f"\n{key}={value}\n")
            
            # Write back
            with open(env_path, 'w') as f:
                f.writelines(lines)
        else:
            # Create new .env file
            with open(env_path, 'w') as f:
                f.write(f"{key}={value}\n")
    
    def _get_expiries_for_symbol(self, symbol):
        """Get expiries for a given symbol (for GUI)."""
        return self.get_current_expiries(symbol)
    
    def _get_strikes_near_price(self, symbol, expiry, ltp_or_target):
        """Get strike prices near a target price (for GUI)."""
        strikes = []
        try:
            # Round to nearest 50 or 100 based on index
            if symbol in ['NIFTY', 'FINNIFTY', 'MIDCPNIFTY']:
                step = 50
            elif symbol == 'BANKNIFTY':
                step = 100
            elif symbol == 'SENSEX':
                step = 100
            else:
                step = 50
            
            # Round target to nearest step
            base = int(round(ltp_or_target / step) * step)
            
            # Generate strikes around base
            for i in range(-10, 11):
                strikes.append(base + (i * step))
            
            return sorted(strikes)
        except:
            return []
    
    def _place_multi_account_order(self, index_num, expiry, strike, opt_type, quantity, transaction_type):
        """Place order across all active accounts (for GUI)."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def place_single_order(broker_key, broker_info):
            try:
                client = broker_info['client']
                account_name = broker_info['name']
                
                # Get instrument details
                index_name = self.indices[index_num]['name']
                instrument_key = self.format_instrument_key_for_broker(
                    broker_key, index_name, expiry, strike, opt_type,
                    self.indices[index_num]
                )
                
                # Place order
                result = client.place_order(
                    instrument_key=instrument_key,
                    quantity=quantity,
                    transaction_type=transaction_type,
                    order_type="MARKET",
                    product="I"
                )
                
                return {'success': result is not None, 'broker': account_name}
            except Exception as e:
                return {'success': False, 'broker': broker_info.get('name', 'Unknown'), 'error': str(e)}
        
        results = []
        if self.multi_account_mode:
            with ThreadPoolExecutor(max_workers=len(self.active_brokers)) as executor:
                futures = {executor.submit(place_single_order, key, info): key 
                          for key, info in self.active_brokers.items()}
                
                for future in as_completed(futures):
                    results.append(future.result())
        else:
            # Single account
            result = place_single_order(self.current_broker, {
                'client': self.current_client,
                'name': self.account_name
            })
            results.append(result)
        
        return results
    
    def run(self):
        """Main application loop."""
        print("\n" + "="*60)
        print("⚡ TRADERCHAMP - Multi-Broker Trading")
        print("="*60)
        
        # Download/update instrument masters
        self.download_instrument_masters()
        self.load_instrument_masters()
        
        # Select broker first
        if not self.select_broker():
            return
        
        while True:
            print("\n" + "="*60)
            print("📋 MAIN MENU")
            print("="*60)
            print("1️⃣  ⚡ Quick Order")
            print("2️⃣  🛡️  Add/Modify Stop Loss")
            print("3️⃣  📈 Increase Position")
            print("4️⃣  🚪 Exit Position")
            print("5️⃣  🚪 Partial Exit")
            print("6️⃣  💼 View Positions")
            print("7️⃣  📊 View Portfolio")
            print("8️⃣  📜 View Closed Positions")
            print("9️⃣  🔄 Switch Broker")
            print("🔟  ❌ Cancel Active Position (type '10')")
            print("🔑  Generate Access Token (type 'token')")
            print("0️⃣  Exit")
            print("="*60)
            
            choice = input("\nEnter choice: ").strip()
            
            if choice == "1":
                self.quick_order()
            elif choice == "2":
                self.add_modify_stop_loss()
            elif choice == "3":
                self.increase_position()
            elif choice == "4":
                self.exit_order()
            elif choice == "5":
                self.partial_exit()
            elif choice == "6":
                self.view_positions()
            elif choice == "7":
                self.view_portfolio()
            elif choice == "8":
                self.view_closed_positions()
            elif choice == "9":
                self.active_brokers.clear()
                self.multi_account_mode = False
                if self.select_broker():
                    print("✅ Broker/Mode switched")
            elif choice == "10":
                self.cancel_position()
            elif choice.lower() == "token":
                self.generate_access_token()
            elif choice == "0":
                print("\n👋 Goodbye!")
                self.stop_loss_monitor_active = False  # Stop monitor thread
                break
            else:
                print("❌ Invalid choice")


def main():
    """Entry point."""
    app = Traderchamp()
    app.run()


if __name__ == "__main__":
    main()
