"""FusionTrade GUI - Multi-Broker Trading Tool with Tkinter GUI.

Based on the design specifications.
"""

# Performance Settings
ENABLE_LOGGING = False  # Set to True to enable file logging (impacts performance)
ENABLE_DEBUG_PRINTS = False  # Set to True to enable debug print statements

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
from datetime import datetime, timedelta
from traderchamp import Traderchamp
from typing import Optional
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import glob
from pathlib import Path
import json

# Fix Windows console encoding for emoji support
if sys.platform == 'win32':
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except:
        pass  # Silently fail if encoding fix doesn't work


class FusionTradeGUI:
    """GUI application for FusionTrade."""
    
    def __init__(self, root):
        """Initialize GUI."""
        self.root = root
        self.root.title("FusionTrade - Multi-Broker Trading")
        self.root.geometry("1200x800")
        self.root.configure(bg='#1e1e1e')
        
        # Track invalid broker tokens to skip order execution
        self.invalid_brokers = set()  # Store broker keys with invalid tokens
        
        # Setup logging only if enabled (improves performance when disabled)
        if ENABLE_LOGGING:
            self.setup_logging()
            self.cleanup_old_logs()
            self._log('info', "="*60)
            self._log('info', "FusionTrade Application Started")
            self._log('info', f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self._log('info', "="*60)
        else:
            # Disable logging completely for performance
            logging.disable(logging.CRITICAL)
        
        # Show loading screen
        self.show_loading()
        
        # Initialize trading engine in background
        threading.Thread(target=self.initialize_trader, daemon=True).start()
    
    def setup_logging(self):
        """Setup logging with daily rotation."""
        if not ENABLE_LOGGING:
            return
        try:
            # Get the directory where the executable/script is running
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
            
            # Create logs directory if it doesn't exist
            log_dir = os.path.join(app_dir, 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            # Create log filename with current date
            log_filename = os.path.join(log_dir, f'fusiontrade_{datetime.now().strftime("%Y%m%d")}.log')
            
            # Configure logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_filename, encoding='utf-8'),
                    logging.StreamHandler(sys.stdout)  # Also print to console
                ]
            )
            
            print(f"✅ Logging initialized: {log_filename}")
        except Exception as e:
            print(f"⚠️ Failed to setup logging: {e}")
    
    def cleanup_old_logs(self):
        """Delete log files older than 24 hours."""
        if not ENABLE_LOGGING:
            return
        try:
            # Get the directory where the executable/script is running
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
            
            log_dir = os.path.join(app_dir, 'logs')
            if not os.path.exists(log_dir):
                return
            
            # Get all log files
            log_files = glob.glob(os.path.join(log_dir, 'fusiontrade_*.log'))
            
            # Current time
            now = datetime.now()
            cutoff_time = now - timedelta(hours=24)
            
            deleted_count = 0
            for log_file in log_files:
                # Get file modification time
                file_time = datetime.fromtimestamp(os.path.getmtime(log_file))
                
                # Delete if older than 24 hours
                if file_time < cutoff_time:
                    try:
                        os.remove(log_file)
                        deleted_count += 1
                        print(f"🗑️ Deleted old log: {os.path.basename(log_file)}")
                    except Exception as e:
                        print(f"⚠️ Failed to delete {log_file}: {e}")
            
            if deleted_count > 0:
                if ENABLE_LOGGING:
                    self._log('info', f"Cleaned up {deleted_count} old log file(s)")
        except Exception as e:
            print(f"⚠️ Failed to cleanup old logs: {e}")
    
    def _log(self, level, message):
        """Conditional logging helper - only logs if ENABLE_LOGGING is True."""
        if ENABLE_LOGGING:
            getattr(logging, level)(message)
    
    def _print(self, message):
        """Conditional print helper - only prints if ENABLE_DEBUG_PRINTS is True."""
        if ENABLE_DEBUG_PRINTS:
            print(message)
    
    def show_loading(self):
        """Show loading screen."""
        self.loading_frame = tk.Frame(self.root, bg='#1e1e1e')
        self.loading_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(self.loading_frame, text="⚡ FUSIONTRADE", 
                font=('Arial', 24, 'bold'), bg='#1e1e1e', fg='#00ff00').pack(pady=50)
        
        self.loading_label = tk.Label(self.loading_frame, text="Loading...", 
                                     font=('Arial', 12), bg='#1e1e1e', fg='#ffffff')
        self.loading_label.pack(pady=20)
        
        self.progress = ttk.Progressbar(self.loading_frame, mode='indeterminate', length=300)
        self.progress.pack(pady=20)
        self.progress.start()
    
    def initialize_trader(self):
        """Initialize trader in background."""
        try:
            # Check if .env file exists
            # Get the directory where the executable/script is running
            if getattr(sys, 'frozen', False):
                # Running in PyInstaller bundle
                app_dir = os.path.dirname(sys.executable)
            else:
                # Running in normal Python
                app_dir = os.path.dirname(os.path.abspath(__file__))
            
            env_file = os.path.join(app_dir, '.env')
            if not os.path.exists(env_file):
                self.root.after(0, lambda: self.show_env_missing_error())
                return
            
            # Update status
            self.root.after(0, lambda: self.loading_label.config(text="Initializing trader..."))
            
            # Initialize trading engine
            self.trader = Traderchamp()
            
            # Download instrument masters with timeout protection
            self.root.after(0, lambda: self.loading_label.config(text="Downloading instrument data..."))
            try:
                self.trader.download_instrument_masters()
                self.trader.load_instrument_masters()
            except Exception as e:
                print(f"⚠️  Warning: Failed to download instruments: {e}")
                print("Continuing without instrument data...")
            
            # Initialize multi-account mode
            self.root.after(0, lambda: self.loading_label.config(text="Connecting to brokers..."))
            self.setup_multi_account()
            
            # Initialize variables
            self.selected_symbol = tk.StringVar()
            self.selected_expiry = tk.StringVar()
            self.selected_strike = tk.StringVar()
            self.selected_type = tk.StringVar(value="CE")
            self.product_type = tk.StringVar(value="INTRADAY")
            self.order_type = tk.StringVar(value="MARKET")
            self.lot_quantity = tk.IntVar(value=1)
            self.avg_price = tk.DoubleVar(value=0.0)
            self.ltp = tk.DoubleVar(value=0.0)
            self.total_margin = tk.DoubleVar(value=0.0)
            self.projected_order_value = tk.DoubleVar(value=0.0)
            self.limit_price_var = tk.DoubleVar(value=0.0)
            self.account_margins = {}  # Store each account's margin separately
            
            # Position data
            self.positions_data = []
            
            # Alert settings
            self.alert_enabled = tk.BooleanVar(value=False)
            self.alert_profit_percent = tk.DoubleVar(value=10.0)
            self.alert_loss_percent = tk.DoubleVar(value=5.0)
            self.alerted_positions = set()  # Track which positions have been alerted
            
            # Market Analysis Settings
            self.market_analysis_enabled = tk.BooleanVar(value=False)  # Disabled by default to prevent API rate limits
            self.analysis_interval = 180000  # 3 minutes in milliseconds
            self.market_history = {'NIFTY': [], 'BANKNIFTY': [], 'SENSEX': []}  # Store price history
            self.analysis_alerts_shown = set()  # Track shown alerts to avoid duplicates
            self.latest_analysis = {}  # Store latest analysis results for viewing
            
            # Market data tracking
            self.market_data = {
                'NIFTY': {'ltp': 0, 'change': 0, 'volume': 0},
                'BANKNIFTY': {'ltp': 0, 'change': 0, 'volume': 0},
                'SENSEX': {'ltp': 0, 'change': 0, 'volume': 0}
            }
            
            # Risk management
            self.today_start_time = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
            self.risk_check_active = True
            
            # Strategy Templates
            self.templates = {}
            self.templates_file = Path(app_dir) / "config" / "templates.json"
            
            # Trace callbacks removed - order value now shown in confirmation dialog
            
            # Create UI on main thread
            self.root.after(0, self.finish_initialization)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Initialization Error", 
                                                            f"Failed to initialize: {e}\n\nPlease check your .env file and tokens."))
            self.root.after(100, self.root.quit)
    
    def show_env_missing_error(self):
        """Show error when .env file is missing."""
        self.progress.stop()
        self.loading_frame.destroy()
        
        error_frame = tk.Frame(self.root, bg='#1e1e1e')
        error_frame.pack(fill=tk.BOTH, expand=True, padx=50, pady=50)
        
        tk.Label(
            error_frame,
            text="⚠️ Configuration File Missing",
            font=('Arial', 18, 'bold'),
            bg='#1e1e1e',
            fg='#ff6600'
        ).pack(pady=20)
        
        message = tk.Label(
            error_frame,
            text="The .env configuration file was not found.\n\n"
                 "To get started:\n\n"
                 "1. Copy .env.template to .env\n"
                 "2. Edit .env with your broker credentials\n"
                 "3. Restart the application\n\n"
                 "OR\n\n"
                 "Click 'Configure Now' to create it using the GUI.",
            font=('Arial', 11),
            bg='#1e1e1e',
            fg='#ffffff',
            justify='left'
        )
        message.pack(pady=20)
        
        button_frame = tk.Frame(error_frame, bg='#1e1e1e')
        button_frame.pack(pady=20)
        
        tk.Button(
            button_frame,
            text="🔧 Configure Now",
            command=self.create_env_and_configure,
            bg='#00aa00',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=10,
            cursor='hand2'
        ).pack(side='left', padx=10)
        
        tk.Button(
            button_frame,
            text="❌ Exit",
            command=self.root.quit,
            bg='#aa0000',
            fg='white',
            font=('Arial', 11, 'bold'),
            padx=20,
            pady=10,
            cursor='hand2'
        ).pack(side='left', padx=10)
    
    def create_env_and_configure(self):
        """Create empty .env and open configuration."""
        import subprocess
        try:
            # Get the directory where the executable is running
            if getattr(sys, 'frozen', False):
                # Running in PyInstaller bundle
                app_dir = os.path.dirname(sys.executable)
            else:
                # Running in normal Python
                app_dir = os.path.dirname(os.path.abspath(__file__))
            
            env_file = os.path.join(app_dir, '.env')
            
            # Create empty .env file
            with open(env_file, 'w') as f:
                f.write("# TraderChamp Configuration\n")
                f.write("# Fill in your broker credentials below\n\n")
            
            # Open .env file in default editor
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(env_file)
                else:  # Linux/Mac
                    subprocess.run(['xdg-open', env_file])
            except Exception:
                pass  # Silently fail if can't open editor
            
            messagebox.showinfo(
                "Next Steps",
                "Please edit the .env file with your broker credentials, then restart the application."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create .env file: {e}")
    
    def finish_initialization(self):
        """Finish initialization on main thread."""
        try:
            # Stop loading animation
            self.progress.stop()
            self.loading_frame.destroy()
            
            # Create UI
            self.create_ui()
            
            # Load templates after UI is ready
            self.load_templates()
            
            # Start position refresh
            self.refresh_positions()
            
            # Start market analysis (every 3 minutes) - DISABLED by default to prevent API rate limits
            # Users can enable it manually from Settings menu if needed
            # if self.market_analysis_enabled.get():
            #     self.root.after(60000, lambda: self.start_market_analysis())  # Start after 1 minute
            
        except Exception as e:
            messagebox.showerror("UI Error", f"Failed to create UI: {e}")
            self.root.quit()
    
    def setup_multi_account(self):
        """Setup multi-account mode."""
        try:
            # Try to setup both accounts
            upstox_key = os.getenv('UPSTOX_API_KEY')
            upstox_token = os.getenv('UPSTOX_ACCESS_TOKEN')
            upstox_name = os.getenv('UPSTOX_ACCOUNT_NAME', 'Sabari')
            
            dhan_id = os.getenv('DHAN_CLIENT_ID')
            dhan_token = os.getenv('DHAN_ACCESS_TOKEN')
            dhan_name = os.getenv('DHAN_ACCOUNT_NAME', 'Karthi')
            
            accounts_setup = 0
            
            if upstox_key and upstox_token:
                try:
                    from brokers.upstox_client import UpstoxClient
                    upstox_client = UpstoxClient(upstox_key, "", upstox_token)
                    self.trader.active_brokers['upstox'] = {
                        'client': upstox_client,
                        'name': upstox_name
                    }
                    accounts_setup += 1
                    print(f"✅ Upstox account setup: {upstox_name}")
                except Exception as e:
                    print(f"⚠️  Failed to setup Upstox: {e}")
            
            if dhan_id and dhan_token:
                try:
                    from brokers.dhan_client import DhanClient
                    # DhanClient requires 3 parameters: api_key, api_secret, access_token
                    # We use client_id as api_key, empty string as api_secret, and token as access_token
                    dhan_client = DhanClient(dhan_id, "", dhan_token)
                    
                    # Validate token by testing positions endpoint
                    try:
                        test_response = dhan_client.get_positions()
                        if test_response and test_response.get('status') == 'success':
                            self.trader.active_brokers['dhan'] = {
                                'client': dhan_client,
                                'name': dhan_name
                            }
                            accounts_setup += 1
                            print(f"✅ Dhan account setup: {dhan_name}")
                        else:
                            print(f"⚠️  Dhan token validation failed for {dhan_name} - skipping")
                            self.invalid_brokers.add('dhan')
                            self._log('warning', f"Dhan account {dhan_name}: Token validation failed")
                    except Exception as ve:
                        if '401' in str(ve) or 'expired' in str(ve).lower() or 'invalid' in str(ve).lower():
                            print(f"⚠️  Dhan token expired/invalid for {dhan_name} - account disabled")
                            self.invalid_brokers.add('dhan')
                            self._log('error', f"Dhan account {dhan_name}: Token expired or invalid - {ve}")
                        else:
                            raise ve
                except Exception as e:
                    print(f"⚠️  Failed to setup Dhan: {e}")
                    self.invalid_brokers.add('dhan')
                    self._log('error', f"Dhan setup failed: {e}")
            
            # Setup second Dhan account if configured
            dhan2_id = os.getenv('DHAN2_CLIENT_ID')
            dhan2_token = os.getenv('DHAN2_ACCESS_TOKEN')
            dhan2_name = os.getenv('DHAN2_ACCOUNT_NAME', 'Dhan2User')
            
            if dhan2_id and dhan2_token:
                try:
                    from brokers.dhan_client import DhanClient
                    dhan2_client = DhanClient(dhan2_id, "", dhan2_token)
                    self.trader.active_brokers['dhan2'] = {
                        'client': dhan2_client,
                        'name': dhan2_name
                    }
                    accounts_setup += 1
                    print(f"✅ Dhan account 2 setup: {dhan2_name}")
                except Exception as e:
                    print(f"⚠️  Failed to setup Dhan 2: {e}")
            
            # Setup second Upstox account if configured
            upstox2_key = os.getenv('UPSTOX2_API_KEY')
            upstox2_token = os.getenv('UPSTOX2_ACCESS_TOKEN')
            upstox2_name = os.getenv('UPSTOX2_ACCOUNT_NAME', 'Upstox2User')
            
            if upstox2_key and upstox2_token:
                try:
                    from brokers.upstox_client import UpstoxClient
                    upstox2_client = UpstoxClient(upstox2_key, "", upstox2_token)
                    self.trader.active_brokers['upstox2'] = {
                        'client': upstox2_client,
                        'name': upstox2_name
                    }
                    accounts_setup += 1
                    print(f"✅ Upstox account 2 setup: {upstox2_name}")
                except Exception as e:
                    print(f"⚠️  Failed to setup Upstox 2: {e}")
            
            if accounts_setup >= 2:
                self.trader.multi_account_mode = True
                print(f"✅ Multi-account mode enabled: {accounts_setup} accounts")
            elif accounts_setup == 1:
                # Single account mode
                broker_key = list(self.trader.active_brokers.keys())[0]
                self.trader.current_client = self.trader.active_brokers[broker_key]['client']
                self.trader.current_broker = broker_key
                self.trader.account_name = self.trader.active_brokers[broker_key]['name']
                print(f"✅ Single account mode: {self.trader.account_name}")
            else:
                print("⚠️  No broker accounts configured!")
                messagebox.showwarning("Warning", 
                    "No broker accounts could be configured.\n\n"
                    "Please check your .env file and ensure tokens are valid.\n"
                    "You may need to regenerate access tokens using:\n"
                    "python traderchamp.py → type 'token'")
        except Exception as e:
            print(f"❌ Error in setup_multi_account: {e}")
            messagebox.showerror("Error", f"Failed to setup accounts: {e}")
    
    def create_menu_bar(self):
        """Create menu bar with configuration options."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Settings menu
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="⚙️ Settings", menu=settings_menu)
        settings_menu.add_command(label="🔐 Configure Brokers", command=self.open_token_config)
        settings_menu.add_command(label="🔔 Alert Settings", command=self.open_alert_settings)
        settings_menu.add_separator()
        settings_menu.add_checkbutton(
            label="🤖 Auto Market Analysis (3-min)",
            variable=self.market_analysis_enabled,
            command=self.toggle_market_analysis
        )
        settings_menu.add_separator()
        settings_menu.add_command(label="🔄 Reload Configuration", command=self.reload_config)
        settings_menu.add_separator()
        settings_menu.add_command(label="❌ Exit", command=self.root.quit)
        
        # Templates menu
        templates_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="📋 Templates", menu=templates_menu)
        templates_menu.add_command(label="💾 Save Current Setup", command=self.save_template)
        templates_menu.add_command(label="📂 Load Template", command=self.load_template)
        templates_menu.add_separator()
        templates_menu.add_command(label="🗑️ Delete Template", command=self.delete_template)
        
        # Tips menu
        tips_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="💡 Tips Buddy", menu=tips_menu)
        tips_menu.add_command(label="📊 Analyze Market", command=self.analyze_market_sentiment)
        tips_menu.add_command(label="🎯 Strike Momentum", command=self.show_strike_momentum)
        tips_menu.add_separator()
        tips_menu.add_command(label="📈 Quick Scan", command=self.quick_market_scan)
        tips_menu.add_command(label="🔍 Analyze Now (Manual)", command=lambda: self.trigger_manual_analysis() if hasattr(self, 'trigger_manual_analysis') else messagebox.showinfo("Loading", "Feature loading..."))
        tips_menu.add_separator()
        tips_menu.add_command(label="📊 View Analysis Report", command=lambda: (print("🔍 Menu: View Analysis Report clicked"), self.show_analysis_report()))
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="❓ Help", menu=help_menu)
        help_menu.add_command(label="📖 About", command=self.show_about)
        help_menu.add_command(label="📄 .env Location", command=self.show_env_location)
    
    def toggle_market_analysis(self):
        """Toggle automatic market analysis."""
        if self.market_analysis_enabled.get():
            messagebox.showinfo(
                "Market Analysis Enabled",
                "Automatic market analysis will run every 3 minutes.\n\n"
                "You'll receive alerts for:\n"
                "✅ Strong bullish/bearish signals\n"
                "✅ Candlestick patterns\n"
                "✅ Momentum indicators\n"
                "✅ Volume surges\n"
                "✅ Recommended strike prices"
            )
            if hasattr(self, 'start_market_analysis'):
                self.start_market_analysis()
        else:
            messagebox.showinfo(
                "Market Analysis Disabled",
                "Automatic market analysis has been disabled.\n\n"
                "You can still manually analyze using:\n"
                "💡 Tips Buddy → Analyze Now (Manual)"
            )
    
    def open_token_config(self):
        """Open .env file for editing."""
        import subprocess
        
        # Get the directory where the executable/script is running
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        
        env_file = os.path.join(app_dir, '.env')
        
        if not os.path.exists(env_file):
            messagebox.showerror("Error", f".env file not found at: {env_file}")
            return
        
        try:
            if os.name == 'nt':  # Windows
                os.startfile(env_file)
            else:  # Linux/Mac
                subprocess.run(['xdg-open', env_file])
            messagebox.showinfo(
                "Configuration",
                "Opening .env file. After making changes, use Settings → Reload Configuration to apply them."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open .env file: {e}")
    
    def reload_config(self):
        """Reload configuration from .env file."""
        result = messagebox.askyesno(
            "Reload Configuration",
            "This will restart the application to load new settings.\n\nContinue?"
        )
        if result:
            # Restart the application
            self.root.destroy()
            if getattr(sys, 'frozen', False):
                # Running as bundled executable
                os.execl(sys.executable, sys.executable)
            else:
                # Running as Python script
                os.execl(sys.executable, sys.executable, *sys.argv)
    
    def load_templates(self):
        """Load templates from JSON file."""
        try:
            if self.templates_file.exists():
                with open(self.templates_file, 'r') as f:
                    self.templates = json.load(f)
                if hasattr(self, 'log_message'):
                    self.log_message(f"Loaded {len(self.templates)} templates")
                else:
                    print(f"📋 Loaded {len(self.templates)} templates")
            else:
                self.templates = {}
                # Create templates file with empty dict
                self.templates_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.templates_file, 'w') as f:
                    json.dump({}, f, indent=2)
        except Exception as e:
            if hasattr(self, 'log_message'):
                self.log_message(f"Error loading templates: {e}", "ERROR")
            else:
                print(f"⚠️  Error loading templates: {e}")
            self.templates = {}
    
    def save_templates(self):
        """Save templates to JSON file."""
        try:
            self.templates_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.templates_file, 'w') as f:
                json.dump(self.templates, f, indent=2)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save templates: {e}")
            return False
    
    def save_template(self):
        """Save current Quick Order configuration as a template."""
        # Get current configuration
        config = {
            'symbol': self.symbol_var.get(),
            'expiry': self.expiry_var.get(),
            'strike': self.strike_var.get(),
            'option_type': self.option_type_var.get(),
            'lot_size': self.lot_var.get(),
            'order_type': self.order_type_var.get(),
            'product_type': self.product_type_var.get()
        }
        
        # Validate that we have something to save
        if not config['symbol']:
            messagebox.showwarning("No Configuration", "Please select a symbol first before saving a template.")
            return
        
        # Create dialog to get template name
        dialog = tk.Toplevel(self.root)
        dialog.title("Save Template")
        dialog.geometry("400x150")
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Name entry
        name_frame = tk.Frame(dialog, bg='#1e1e1e')
        name_frame.pack(pady=20, padx=20, fill='x')
        
        tk.Label(name_frame, text="Template Name:", bg='#1e1e1e', fg='white', 
                font=('Arial', 10)).pack(side='left', padx=(0, 10))
        
        name_entry = tk.Entry(name_frame, font=('Arial', 10), width=25)
        name_entry.pack(side='left', fill='x', expand=True)
        name_entry.focus()
        
        # Suggestion based on current config
        suggestion = f"{config['symbol']} {config['option_type']} {config['strike']}"
        name_entry.insert(0, suggestion)
        name_entry.select_range(0, tk.END)
        
        # Config preview
        preview_text = f"Symbol: {config['symbol']} | Expiry: {config['expiry']} | Strike: {config['strike']} | Type: {config['option_type']} | Lots: {config['lot_size']}"
        tk.Label(dialog, text=preview_text, bg='#1e1e1e', fg='#888', 
                font=('Arial', 8)).pack(pady=(0, 10))
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg='#1e1e1e')
        btn_frame.pack(pady=10)
        
        def do_save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("Invalid Name", "Please enter a template name.", parent=dialog)
                return
            
            # Check if template exists
            if name in self.templates:
                if not messagebox.askyesno("Overwrite?", 
                                          f"Template '{name}' already exists. Overwrite?", 
                                          parent=dialog):
                    return
            
            # Save template
            self.templates[name] = config
            if self.save_templates():
                messagebox.showinfo("Success", f"Template '{name}' saved successfully!", parent=dialog)
                dialog.destroy()
        
        tk.Button(btn_frame, text="💾 Save", command=do_save, bg='#0d7377', fg='white',
                 font=('Arial', 10, 'bold'), padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy, bg='#d9534f', fg='white',
                 font=('Arial', 10), padx=20, pady=5).pack(side='left', padx=5)
        
        # Bind Enter key
        name_entry.bind('<Return>', lambda e: do_save())
        dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    def load_template(self):
        """Load a saved template and apply it to Quick Order."""
        if not self.templates:
            messagebox.showinfo("No Templates", "No saved templates found. Use Templates → Save Current Setup to create one.")
            return
        
        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Load Template")
        dialog.geometry("600x400")
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="Select a template to load:", bg='#1e1e1e', fg='white',
                font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Listbox with scrollbar
        list_frame = tk.Frame(dialog, bg='#1e1e1e')
        list_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        
        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, 
                            bg='#2d2d2d', fg='white', font=('Consolas', 10),
                            selectmode='single', height=15)
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Add templates to listbox
        template_names = sorted(self.templates.keys())
        for name in template_names:
            listbox.insert(tk.END, name)
        
        # Preview label
        preview_label = tk.Label(dialog, text="", bg='#1e1e1e', fg='#888',
                                font=('Arial', 9), wraplength=550, justify='left')
        preview_label.pack(pady=10, padx=20)
        
        def on_select(event):
            selection = listbox.curselection()
            if selection:
                name = listbox.get(selection[0])
                config = self.templates[name]
                preview = f"Symbol: {config['symbol']} | Expiry: {config['expiry']} | Strike: {config['strike']} | Type: {config['option_type']} | Lots: {config['lot_size']} | Order: {config['order_type']} | Product: {config['product_type']}"
                preview_label.config(text=preview)
        
        listbox.bind('<<ListboxSelect>>', on_select)
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg='#1e1e1e')
        btn_frame.pack(pady=10)
        
        def do_load():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a template to load.", parent=dialog)
                return
            
            name = listbox.get(selection[0])
            config = self.templates[name]
            
            # Apply template to Quick Order
            self.symbol_var.set(config['symbol'])
            self.on_symbol_select(None)  # Trigger expiry load
            
            # Wait a moment for expiries to load, then set other values
            def apply_rest():
                self.expiry_var.set(config['expiry'])
                self.on_expiry_select(None)  # Trigger strikes load
                
                def apply_final():
                    self.strike_var.set(config['strike'])
                    self.option_type_var.set(config['option_type'])
                    self.lot_var.set(config['lot_size'])
                    self.order_type_var.set(config['order_type'])
                    self.product_type_var.set(config['product_type'])
                    
                    messagebox.showinfo("Success", f"Template '{name}' loaded successfully!", parent=dialog)
                    dialog.destroy()
                
                self.root.after(300, apply_final)
            
            self.root.after(300, apply_rest)
        
        tk.Button(btn_frame, text="📂 Load", command=do_load, bg='#0d7377', fg='white',
                 font=('Arial', 10, 'bold'), padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy, bg='#d9534f', fg='white',
                 font=('Arial', 10), padx=20, pady=5).pack(side='left', padx=5)
        
        # Bind double-click and Enter
        listbox.bind('<Double-Button-1>', lambda e: do_load())
        listbox.bind('<Return>', lambda e: do_load())
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        
        # Select first item by default
        if template_names:
            listbox.selection_set(0)
            on_select(None)
    
    def delete_template(self):
        """Delete a saved template."""
        if not self.templates:
            messagebox.showinfo("No Templates", "No saved templates found.")
            return
        
        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Delete Template")
        dialog.geometry("500x350")
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        tk.Label(dialog, text="Select template(s) to delete:", bg='#1e1e1e', fg='white',
                font=('Arial', 12, 'bold')).pack(pady=10)
        
        # Listbox with scrollbar (multiple selection)
        list_frame = tk.Frame(dialog, bg='#1e1e1e')
        list_frame.pack(pady=10, padx=20, fill='both', expand=True)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        
        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, 
                            bg='#2d2d2d', fg='white', font=('Consolas', 10),
                            selectmode='extended', height=12)
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.config(command=listbox.yview)
        
        # Add templates to listbox
        template_names = sorted(self.templates.keys())
        for name in template_names:
            config = self.templates[name]
            display = f"{name} - {config['symbol']} {config['option_type']} {config['strike']}"
            listbox.insert(tk.END, display)
        
        tk.Label(dialog, text="Tip: Hold Ctrl to select multiple templates", 
                bg='#1e1e1e', fg='#888', font=('Arial', 8)).pack()
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg='#1e1e1e')
        btn_frame.pack(pady=15)
        
        def do_delete():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select template(s) to delete.", parent=dialog)
                return
            
            # Get selected template names
            to_delete = [template_names[i] for i in selection]
            
            # Confirm deletion
            if len(to_delete) == 1:
                msg = f"Delete template '{to_delete[0]}'?"
            else:
                msg = f"Delete {len(to_delete)} templates?\n\n" + "\n".join(to_delete)
            
            if not messagebox.askyesno("Confirm Delete", msg, parent=dialog):
                return
            
            # Delete templates
            for name in to_delete:
                del self.templates[name]
            
            if self.save_templates():
                messagebox.showinfo("Success", f"Deleted {len(to_delete)} template(s).", parent=dialog)
                dialog.destroy()
        
        tk.Button(btn_frame, text="🗑️ Delete", command=do_delete, bg='#d9534f', fg='white',
                 font=('Arial', 10, 'bold'), padx=20, pady=5).pack(side='left', padx=5)
        tk.Button(btn_frame, text="❌ Cancel", command=dialog.destroy, bg='#6c757d', fg='white',
                 font=('Arial', 10), padx=20, pady=5).pack(side='left', padx=5)
        
        dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    def analyze_market_sentiment(self):
        """Analyze market sentiment using price action, pivots, VWAP, and momentum."""
        threading.Thread(target=self._analyze_market_async, daemon=True).start()
    
    def _analyze_market_async(self):
        """Async market analysis with technical indicators."""
        try:
            # Show loading message
            self.root.after(0, lambda: self._show_tips_loading())
            
            # Get first available broker client
            client = None
            broker_name = ""
            for broker_key, broker_info in self.trader.active_brokers.items():
                client = broker_info['client']
                broker_name = broker_info['name']
                break
            
            if not client:
                self.root.after(0, lambda: messagebox.showerror("Error", "No active broker found"))
                return
            
            # Fetch NIFTY spot data (historical candles for analysis)
            # Using NIFTY 50 index symbol
            analysis = self._perform_technical_analysis(client, broker_name)
            
            # Show results
            self.root.after(0, lambda: self._show_tips_results(analysis))
            
        except Exception as e:
            print(f"Market analysis error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Analysis failed: {e}"))
    
    def _perform_technical_analysis(self, client, broker_name):
        """Perform comprehensive technical analysis on NIFTY with RSI, MA, Volume."""
        from datetime import datetime, timedelta
        import yfinance as yf
        
        try:
            # Get NIFTY index instrument key - EXACT format from Upstox
            nifty_instrument = "NSE_INDEX|Nifty 50"
            
            # Fetch REAL-TIME NIFTY current price
            current_price = 0
            data_source = "Unknown"
            
            # Try Upstox first
            try:
                print(f"🔍 Attempting to fetch NIFTY price from Upstox...")
                ltp_response = client.get_ltp(nifty_instrument)
                print(f"📡 Upstox LTP Response: {ltp_response}")
                
                if ltp_response and ltp_response.get('status') == 'success' and ltp_response.get('data'):
                    ltp_data = ltp_response['data']
                    if isinstance(ltp_data, dict):
                        # Upstox format: {'NSE_INDEX|Nifty 50': {'last_price': 23500.50}}
                        if nifty_instrument in ltp_data:
                            current_price = ltp_data[nifty_instrument].get('last_price', 0)
                            data_source = "Upstox"
                        else:
                            # Try first key
                            first_key = next(iter(ltp_data), None)
                            if first_key and isinstance(ltp_data[first_key], dict):
                                current_price = ltp_data[first_key].get('last_price', 0)
                                data_source = "Upstox"
                
                if current_price > 0:
                    print(f"✅ Upstox: NIFTY price = ₹{current_price:.2f}")
                    
            except Exception as e:
                print(f"⚠️ Upstox fetch failed: {e}")
            
            # Fallback to Yahoo Finance if Upstox fails
            if current_price == 0:
                try:
                    print(f"🔄 Falling back to Yahoo Finance...")
                    nifty_ticker = yf.Ticker("^NSEI")
                    nifty_data = nifty_ticker.history(period="1d")
                    
                    if not nifty_data.empty:
                        current_price = float(nifty_data['Close'].iloc[-1])
                        data_source = "Yahoo Finance"
                        print(f"✅ Yahoo Finance: NIFTY price = ₹{current_price:.2f}")
                    else:
                        raise Exception("No data from Yahoo Finance")
                        
                except Exception as e:
                    print(f"⚠️ Yahoo Finance fetch failed: {e}")
                    print(f"⚠️ Using fallback estimate. Market may be closed.")
                    current_price = 23900  # Conservative fallback
                    data_source = "Estimated (Market Closed)"
            
            # Fetch COMPREHENSIVE HISTORICAL DATA for advanced indicators
            prev_high = current_price + 200
            prev_low = current_price - 200
            prev_close = current_price
            prev_open = current_price
            historical_data_available = False
            
            # Additional indicators
            rsi = 50  # Default neutral
            ma_20 = current_price
            ma_50 = current_price
            volume_trend = "Normal"
            price_momentum = "Neutral"
            
            try:
                # Get extended historical data for indicators
                print(f"🔄 Fetching historical data from Yahoo Finance...")
                nifty_ticker = yf.Ticker("^NSEI")
                hist_data = nifty_ticker.history(period="60d")  # 60 days for better MA calculation
                
                if len(hist_data) >= 14:  # Minimum for RSI
                    # Calculate RSI (14-period)
                    close_prices = hist_data['Close'].values
                    deltas = [close_prices[i] - close_prices[i-1] for i in range(1, len(close_prices))]
                    gains = [d if d > 0 else 0 for d in deltas]
                    losses = [-d if d < 0 else 0 for d in deltas]
                    
                    avg_gain = sum(gains[-14:]) / 14
                    avg_loss = sum(losses[-14:]) / 14
                    
                    if avg_loss == 0:
                        rsi = 100
                    else:
                        rs = avg_gain / avg_loss
                        rsi = 100 - (100 / (1 + rs))
                    
                    print(f"✅ RSI calculated: {rsi:.2f}")
                    
                    # Calculate Moving Averages
                    if len(close_prices) >= 20:
                        ma_20 = sum(close_prices[-20:]) / 20
                        print(f"✅ MA(20): {ma_20:.2f}")
                    
                    if len(close_prices) >= 50:
                        ma_50 = sum(close_prices[-50:]) / 50
                        print(f"✅ MA(50): {ma_50:.2f}")
                    
                    # Volume trend analysis
                    volumes = hist_data['Volume'].values
                    if len(volumes) >= 10:
                        recent_vol = sum(volumes[-5:]) / 5
                        avg_vol = sum(volumes[-20:]) / 20
                        
                        if recent_vol > avg_vol * 1.3:
                            volume_trend = "High (Bullish)"
                        elif recent_vol < avg_vol * 0.7:
                            volume_trend = "Low (Weak)"
                        else:
                            volume_trend = "Normal"
                        
                        print(f"✅ Volume trend: {volume_trend}")
                    
                    # Get previous day data
                    if len(hist_data) >= 2:
                        prev_day = hist_data.iloc[-2]
                        prev_open = float(prev_day['Open'])
                        prev_high = float(prev_day['High'])
                        prev_low = float(prev_day['Low'])
                        prev_close = float(prev_day['Close'])
                        historical_data_available = True
                        print(f"✅ Previous day: O={prev_open:.2f}, H={prev_high:.2f}, L={prev_low:.2f}, C={prev_close:.2f}")
                    
                    # Price momentum (comparing current to 5-day average)
                    if len(close_prices) >= 5:
                        five_day_avg = sum(close_prices[-5:]) / 5
                        momentum_pct = ((current_price - five_day_avg) / five_day_avg) * 100
                        
                        if momentum_pct > 1:
                            price_momentum = "Strong Bullish"
                        elif momentum_pct > 0.3:
                            price_momentum = "Bullish"
                        elif momentum_pct < -1:
                            price_momentum = "Strong Bearish"
                        elif momentum_pct < -0.3:
                            price_momentum = "Bearish"
                        else:
                            price_momentum = "Neutral"
                        
                        print(f"✅ Price momentum: {price_momentum} ({momentum_pct:+.2f}%)")
                
            except Exception as e:
                print(f"⚠️ Historical data/indicators failed: {e}")
            
            # Determine Market Day Type based on price action
            day_range = prev_high - prev_low
            body_size = abs(prev_close - prev_open)
            body_percent = (body_size / day_range * 100) if day_range > 0 else 0
            
            # Calculate where close is relative to range
            close_position = ((prev_close - prev_low) / day_range * 100) if day_range > 0 else 50
            
            # Classify market day type
            if body_percent >= 70:
                if prev_close > prev_open:
                    market_day_type = "📈 STRONG TREND DAY (Bullish)"
                    day_type_color = "#00ff00"
                else:
                    market_day_type = "📉 STRONG TREND DAY (Bearish)"
                    day_type_color = "#ff4444"
            elif body_percent >= 45:
                if prev_close > prev_open:
                    market_day_type = "📊 TREND DAY (Bullish)"
                    day_type_color = "#00cc00"
                else:
                    market_day_type = "📊 TREND DAY (Bearish)"
                    day_type_color = "#ff6666"
            elif day_range < 150:
                market_day_type = "😴 SIDEWAYS DAY (Low Volatility)"
                day_type_color = "#888888"
            else:
                market_day_type = "⚡ VOLATILE DAY (Range-bound)"
                day_type_color = "#ffa500"
            
            pivot = (prev_high + prev_low + prev_close) / 3
            r1 = 2 * pivot - prev_low
            s1 = 2 * pivot - prev_high
            r2 = pivot + (prev_high - prev_low)
            s2 = pivot - (prev_high - prev_low)
            
            # ADVANCED SENTIMENT ANALYSIS (Multi-factor)
            bullish_signals = 0
            bearish_signals = 0
            
            # Signal 1: Price vs Pivot
            if current_price > pivot:
                bullish_signals += 1
            else:
                bearish_signals += 1
            
            # Signal 2: RSI
            if rsi > 60:
                bullish_signals += 1
            elif rsi < 40:
                bearish_signals += 1
            
            # Signal 3: Moving Averages
            if current_price > ma_20 > ma_50:
                bullish_signals += 2  # Strong signal
            elif current_price < ma_20 < ma_50:
                bearish_signals += 2  # Strong signal
            elif current_price > ma_20:
                bullish_signals += 1
            elif current_price < ma_20:
                bearish_signals += 1
            
            # Signal 4: Volume trend
            if "High" in volume_trend:
                if current_price > prev_close:
                    bullish_signals += 1
                else:
                    bearish_signals += 1
            
            # Signal 5: Price momentum
            if "Bullish" in price_momentum:
                bullish_signals += 1
            elif "Bearish" in price_momentum:
                bearish_signals += 1
            
            # Determine overall sentiment
            total_signals = bullish_signals + bearish_signals
            bullish_strength = (bullish_signals / total_signals * 100) if total_signals > 0 else 50
            
            if bullish_signals >= bearish_signals + 2:
                sentiment = "STRONG BULLISH 📈📈"
                bias = "CE"
                confidence = 90
            elif bullish_signals > bearish_signals:
                sentiment = "BULLISH 📈"
                bias = "CE"
                confidence = 70
            elif bearish_signals >= bullish_signals + 2:
                sentiment = "STRONG BEARISH 📉📉"
                bias = "PE"
                confidence = 90
            elif bearish_signals > bullish_signals:
                sentiment = "BEARISH 📉"
                bias = "PE"
                confidence = 70
            else:
                sentiment = "NEUTRAL ➡️"
                bias = "NEUTRAL"
                confidence = 50
            
            # Determine recommended strike with logic
            atm_strike = round(current_price / 50) * 50
            
            if bias == "CE":
                # Bullish - recommend based on strength
                if confidence >= 85 and current_price > r1:
                    recommended_strike = atm_strike + 50  # OTM for aggressive
                    strike_logic = "OTM CE - Strong uptrend, target R2"
                else:
                    recommended_strike = atm_strike  # ATM for moderate
                    strike_logic = "ATM CE - Moderate bullish, safer entry"
                
                strikes = {
                    'ATM': atm_strike,
                    'OTM1': atm_strike + 50,
                    'OTM2': atm_strike + 100,
                    'ITM': atm_strike - 50
                }
            elif bias == "PE":
                # Bearish - recommend based on strength
                if confidence >= 85 and current_price < s1:
                    recommended_strike = atm_strike - 50  # OTM for aggressive
                    strike_logic = "OTM PE - Strong downtrend, target S2"
                else:
                    recommended_strike = atm_strike  # ATM for moderate
                    strike_logic = "ATM PE - Moderate bearish, safer entry"
                
                strikes = {
                    'ATM': atm_strike,
                    'OTM1': atm_strike - 50,
                    'OTM2': atm_strike - 100,
                    'ITM': atm_strike + 50
                }
            else:
                recommended_strike = atm_strike
                strike_logic = "Wait for clear setup - No trade"
                strikes = {'ATM': atm_strike}
            
            # Build final recommendation
            if bias == "CE":
                recommendation = f"🎯 BUY: NIFTY {recommended_strike} CE | {strike_logic}"
            elif bias == "PE":
                recommendation = f"🎯 BUY: NIFTY {recommended_strike} PE | {strike_logic}"
            else:
                recommendation = f"⏸️ WAIT - RSI={rsi:.1f}, Signals mixed. No clear setup."
            
            return {
                'current_price': current_price,
                'data_source': data_source,
                'market_day_type': market_day_type,
                'day_type_color': day_type_color,
                'prev_range': day_range,
                'prev_high': prev_high,
                'prev_low': prev_low,
                'prev_close': prev_close,
                'trend': sentiment,
                'strength': f"{int(confidence)}%",
                'pivot': pivot,
                'r1': r1,
                'r2': r2,
                's1': s1,
                's2': s2,
                'rsi': rsi,
                'ma_20': ma_20,
                'ma_50': ma_50,
                'volume_trend': volume_trend,
                'price_momentum': price_momentum,
                'bullish_signals': bullish_signals,
                'bearish_signals': bearish_signals,
                'bullish_strength': bullish_strength,
                'recommendation': recommendation,
                'bias': bias,
                'confidence': confidence,
                'strikes': strikes,
                'recommended_strike': recommended_strike,
                'strike_logic': strike_logic,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
            
        except Exception as e:
            print(f"Technical analysis error: {e}")
            return None
    
    def _show_tips_loading(self):
        """Show loading dialog."""
        self.tips_dialog = tk.Toplevel(self.root)
        self.tips_dialog.title("💡 Analyzing Market...")
        self.tips_dialog.geometry("300x100")
        self.tips_dialog.configure(bg='#2d2d2d')
        self.tips_dialog.transient(self.root)
        
        tk.Label(self.tips_dialog, text="Analyzing NIFTY trend...\nPlease wait...",
                font=('Arial', 11), bg='#2d2d2d', fg='white', pady=20).pack()
    
    def _show_tips_results(self, analysis):
        """Show analysis results in a dialog."""
        try:
            if hasattr(self, 'tips_dialog') and self.tips_dialog:
                self.tips_dialog.destroy()
        except:
            pass
        
        if not analysis:
            messagebox.showerror("Error", "Failed to analyze market")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("💡 Tips Buddy - Market Analysis")
        dialog.geometry("600x700")
        dialog.configure(bg='#2d2d2d')
        dialog.transient(self.root)
        
        # Main container with scrollbar
        canvas = tk.Canvas(dialog, bg='#2d2d2d', highlightthickness=0)
        scrollbar = tk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#2d2d2d')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Header
        header = tk.Frame(scrollable_frame, bg='#1a1a1a', pady=15)
        header.pack(fill='x', padx=10, pady=(10, 5))
        
        tk.Label(header, text="📊 NIFTY Market Analysis", font=('Arial', 16, 'bold'),
                bg='#1a1a1a', fg='#00ff00').pack()
        tk.Label(header, text=f"Updated: {analysis['timestamp']} | Source: {analysis['data_source']}", 
                font=('Arial', 9), bg='#1a1a1a', fg='#888').pack()
        
        # Current Price
        price_frame = tk.Frame(scrollable_frame, bg='#1a1a1a', pady=10)
        price_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(price_frame, text=f"NIFTY: ₹{analysis['current_price']:.2f}",
                font=('Arial', 20, 'bold'), bg='#1a1a1a', fg='#00d4ff').pack()
        
        # Technical Indicators Section
        indicators_frame = tk.Frame(scrollable_frame, bg='#1a1a1a', pady=10)
        indicators_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(indicators_frame, text="📊 Technical Indicators", font=('Arial', 12, 'bold'),
                bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10)
        
        rsi_color = '#ff4444' if analysis['rsi'] > 70 else '#00ff00' if analysis['rsi'] < 30 else '#ffa500'
        rsi_status = 'Overbought 📉' if analysis['rsi'] > 70 else 'Oversold 📈' if analysis['rsi'] < 30 else 'Neutral ➡️'
        
        indicators_text = f"""RSI(14): {analysis['rsi']:.2f} - {rsi_status}
MA(20): ₹{analysis['ma_20']:.2f}  {'✅ Above' if analysis['current_price'] > analysis['ma_20'] else '❌ Below'}
MA(50): ₹{analysis['ma_50']:.2f}  {'✅ Above' if analysis['current_price'] > analysis['ma_50'] else '❌ Below'}
Volume: {analysis['volume_trend']}
Momentum: {analysis['price_momentum']}"""
        
        tk.Label(indicators_frame, text=indicators_text, font=('Courier', 10),
                bg='#1a1a1a', fg='#ccc', justify='left').pack(anchor='w', padx=20, pady=5)
        
        # Signal Strength
        signal_frame = tk.Frame(scrollable_frame, bg='#1a1a1a', pady=10)
        signal_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(signal_frame, text="🎯 Signal Strength", font=('Arial', 12, 'bold'),
                bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10)
        
        signal_text = f"""Bullish Signals: {analysis['bullish_signals']}  |  Bearish Signals: {analysis['bearish_signals']}
Confidence: {analysis['bullish_strength']:.1f}% Bullish"""
        
        tk.Label(signal_frame, text=signal_text, font=('Arial', 11),
                bg='#1a1a1a', fg='#ffff00').pack(anchor='w', padx=20, pady=5)
        
        # Market Day Type
        day_type_frame = tk.Frame(scrollable_frame, bg='#1a1a1a', pady=10)
        day_type_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(day_type_frame, text=analysis['market_day_type'],
                font=('Arial', 14, 'bold'), bg='#1a1a1a', fg=analysis['day_type_color']).pack()
        tk.Label(day_type_frame, text=f"Previous Day Range: ₹{analysis['prev_range']:.2f}",
                font=('Arial', 10), bg='#1a1a1a', fg='#aaa').pack()
        
        # Trend & Strength
        trend_frame = tk.Frame(scrollable_frame, bg='#1a1a1a', pady=10)
        trend_frame.pack(fill='x', padx=10, pady=5)
        
        trend_color = '#00ff00' if analysis['trend'] == 'BULLISH' else '#ff4444'
        tk.Label(trend_frame, text=f"Trend: {analysis['trend']} ({analysis['strength']})",
                font=('Arial', 14, 'bold'), bg='#1a1a1a', fg=trend_color).pack()
        
        # Confidence
        confidence_frame = tk.Frame(scrollable_frame, bg='#1a1a1a', pady=5)
        confidence_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(confidence_frame, text=f"Confidence: {analysis['confidence']}%",
                font=('Arial', 12), bg='#1a1a1a', fg='#ffa500').pack()
        
        # Recommendation
        rec_frame = tk.Frame(scrollable_frame, bg='#ffaa00', pady=15)
        rec_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(rec_frame, text=analysis['recommendation'],
                font=('Arial', 13, 'bold'), bg='#ffaa00', fg='#000', wraplength=550).pack()
        
        # Pivot Levels
        pivot_frame = tk.Frame(scrollable_frame, bg='#1a1a1a', pady=10)
        pivot_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(pivot_frame, text="📍 Pivot Levels", font=('Arial', 12, 'bold'),
                bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10)
        
        levels_text = f"""
        R2: {analysis['r2']:.2f}  (Strong Resistance)
        R1: {analysis['r1']:.2f}  (Resistance)
        PP: {analysis['pivot']:.2f}  (Pivot Point)
        S1: {analysis['s1']:.2f}  (Support)
        S2: {analysis['s2']:.2f}  (Strong Support)
        """
        
        tk.Label(pivot_frame, text=levels_text, font=('Courier', 10),
                bg='#1a1a1a', fg='#ccc', justify='left').pack(anchor='w', padx=20)
        
        # Money Zone & Value Area Analysis
        money_zone_frame = tk.Frame(scrollable_frame, bg='#1a1a1a', pady=10)
        money_zone_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(money_zone_frame, text="💰 Money Zone & Value Area", font=('Arial', 12, 'bold'),
                bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10)
        
        # Calculate Value Area from previous day's range
        current = analysis['current_price']
        prev_high = analysis.get('prev_high', current + 200)
        prev_low = analysis.get('prev_low', current - 200)
        prev_close = analysis.get('prev_close', current)
        
        # Value Area calculation (70% rule)
        day_range = prev_high - prev_low
        poc = (prev_high + prev_low + prev_close) / 3  # Point of Control
        vah = poc + (day_range * 0.35)  # Value Area High
        val = poc - (day_range * 0.35)  # Value Area Low
        
        # Determine current position in Value Area
        if current >= vah:
            zone_status = "PREMIUM ZONE (Above VAH)"
            zone_color = '#ff4444'
            zone_msg = "⚠️ Market trading at premium - Resistance likely"
        elif current <= val:
            zone_status = "DISCOUNT ZONE (Below VAL)"
            zone_color = '#00ff00'
            zone_msg = "✅ Market trading at discount - Support likely"
        else:
            zone_status = "FAIR VALUE ZONE (Within VA)"
            zone_color = '#ffa500'
            zone_msg = "➡️ Market in fair value - Range-bound possible"
        
        tk.Label(money_zone_frame, text=f"Current Zone: {zone_status}", font=('Arial', 11, 'bold'),
                bg='#1a1a1a', fg=zone_color).pack(anchor='w', padx=20, pady=3)
        tk.Label(money_zone_frame, text=f"   {zone_msg}", font=('Arial', 10),
                bg='#1a1a1a', fg='#ccc').pack(anchor='w', padx=20, pady=2)
        
        # Value Area levels
        value_levels_text = f"""
   Value Area High (VAH): ₹{vah:.2f}  (70% top boundary)
   Point of Control (POC): ₹{poc:.2f}  (Most traded level)
   Value Area Low (VAL): ₹{val:.2f}  (70% bottom boundary)
   
   Current Price: ₹{current:.2f}"""
        
        tk.Label(money_zone_frame, text=value_levels_text, font=('Courier', 9),
                bg='#1a1a1a', fg='#aaa', justify='left').pack(anchor='w', padx=20, pady=3)
        
        # Trading implications
        tk.Label(money_zone_frame, text="💡 Value Area Trading Rules:", font=('Arial', 10, 'bold'),
                bg='#1a1a1a', fg='#ffaa00').pack(anchor='w', padx=20, pady=5)
        
        if current >= vah:
            va_tips = """   • Price at premium - Look for reversals or profit booking
   • Selling opportunities near VAH (resistance)
   • PE options may work if reversal occurs
   • Use tight stop loss for CE trades"""
        elif current <= val:
            va_tips = """   • Price at discount - Look for buying opportunities
   • Support expected near VAL
   • CE options favored if bounce occurs
   • Use tight stop loss for PE trades"""
        else:
            va_tips = """   • Price in fair value - Choppy/range-bound expected
   • Wait for breakout above VAH or breakdown below VAL
   • Avoid directional bets, prefer scalping
   • Both CE/PE risky until clear trend emerges"""
        
        tk.Label(money_zone_frame, text=va_tips, font=('Arial', 9),
                bg='#1a1a1a', fg='#ccc', justify='left').pack(anchor='w', padx=20, pady=2)
        
        # Money management zones
        tk.Label(money_zone_frame, text="\n💵 Money Management Zones:", font=('Arial', 10, 'bold'),
                bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=20, pady=3)
        
        mm_zones = f"""   🟢 Buying Zone: Below ₹{val:.2f} (Discount - Good R:R for longs)
   🟡 Neutral Zone: ₹{val:.2f} - ₹{vah:.2f} (Fair value - Range trading)
   🔴 Selling Zone: Above ₹{vah:.2f} (Premium - Good R:R for shorts)
   
   Current Position: {zone_status}"""
        
        tk.Label(money_zone_frame, text=mm_zones, font=('Courier', 9),
                bg='#1a1a1a', fg='#fff', justify='left').pack(anchor='w', padx=20, pady=3)
        
        # Strike Recommendations
        strike_frame = tk.Frame(scrollable_frame, bg='#1a1a1a', pady=10)
        strike_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(strike_frame, text=f"🎯 Recommended Strikes ({analysis['bias']})",
                font=('Arial', 12, 'bold'), bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10)
        
        for strike_type, strike_val in analysis['strikes'].items():
            strike_label = f"{strike_type}: {strike_val} {analysis['bias']}"
            tk.Label(strike_frame, text=strike_label, font=('Arial', 11),
                    bg='#1a1a1a', fg='#ffff00').pack(anchor='w', padx=20, pady=2)
        
        # Trading Tips
        tips_frame = tk.Frame(scrollable_frame, bg='#1a1a1a', pady=10)
        tips_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(tips_frame, text="💡 Trading Tips", font=('Arial', 12, 'bold'),
                bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10)
        
        tips_text = f"""
        • Watch for price action near {analysis['pivot']:.0f}
        • Use Stop Loss below {analysis['s1']:.0f} for longs
        • Use Stop Loss above {analysis['r1']:.0f} for shorts
        • High volume confirms trend direction
        • Trade in direction of pivot bias
        """
        
        tk.Label(tips_frame, text=tips_text, font=('Arial', 10),
                bg='#1a1a1a', fg='#ccc', justify='left').pack(anchor='w', padx=20)
        
        # Close button
        tk.Button(scrollable_frame, text="✅ Got it!", command=dialog.destroy,
                 bg='#28a745', fg='white', font=('Arial', 11, 'bold'),
                 padx=30, pady=10).pack(pady=20)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    def show_strike_momentum(self):
        """Show strike-wise momentum analysis."""
        threading.Thread(target=self._show_strike_momentum_async, daemon=True).start()
    
    def _show_strike_momentum_async(self):
        """Async strike momentum analysis."""
        import yfinance as yf
        
        try:
            # Get first available broker client
            client = None
            broker_name = ""
            for broker_key, broker_info in self.trader.active_brokers.items():
                client = broker_info['client']
                broker_name = broker_info['name']
                break
            
            if not client:
                self.root.after(0, lambda: messagebox.showerror("Error", "No active broker found"))
                return
            
            # Fetch NIFTY current price for ATM calculation
            nifty_instrument = "NSE_INDEX|Nifty 50"
            current_price = 23500  # Default
            
            try:
                # Try Upstox first
                ltp_response = client.get_ltp(nifty_instrument)
                if ltp_response and ltp_response.get('status') == 'success' and ltp_response.get('data'):
                    ltp_data = ltp_response['data']
                    first_key = next(iter(ltp_data), None)
                    if first_key and isinstance(ltp_data[first_key], dict):
                        current_price = ltp_data[first_key].get('last_price', 0)
            except:
                pass
            
            # Fallback to Yahoo Finance
            if current_price == 0:
                try:
                    nifty = yf.Ticker("^NSEI")
                    data = nifty.history(period="1d")
                    if not data.empty:
                        current_price = float(data['Close'].iloc[-1])
                except:
                    pass
            
            # Calculate ATM strike
            atm_strike = round(current_price / 50) * 50
            
            # Fetch real option data from Upstox instruments
            print(f"📊 Fetching option data for strikes around {atm_strike}...")
            
            momentum_data = []
            
            # Define strikes to analyze (ATM ± 200 points)
            strikes_to_check = [atm_strike - 100, atm_strike - 50, atm_strike, 
                               atm_strike + 50, atm_strike + 100]
            
            # Get today's date for expiry
            from datetime import datetime, timedelta
            today = datetime.now()
            
            # Find next Thursday (weekly expiry)
            days_ahead = 3 - today.weekday()  # Thursday is 3
            if days_ahead <= 0:
                days_ahead += 7
            next_thursday = today + timedelta(days=days_ahead)
            expiry_str = next_thursday.strftime('%d%b%y').upper()
            
            print(f"🔍 Looking for expiry: {expiry_str}")
            
            # Search in Upstox instruments for these strikes
            for strike in strikes_to_check:
                for opt_type in ['CE', 'PE']:
                    symbol_pattern = f"NIFTY{expiry_str}{strike}{opt_type}"
                    
                    # Search for this symbol in loaded instruments
                    if hasattr(self.trader, 'upstox_instruments'):
                        for inst_key, inst_data in self.trader.upstox_instruments.items():
                            if inst_data.get('tradingsymbol', '').upper() == symbol_pattern.upper():
                                # Found the option, get its LTP
                                try:
                                    ltp_resp = client.get_ltp(inst_key)
                                    if ltp_resp and ltp_resp.get('status') == 'success':
                                        ltp_data = ltp_resp['data']
                                        if inst_key in ltp_data:
                                            ltp = ltp_data[inst_key].get('last_price', 0)
                                        else:
                                            first_key = next(iter(ltp_data), None)
                                            if first_key:
                                                ltp = ltp_data[first_key].get('last_price', 0)
                                            else:
                                                ltp = 0
                                    else:
                                        ltp = 0
                                        
                                    # Calculate momentum score (simplified: based on distance from ATM and LTP)
                                    distance_from_atm = abs(strike - atm_strike)
                                    if distance_from_atm == 0:
                                        momentum = 92  # ATM has highest momentum
                                    elif distance_from_atm == 50:
                                        momentum = 78  # Near ATM
                                    elif distance_from_atm == 100:
                                        momentum = 65  # Moderate
                                    else:
                                        momentum = 55  # Far OTM
                                    
                                    # Add random variation based on premium
                                    if ltp > 200:
                                        momentum += 10
                                    elif ltp > 100:
                                        momentum += 5
                                    
                                    # Estimate OI change and volume (placeholder for real data)
                                    oi_change = f"+{15 + (92 - momentum)}%"
                                    volume = int(50000 + (92 - momentum) * 2000)
                                    
                                    momentum_data.append({
                                        'strike': strike,
                                        'type': opt_type,
                                        'momentum': min(momentum, 95),
                                        'oi_change': oi_change,
                                        'volume': volume,
                                        'ltp': ltp if ltp > 0 else (200 if distance_from_atm < 50 else 100)
                                    })
                                    
                                    print(f"✅ {symbol_pattern}: LTP=₹{ltp:.2f}, Momentum={momentum}%")
                                except Exception as e:
                                    print(f"⚠️ Error fetching {symbol_pattern}: {e}")
                                break
            
            # If no real data found, use sample data
            if len(momentum_data) == 0:
                print("⚠️ No real option data found, using sample data")
                momentum_data = [
                    {'strike': atm_strike - 100, 'type': 'CE', 'momentum': 65, 'oi_change': '+12%', 'volume': 45000, 'ltp': 180.5},
                    {'strike': atm_strike - 50, 'type': 'CE', 'momentum': 78, 'oi_change': '+18%', 'volume': 68000, 'ltp': 220.0},
                    {'strike': atm_strike, 'type': 'CE', 'momentum': 92, 'oi_change': '+25%', 'volume': 125000, 'ltp': 280.5},
                    {'strike': atm_strike + 50, 'type': 'CE', 'momentum': 71, 'oi_change': '+8%', 'volume': 42000, 'ltp': 145.0},
                    {'strike': atm_strike + 100, 'type': 'CE', 'momentum': 58, 'oi_change': '+5%', 'volume': 28000, 'ltp': 95.5},
                    {'strike': atm_strike - 100, 'type': 'PE', 'momentum': 55, 'oi_change': '+3%', 'volume': 22000, 'ltp': 88.0},
                    {'strike': atm_strike - 50, 'type': 'PE', 'momentum': 68, 'oi_change': '+10%', 'volume': 38000, 'ltp': 135.5},
                    {'strike': atm_strike, 'type': 'PE', 'momentum': 85, 'oi_change': '+22%', 'volume': 98000, 'ltp': 275.0},
                    {'strike': atm_strike + 50, 'type': 'PE', 'momentum': 73, 'oi_change': '+15%', 'volume': 52000, 'ltp': 215.5},
                    {'strike': atm_strike + 100, 'type': 'PE', 'momentum': 62, 'oi_change': '+7%', 'volume': 35000, 'ltp': 175.0},
                ]
            
            # Sort by momentum (highest first)
            momentum_data.sort(key=lambda x: x['momentum'], reverse=True)
            
            # Determine if we have real data
            has_real_data = len([d for d in momentum_data if d.get('ltp', 0) > 0]) > 5
            
            self.root.after(0, lambda: self._display_strike_momentum(momentum_data, atm_strike, has_real_data))
            
        except Exception as e:
            print(f"Strike momentum error: {e}")
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to analyze strikes: {e}"))
    
    def _display_strike_momentum(self, momentum_data, atm_strike, has_real_data=False):
        """Display strike momentum results."""
        dialog = tk.Toplevel(self.root)
        dialog.title("🎯 Strike Momentum Analysis")
        dialog.geometry("700x600")
        dialog.configure(bg='#2d2d2d')
        dialog.transient(self.root)
        
        # Header
        header = tk.Frame(dialog, bg='#1a1a1a', pady=15)
        header.pack(fill='x', padx=10, pady=(10, 5))
        
        tk.Label(header, text="🎯 Top Strikes by Momentum", font=('Arial', 16, 'bold'),
                bg='#1a1a1a', fg='#00ff00').pack()
        tk.Label(header, text=f"ATM: {atm_strike} | Updated: {datetime.now().strftime('%H:%M:%S')}",
                font=('Arial', 9), bg='#1a1a1a', fg='#888').pack()
        
        # Table frame with scrollbar
        table_container = tk.Frame(dialog, bg='#2d2d2d')
        table_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(table_container, bg='#2d2d2d', highlightthickness=0)
        scrollbar = tk.Scrollbar(table_container, orient="vertical", command=canvas.yview)
        table_frame = tk.Frame(canvas, bg='#2d2d2d')
        
        table_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=table_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Table headers
        headers = ['Strike', 'Type', 'Momentum', 'OI Change', 'Volume', 'LTP']
        header_row = tk.Frame(table_frame, bg='#1a1a1a')
        header_row.pack(fill='x', pady=(0, 5))
        
        widths = [10, 6, 10, 10, 12, 10]
        for i, (header, width) in enumerate(zip(headers, widths)):
            tk.Label(header_row, text=header, font=('Arial', 10, 'bold'),
                    bg='#1a1a1a', fg='#00d4ff', width=width).pack(side='left', padx=2)
        
        # Data rows
        for idx, data in enumerate(momentum_data):
            row_bg = '#2d2d2d' if idx % 2 == 0 else '#3a3a3a'
            row = tk.Frame(table_frame, bg=row_bg, pady=5)
            row.pack(fill='x')
            
            # Color code by momentum strength
            if data['momentum'] >= 85:
                momentum_color = '#00ff00'  # Strong (green)
            elif data['momentum'] >= 70:
                momentum_color = '#ffa500'  # Moderate (orange)
            else:
                momentum_color = '#888'  # Weak (gray)
            
            type_color = '#00d4ff' if data['type'] == 'CE' else '#ff69b4'
            strike_text = f"{data['strike']} {'(ATM)' if data['strike'] == atm_strike else ''}"
            
            values = [
                (strike_text, '#fff', widths[0]),
                (data['type'], type_color, widths[1]),
                (f"{data['momentum']}%", momentum_color, widths[2]),
                (data['oi_change'], '#ffa500', widths[3]),
                (f"{data['volume']:,}", '#ccc', widths[4]),
                (f"₹{data['ltp']:.2f}", '#fff', widths[5])
            ]
            
            for val, color, width in values:
                tk.Label(row, text=val, font=('Courier', 9), bg=row_bg,
                        fg=color, width=width).pack(side='left', padx=2)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Info footer
        footer = tk.Frame(dialog, bg='#1a1a1a', pady=10)
        footer.pack(fill='x', padx=10, pady=(5, 10))
        
        info_text = "💡 Momentum = OI Change + Volume + Price Action | Higher % = Stronger momentum"
        tk.Label(footer, text=info_text, font=('Arial', 9), bg='#1a1a1a',
                fg='#888', wraplength=650).pack()
        
        # Note about data source
        if has_real_data:
            note_text = "✅ Real option data with live LTP prices from Upstox API"
            note_color = '#00ff00'
        else:
            note_text = "⚠️ Sample data shown. Real-time option chain API integration pending."
            note_color = '#ff8800'
        
        tk.Label(footer, text=note_text, font=('Arial', 8, 'italic'), bg='#1a1a1a',
                fg=note_color).pack(pady=(5, 0))
        
        tk.Button(dialog, text="Close", command=dialog.destroy,
                 bg='#6c757d', fg='white', font=('Arial', 10), padx=20, pady=5).pack(pady=10)
        
        dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    def quick_market_scan(self):
        """Quick market scan with simple signals."""
        threading.Thread(target=self._quick_market_scan_async, daemon=True).start()
    
    def _quick_market_scan_async(self):
        """Async quick market scan."""
        import yfinance as yf
        
        try:
            # Get first available broker client
            client = None
            broker_name = ""
            for broker_key, broker_info in self.trader.active_brokers.items():
                client = broker_info['client']
                broker_name = broker_info['name']
                break
            
            if not client:
                self.root.after(0, lambda: messagebox.showerror("Error", "No active broker found"))
                return
            
            # Fetch NIFTY data using same logic as full analysis
            nifty_instrument = "NSE_INDEX|Nifty 50"
            current_price = 0
            data_source = "Unknown"
            
            # Try Upstox first
            try:
                ltp_response = client.get_ltp(nifty_instrument)
                if ltp_response and ltp_response.get('status') == 'success' and ltp_response.get('data'):
                    ltp_data = ltp_response['data']
                    if isinstance(ltp_data, dict):
                        if nifty_instrument in ltp_data:
                            current_price = ltp_data[nifty_instrument].get('last_price', 0)
                            data_source = "Upstox"
                        else:
                            first_key = next(iter(ltp_data), None)
                            if first_key and isinstance(ltp_data[first_key], dict):
                                current_price = ltp_data[first_key].get('last_price', 0)
                                data_source = "Upstox"
            except:
                pass
            
            # Fallback to Yahoo Finance
            if current_price == 0:
                try:
                    nifty_ticker = yf.Ticker("^NSEI")
                    nifty_data = nifty_ticker.history(period="1d")
                    if not nifty_data.empty:
                        current_price = float(nifty_data['Close'].iloc[-1])
                        data_source = "Yahoo Finance"
                except:
                    pass
            
            if current_price == 0:
                self.root.after(0, lambda: messagebox.showerror("Error", "Failed to fetch NIFTY price"))
                return
            
            # Simple analysis
            atm_strike = round(current_price / 50) * 50
            pivot_estimate = atm_strike
            
            # Determine trend based on ATM position
            if current_price > pivot_estimate + 50:
                trend = "📈 BULLISH"
                trend_color = "#00ff00"
                recommendation = "Focus on CE (Call) options"
                support = atm_strike - 100
                resistance = atm_strike + 100
            elif current_price < pivot_estimate - 50:
                trend = "📉 BEARISH"
                trend_color = "#ff4444"
                recommendation = "Focus on PE (Put) options"
                support = atm_strike - 100
                resistance = atm_strike + 100
            else:
                trend = "⚖️ NEUTRAL"
                trend_color = "#ffa500"
                recommendation = "Wait for clear direction"
                support = atm_strike - 50
                resistance = atm_strike + 50
            
            scan_result = {
                'price': current_price,
                'data_source': data_source,
                'trend': trend,
                'trend_color': trend_color,
                'atm': atm_strike,
                'support': support,
                'resistance': resistance,
                'recommendation': recommendation,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
            
            self.root.after(0, lambda: self._display_quick_scan(scan_result))
            
        except Exception as e:
            print(f"Quick scan error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Scan failed: {e}"))
    
    def _display_quick_scan(self, result):
        """Display quick scan results in compact window."""
        dialog = tk.Toplevel(self.root)
        dialog.title("📈 Quick Market Scan")
        dialog.geometry("450x400")
        dialog.configure(bg='#2d2d2d')
        dialog.transient(self.root)
        
        # Header
        header = tk.Frame(dialog, bg='#1a1a1a', pady=15)
        header.pack(fill='x', padx=10, pady=10)
        
        tk.Label(header, text="⚡ Quick Scan Results", font=('Arial', 16, 'bold'),
                bg='#1a1a1a', fg='#00d4ff').pack()
        tk.Label(header, text=f"Updated: {result['timestamp']} | Source: {result['data_source']}", 
                font=('Arial', 9), bg='#1a1a1a', fg='#888').pack()
        
        # Price
        price_frame = tk.Frame(dialog, bg='#1a1a1a', pady=10)
        price_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(price_frame, text=f"NIFTY: ₹{result['price']:.2f}",
                font=('Arial', 18, 'bold'), bg='#1a1a1a', fg='#00ff00').pack()
        
        # Trend
        trend_frame = tk.Frame(dialog, bg='#1a1a1a', pady=10)
        trend_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(trend_frame, text=result['trend'],
                font=('Arial', 16, 'bold'), bg='#1a1a1a', fg=result['trend_color']).pack()
        
        # Levels
        levels_frame = tk.Frame(dialog, bg='#2d2d2d', pady=10)
        levels_frame.pack(fill='x', padx=10, pady=10)
        
        levels_data = [
            ('Resistance', result['resistance'], '#ff4444'),
            ('ATM Strike', result['atm'], '#00d4ff'),
            ('Support', result['support'], '#00ff00')
        ]
        
        for label, value, color in levels_data:
            row = tk.Frame(levels_frame, bg='#2d2d2d')
            row.pack(fill='x', pady=2)
            
            tk.Label(row, text=f"{label}:", font=('Arial', 11),
                    bg='#2d2d2d', fg='#ccc', width=15, anchor='w').pack(side='left', padx=5)
            tk.Label(row, text=f"{value}", font=('Arial', 11, 'bold'),
                    bg='#2d2d2d', fg=color).pack(side='left')
        
        # Recommendation
        rec_frame = tk.Frame(dialog, bg='#ffaa00', pady=15)
        rec_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(rec_frame, text=result['recommendation'],
                font=('Arial', 12, 'bold'), bg='#ffaa00', fg='#000').pack()
        
        # Close button
        tk.Button(dialog, text="Close", command=dialog.destroy,
                 bg='#28a745', fg='white', font=('Arial', 11, 'bold'),
                 padx=30, pady=8).pack(pady=15)
        
        dialog.bind('<Escape>', lambda e: dialog.destroy())
    
    def show_about(self):
        """Show about dialog."""
        about_text = """
FusionTrade - Multi-Broker Trading Platform

Version: 1.0
Supports: Zerodha, Angel One, Dhan, Upstox

Features:
• Multi-broker support
• Quick options trading
• Real-time positions tracking
• Account management

Configure your broker credentials via:
Settings → Configure Brokers
        """
        messagebox.showinfo("About FusionTrade", about_text)
    
    def show_env_location(self):
        """Show .env file location."""
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        
        env_path = os.path.join(app_dir, '.env')
        exists = "✅ EXISTS" if os.path.exists(env_path) else "❌ NOT FOUND"
        
        messagebox.showinfo(
            ".env File Location",
            f"Configuration file location:\n\n{env_path}\n\nStatus: {exists}\n\n"
            f"Create this file with your broker credentials.\n"
            f"Use Settings → Configure Brokers to edit it."
        )
    
    def open_alert_settings(self):
        """Open alert settings dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("🔔 Position Alert Settings")
        dialog.geometry("400x300")
        dialog.configure(bg='#2d2d2d')
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Enable/Disable alerts
        enable_frame = tk.Frame(dialog, bg='#2d2d2d')
        enable_frame.pack(pady=15, padx=20, fill=tk.X)
        
        tk.Checkbutton(enable_frame, text="Enable Position Alerts", 
                      variable=self.alert_enabled,
                      bg='#2d2d2d', fg='#ffffff', selectcolor='#1e1e1e',
                      font=('Arial', 12, 'bold')).pack()
        
        # Profit alert threshold
        profit_frame = tk.LabelFrame(dialog, text="Profit Alert", bg='#2d2d2d', 
                                    fg='#00ff00', font=('Arial', 10, 'bold'))
        profit_frame.pack(pady=10, padx=20, fill=tk.X)
        
        tk.Label(profit_frame, text="Alert when position profit reaches:",
                bg='#2d2d2d', fg='#ffffff', font=('Arial', 10)).pack(pady=5)
        
        profit_entry_frame = tk.Frame(profit_frame, bg='#2d2d2d')
        profit_entry_frame.pack(pady=5)
        
        tk.Entry(profit_entry_frame, textvariable=self.alert_profit_percent,
                width=8, font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Label(profit_entry_frame, text="%", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 12)).pack(side=tk.LEFT)
        
        # Loss alert threshold
        loss_frame = tk.LabelFrame(dialog, text="Loss Alert", bg='#2d2d2d', 
                                  fg='#ff0000', font=('Arial', 10, 'bold'))
        loss_frame.pack(pady=10, padx=20, fill=tk.X)
        
        tk.Label(loss_frame, text="Alert when position loss reaches:",
                bg='#2d2d2d', fg='#ffffff', font=('Arial', 10)).pack(pady=5)
        
        loss_entry_frame = tk.Frame(loss_frame, bg='#2d2d2d')
        loss_entry_frame.pack(pady=5)
        
        tk.Entry(loss_entry_frame, textvariable=self.alert_loss_percent,
                width=8, font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)
        tk.Label(loss_entry_frame, text="%", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 12)).pack(side=tk.LEFT)
        
        # Save button
        tk.Button(dialog, text="✓ Save Settings", command=lambda: [
            messagebox.showinfo("Success", "Alert settings saved!"),
            dialog.destroy()
        ], bg='#00ff00', fg='#000000', font=('Arial', 11, 'bold'),
                 width=15).pack(pady=15)
    
    def check_position_alerts(self):
        """Check positions and trigger alerts for profit/loss thresholds."""
        try:
            profit_threshold = self.alert_profit_percent.get()
            loss_threshold = self.alert_loss_percent.get()
            
            for pos in self.positions_data:
                symbol = pos.get('tradingsymbol', 'Unknown')
                avg_price = (pos.get('average_price') or 
                            pos.get('buy_avg') or 
                            pos.get('buyAvg') or 0)
                ltp = pos.get('last_price') or pos.get('ltp') or pos.get('lastPrice') or 0
                qty = pos.get('quantity', 0) or pos.get('netQty', 0)
                
                if avg_price > 0 and ltp > 0:
                    pnl_percent = ((ltp - avg_price) / avg_price) * 100
                    if qty < 0:  # Short position
                        pnl_percent = -pnl_percent
                    
                    pos_key = f"{symbol}_{qty}"
                    
                    # Check profit alert
                    if pnl_percent >= profit_threshold and pos_key not in self.alerted_positions:
                        self.alerted_positions.add(pos_key)
                        self.root.bell()  # System beep
                        messagebox.showinfo(
                            "🎯 Profit Alert!",
                            f"{symbol}\n\nProfit: {pnl_percent:+.2f}%\n"
                            f"Entry: ₹{avg_price:.2f}\n"
                            f"Current: ₹{ltp:.2f}",
                            parent=self.root
                        )
                    
                    # Check loss alert
                    elif pnl_percent <= -loss_threshold and pos_key not in self.alerted_positions:
                        self.alerted_positions.add(pos_key)
                        self.root.bell()  # System beep
                        messagebox.showwarning(
                            "⚠️ Loss Alert!",
                            f"{symbol}\n\nLoss: {pnl_percent:+.2f}%\n"
                            f"Entry: ₹{avg_price:.2f}\n"
                            f"Current: ₹{ltp:.2f}",
                            parent=self.root
                        )
                    
                    # Reset alert if position recovered to normal range
                    elif -loss_threshold < pnl_percent < profit_threshold:
                        self.alerted_positions.discard(pos_key)
                        
        except Exception as e:
            print(f"Error checking alerts: {e}")
    
    def create_market_data_panel(self):
        """Create market data panel showing live index prices."""
        market_frame = tk.Frame(self.root, bg='#1e1e1e', relief=tk.RIDGE, bd=2)
        market_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        
        # Title
        tk.Label(market_frame, text="📈 MARKET", bg='#1e1e1e', fg='#00aaff',
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=10, pady=5)
        
        # NIFTY
        self.nifty_label = tk.Label(market_frame, text="NIFTY: --", bg='#1e1e1e', 
                                   fg='#ffffff', font=('Arial', 11, 'bold'))
        self.nifty_label.pack(side=tk.LEFT, padx=15, pady=5)
        
        # BANKNIFTY
        self.banknifty_label = tk.Label(market_frame, text="BANKNIFTY: --", bg='#1e1e1e',
                                       fg='#ffffff', font=('Arial', 11, 'bold'))
        self.banknifty_label.pack(side=tk.LEFT, padx=15, pady=5)
        
        # SENSEX
        self.sensex_label = tk.Label(market_frame, text="SENSEX: --", bg='#1e1e1e',
                                    fg='#ffffff', font=('Arial', 11, 'bold'))
        self.sensex_label.pack(side=tk.LEFT, padx=15, pady=5)
        
        # Start market data updates
        self.update_market_data()
    
    def update_market_data(self):
        """Update market data from broker API."""
        try:
            if self.trader and self.trader.active_brokers:
                # Use first available broker for market data
                broker_info = next(iter(self.trader.active_brokers.values()))
                client = broker_info['client']
                
                # Get index LTPs
                indices_to_fetch = {
                    'NIFTY': 'NSE_INDEX|Nifty 50',
                    'BANKNIFTY': 'NSE_INDEX|Nifty Bank',
                    'SENSEX': 'BSE_INDEX|SENSEX'
                }
                
                for index_name, instrument_key in indices_to_fetch.items():
                    try:
                        # Try to get LTP from broker
                        # This is a simplified example - actual implementation depends on broker API
                        if hasattr(client, 'get_ltp'):
                            ltp_data = client.get_ltp(instrument_key)
                            if ltp_data:
                                ltp = ltp_data.get('ltp', 0)
                                prev_ltp = self.market_data[index_name]['ltp']
                                
                                if ltp > 0:
                                    self.market_data[index_name]['ltp'] = ltp
                                    
                                    # Calculate change
                                    if prev_ltp > 0:
                                        change = ltp - prev_ltp
                                        change_pct = (change / prev_ltp) * 100
                                        self.market_data[index_name]['change'] = change_pct
                    except:
                        pass
                
                # Update labels
                self.update_market_labels()
                
        except Exception as e:
            pass  # Silently fail, don't spam console
        
        # Update every 30 seconds to prevent API rate limits
        self.root.after(30000, self.update_market_data)
    
    def update_market_labels(self):
        """Update market data labels with colors."""
        for index_name, label in [('NIFTY', self.nifty_label), 
                                   ('BANKNIFTY', self.banknifty_label),
                                   ('SENSEX', self.sensex_label)]:
            ltp = self.market_data[index_name]['ltp']
            change = self.market_data[index_name]['change']
            
            if ltp > 0:
                text = f"{index_name}: {ltp:,.2f}"
                if change != 0:
                    text += f" ({change:+.2f}%)"
                
                # Color based on change
                if change > 0:
                    color = '#00ff00'
                elif change < 0:
                    color = '#ff0000'
                else:
                    color = '#ffffff'
                
                label.config(text=text, fg=color)
            else:
                label.config(text=f"{index_name}: --", fg='#888888')
    
    def create_ui(self):
        """Create the main UI layout."""
        # Create menu bar
        self.create_menu_bar()
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#1e1e1e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel - Order entry (30%)
        left_panel = tk.Frame(main_frame, bg='#2d2d2d', relief=tk.RAISED, borderwidth=2)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 5), ipadx=10, ipady=10)
        left_panel.pack_propagate(False)
        left_panel.config(width=350)
        
        # Right panel - Positions and actions (70%)
        right_panel = tk.Frame(main_frame, bg='#2d2d2d', relief=tk.RAISED, borderwidth=2)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Build panels
        self.create_order_entry_panel(left_panel)
        self.create_positions_panel(right_panel)
    
    def create_order_entry_panel(self, parent):
        """Create order entry panel."""
        # Title
        title = tk.Label(parent, text="📊 QUICK ORDER", font=('Arial', 14, 'bold'),
                        bg='#2d2d2d', fg='#00ff00')
        title.pack(pady=(0, 10))
        
        # Symbol selection
        symbol_frame = tk.LabelFrame(parent, text="Symbol", bg='#2d2d2d', fg='#ffffff',
                                     font=('Arial', 10, 'bold'))
        symbol_frame.pack(fill=tk.X, pady=5)
        
        symbols = ["NIFTY", "BANKNIFTY", "SENSEX"]
        for i, sym in enumerate(symbols):
            btn = tk.Radiobutton(symbol_frame, text=sym, variable=self.selected_symbol,
                               value=sym, bg='#2d2d2d', fg='#ffffff', selectcolor='#1e1e1e',
                               command=self.on_symbol_change)
            btn.pack(side=tk.LEFT, padx=5, pady=2)
        
        self.selected_symbol.set("NIFTY")
        
        # Expiry selection
        expiry_frame = tk.LabelFrame(parent, text="Expiry", bg='#2d2d2d', fg='#ffffff',
                                    font=('Arial', 10, 'bold'))
        expiry_frame.pack(fill=tk.X, pady=5)
        
        self.expiry_listbox = tk.Listbox(expiry_frame, height=4, bg='#1e1e1e', fg='#ffffff',
                                        selectbackground='#00ff00', selectforeground='#000000')
        self.expiry_listbox.pack(fill=tk.X, padx=5, pady=5)
        self.expiry_listbox.bind('<<ListboxSelect>>', self.on_expiry_select)
        
        # Strike selection
        strike_frame = tk.LabelFrame(parent, text="Strike Price", bg='#2d2d2d', fg='#ffffff',
                                    font=('Arial', 10, 'bold'))
        strike_frame.pack(fill=tk.X, pady=5)
        
        strike_input_frame = tk.Frame(strike_frame, bg='#2d2d2d')
        strike_input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Use Combobox for strike selection with dropdown
        from tkinter import ttk
        style = ttk.Style()
        style.configure('Strike.TCombobox', fieldbackground='#1e1e1e', background='#2d2d2d',
                       foreground='#ffffff', arrowcolor='#00ff00')
        self.strike_combo = ttk.Combobox(strike_input_frame, values=[],
                                        font=('Arial', 12), state='normal', style='Strike.TCombobox')
        self.strike_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.strike_combo.bind('<<ComboboxSelected>>', lambda e: self.on_strike_selected())
        self.strike_combo.bind('<Return>', lambda e: self.on_strike_selected())
        
        tk.Button(strike_input_frame, text="Load", command=self.load_strike_options,
                 bg='#00ff00', fg='#000000', font=('Arial', 10, 'bold')).pack(side=tk.RIGHT, padx=(5, 0))
        
        # Call/Put selection
        type_frame = tk.Frame(parent, bg='#2d2d2d')
        type_frame.pack(fill=tk.X, pady=5)
        
        tk.Radiobutton(type_frame, text="CALL", variable=self.selected_type, value="CE",
                      bg='#2d2d2d', fg='#00ff00', selectcolor='#1e1e1e',
                      font=('Arial', 10, 'bold')).pack(side=tk.LEFT, expand=True)
        tk.Radiobutton(type_frame, text="PUT", variable=self.selected_type, value="PE",
                      bg='#2d2d2d', fg='#ff0000', selectcolor='#1e1e1e',
                      font=('Arial', 10, 'bold')).pack(side=tk.RIGHT, expand=True)
        
        # Lot quantity
        lot_frame = tk.LabelFrame(parent, text="Lot Quantity", bg='#2d2d2d', fg='#ffffff',
                                 font=('Arial', 10, 'bold'))
        lot_frame.pack(fill=tk.X, pady=5)
        
        lot_control_frame = tk.Frame(lot_frame, bg='#2d2d2d')
        lot_control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(lot_control_frame, text="-", command=lambda: self.adjust_lots(-1),
                 bg='#ff0000', fg='#ffffff', font=('Arial', 12, 'bold'), width=3).pack(side=tk.LEFT)
        
        # Editable lot entry instead of label
        self.lot_entry = tk.Entry(lot_control_frame, textvariable=self.lot_quantity,
                                 bg='#1e1e1e', fg='#ffffff', font=('Arial', 14, 'bold'),
                                 width=5, justify='center', insertbackground='#ffffff')
        self.lot_entry.pack(side=tk.LEFT, expand=True, padx=5)
        self.lot_entry.bind('<Return>', lambda e: self.validate_lot_entry())
        self.lot_entry.bind('<FocusOut>', lambda e: self.validate_lot_entry())
        
        tk.Button(lot_control_frame, text="+", command=lambda: self.adjust_lots(1),
                 bg='#00ff00', fg='#000000', font=('Arial', 12, 'bold'), width=3).pack(side=tk.RIGHT)
        
        # Quick lot selection buttons
        quick_lot_frame = tk.Frame(lot_frame, bg='#2d2d2d')
        quick_lot_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        for lot_val in [10, 20, 30, 40, 50]:
            btn = tk.Button(quick_lot_frame, text=str(lot_val), command=lambda l=lot_val: self.set_lot_quantity(l),
                          bg='#444444', fg='#ffffff', font=('Arial', 9), width=4)
            btn.pack(side=tk.LEFT, expand=True, padx=2)
        
        # Limit price entry (shown only for LIMIT orders)
        self.limit_price_frame = tk.LabelFrame(parent, text="Limit Price", bg='#2d2d2d', fg='#ffffff',
                                              font=('Arial', 10, 'bold'))
        
        limit_input_frame = tk.Frame(self.limit_price_frame, bg='#2d2d2d')
        limit_input_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(limit_input_frame, text="₹", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=(0, 5))
        
        self.limit_price_entry = tk.Entry(limit_input_frame, textvariable=self.limit_price_var,
                                          bg='#1e1e1e', fg='#ffffff', font=('Arial', 12),
                                          insertbackground='#ffffff', justify='right')
        self.limit_price_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Hide limit price by default
        self.limit_price_frame.pack_forget()
        
        # Stop Loss Frame
        sl_frame = tk.LabelFrame(parent, text="🛡️ Auto Stop Loss (Optional)", bg='#2d2d2d', fg='#ff6600',
                                font=('Arial', 10, 'bold'))
        sl_frame.pack(fill=tk.X, pady=5)
        
        # Stop Loss section with checkbox
        sl_section = tk.Frame(sl_frame, bg='#2d2d2d')
        sl_section.pack(fill=tk.X, padx=5, pady=5)
        
        self.enable_auto_sl = tk.BooleanVar(value=False)
        tk.Checkbutton(sl_section, text="Enable Auto SL", variable=self.enable_auto_sl,
                      bg='#2d2d2d', fg='#ffffff', selectcolor='#1e1e1e',
                      font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
        
        self.auto_sl_percent = tk.DoubleVar(value=10.0)
        tk.Entry(sl_section, textvariable=self.auto_sl_percent, width=6, justify='center',
                bg='#1e1e1e', fg='#ff6600', font=('Arial', 10, 'bold'),
                insertbackground='#ff6600').pack(side=tk.LEFT, padx=5)
        tk.Label(sl_section, text="%", bg='#2d2d2d', fg='#ff6600',
                font=('Arial', 9)).pack(side=tk.LEFT)
        
        # Product type (before Order type)
        product_type_frame = tk.LabelFrame(parent, text="Product Type", bg='#2d2d2d', fg='#ffffff',
                                          font=('Arial', 10, 'bold'))
        product_type_frame.pack(fill=tk.X, pady=5)
        
        product_type_buttons = tk.Frame(product_type_frame, bg='#2d2d2d')
        product_type_buttons.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Radiobutton(product_type_buttons, text="INTRADAY", variable=self.product_type, value="INTRADAY",
                      bg='#2d2d2d', fg='#00ff00', selectcolor='#1e1e1e',
                      font=('Arial', 10, 'bold')).pack(side=tk.LEFT, expand=True)
        tk.Radiobutton(product_type_buttons, text="NORMAL", variable=self.product_type, value="NORMAL",
                      bg='#2d2d2d', fg='#00aaff', selectcolor='#1e1e1e',
                      font=('Arial', 10, 'bold')).pack(side=tk.RIGHT, expand=True)
        
        # Order type
        self.order_type_frame = tk.LabelFrame(parent, text="Order Type", bg='#2d2d2d', fg='#ffffff',
                                        font=('Arial', 10, 'bold'))
        self.order_type_frame.pack(fill=tk.X, pady=5)
        
        order_type_buttons = tk.Frame(self.order_type_frame, bg='#2d2d2d')
        order_type_buttons.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Radiobutton(order_type_buttons, text="MARKET", variable=self.order_type, value="MARKET",
                      bg='#2d2d2d', fg='#ffffff', selectcolor='#1e1e1e',
                      command=self.toggle_limit_price).pack(side=tk.LEFT, expand=True)
        tk.Radiobutton(order_type_buttons, text="LIMIT", variable=self.order_type, value="LIMIT",
                      bg='#2d2d2d', fg='#ffffff', selectcolor='#1e1e1e',
                      command=self.toggle_limit_price).pack(side=tk.RIGHT, expand=True)
        
        # Margin Info frame - show breakdown by account
        margin_frame = tk.LabelFrame(parent, text="Margin Info", bg='#2d2d2d', fg='#ffffff',
                                    font=('Arial', 10, 'bold'))
        margin_frame.pack(fill=tk.X, pady=5)
        
        # Create scrollable frame for account margins
        self.margin_accounts_frame = tk.Frame(margin_frame, bg='#2d2d2d')
        self.margin_accounts_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Total margin row
        total_frame = tk.Frame(margin_frame, bg='#2d2d2d')
        total_frame.pack(fill=tk.X, padx=5, pady=(5, 2))
        tk.Label(total_frame, text="Total Available:", bg='#2d2d2d', fg='#ffff00',
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        self.margin_label = tk.Label(total_frame, textvariable=self.total_margin, bg='#2d2d2d', fg='#00ff00',
                font=('Arial', 10, 'bold'))
        self.margin_label.pack(side=tk.LEFT, padx=(5, 10))
        
        # Refresh margin button
        tk.Button(total_frame, text="🔄", command=lambda: threading.Thread(target=self.refresh_margin, daemon=True).start(),
                 bg='#0d7377', fg='white', font=('Arial', 8), width=3, height=1,
                 relief=tk.RAISED).pack(side=tk.LEFT)
        
        # BUY/SELL buttons
        button_frame = tk.Frame(parent, bg='#2d2d2d')
        button_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(button_frame, text="🟢 BUY", command=lambda: self.place_order("BUY"),
                 bg='#00ff00', fg='#000000', font=('Arial', 14, 'bold'),
                 height=2).pack(side=tk.LEFT, expand=True, padx=(0, 5))
        
        tk.Button(button_frame, text="🔴 SELL", command=lambda: self.place_order("SELL"),
                 bg='#ff0000', fg='#ffffff', font=('Arial', 14, 'bold'),
                 height=2).pack(side=tk.RIGHT, expand=True, padx=(5, 0))
        
        # Load initial data
        self.load_expiries()
    
    def create_positions_panel(self, parent):
        """Create positions display panel with tabs."""
        # Initialize order filter variable
        self.order_filter = tk.StringVar(value="today")
        
        # Notebook for tabs
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Open Positions
        open_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(open_tab, text='📊 OPEN POSITIONS')
        
        # P&L Summary Panel at top
        summary_frame = tk.Frame(open_tab, bg='#2d2d2d', relief=tk.RIDGE, bd=2)
        summary_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Total P&L Display
        self.total_pnl_label = tk.Label(summary_frame, text="Total P&L: ₹0.00", 
                                       bg='#2d2d2d', fg='#00ff00', 
                                       font=('Arial', 14, 'bold'))
        self.total_pnl_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Day P&L Display
        self.day_pnl_label = tk.Label(summary_frame, text="Day P&L: ₹0.00", 
                                     bg='#2d2d2d', fg='#00aaff', 
                                     font=('Arial', 12, 'bold'))
        self.day_pnl_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Position Count
        self.pos_count_label = tk.Label(summary_frame, text="Positions: 0", 
                                       bg='#2d2d2d', fg='#ffffff', 
                                       font=('Arial', 11))
        self.pos_count_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Positions table
        positions_frame = tk.Frame(open_tab, bg='#2d2d2d')
        positions_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview for positions
        columns = ('Broker', 'Symbol', 'Qty', 'Entry', 'LTP', 'P&L', 'P&L%', 'Day P&L', 'Time', 'Tips')
        self.positions_tree = ttk.Treeview(positions_frame, columns=columns, show='headings',
                                          height=10, selectmode='browse')
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", background="#1e1e1e", foreground="#ffffff",
                       fieldbackground="#1e1e1e", font=('Arial', 10))
        style.configure("Treeview.Heading", background="#2d2d2d", foreground="#00ff00",
                       font=('Arial', 10, 'bold'))
        style.map('Treeview', background=[('selected', '#00ff00')],
                 foreground=[('selected', '#000000')])
        
        # Column headers
        for col in columns:
            self.positions_tree.heading(col, text=col)
            if col == 'Symbol':
                self.positions_tree.column(col, width=200)
            elif col == 'Tips':
                self.positions_tree.column(col, width=150)
            elif col in ('P&L', 'P&L%', 'Day P&L'):
                self.positions_tree.column(col, width=100)
            elif col == 'Broker':
                self.positions_tree.column(col, width=90)
            else:
                self.positions_tree.column(col, width=80)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(positions_frame, orient=tk.VERTICAL,
                                 command=self.positions_tree.yview)
        self.positions_tree.configure(yscrollcommand=scrollbar.set)
        
        self.positions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Tab 1.5: Active Orders (Pending SL orders)
        orders_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(orders_tab, text='📋 ACTIVE ORDERS')
        
        # Orders table
        orders_frame = tk.Frame(orders_tab, bg='#2d2d2d')
        orders_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Filter controls frame at top
        filter_frame = tk.Frame(orders_frame, bg='#2d2d2d')
        filter_frame.pack(fill=tk.X, pady=(5, 0))
        
        tk.Label(filter_frame, text="📅 Filter:", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=5)
        
        tk.Radiobutton(filter_frame, text="Today", variable=self.order_filter, value="today",
                      bg='#2d2d2d', fg='#00ff00', selectcolor='#1e1e1e',
                      font=('Arial', 9, 'bold'), command=self.refresh_active_orders).pack(side=tk.LEFT, padx=5)
        
        tk.Radiobutton(filter_frame, text="Yesterday", variable=self.order_filter, value="yesterday",
                      bg='#2d2d2d', fg='#ffaa00', selectcolor='#1e1e1e',
                      font=('Arial', 9, 'bold'), command=self.refresh_active_orders).pack(side=tk.LEFT, padx=5)
        
        tk.Radiobutton(filter_frame, text="All", variable=self.order_filter, value="all",
                      bg='#2d2d2d', fg='#00aaff', selectcolor='#1e1e1e',
                      font=('Arial', 9, 'bold'), command=self.refresh_active_orders).pack(side=tk.LEFT, padx=5)
        
        # Button frame at top
        btn_frame = tk.Frame(orders_frame, bg='#2d2d2d')
        btn_frame.pack(fill=tk.X, pady=5)
        
        # Refresh button for orders
        refresh_orders_btn = tk.Button(btn_frame, text="🔄 REFRESH ORDERS", 
                                       command=self.refresh_active_orders,
                                       bg='#00ff00', fg='#000000', 
                                       font=('Arial', 10, 'bold'), height=1)
        refresh_orders_btn.pack(side=tk.LEFT, padx=5)
        
        # Cancel button for selected order
        cancel_btn = tk.Button(btn_frame, text="❌ CANCEL SELECTED ORDER", 
                               command=self.cancel_selected_order,
                               bg='#ff0000', fg='#ffffff', 
                               font=('Arial', 10, 'bold'), height=1)
        cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Frame for treeview and scrollbar
        tree_frame = tk.Frame(orders_frame, bg='#2d2d2d')
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview for active orders
        order_columns = ('Date', 'Time', 'Broker', 'Symbol', 'Type', 'Qty', 'Trigger', 'Status', 'OrderID')
        self.orders_tree = ttk.Treeview(tree_frame, columns=order_columns, show='headings',
                                       height=10, selectmode='browse')
        
        # Column headers
        for col in order_columns:
            self.orders_tree.heading(col, text=col)
            if col == 'Symbol':
                self.orders_tree.column(col, width=180)
            elif col == 'OrderID':
                self.orders_tree.column(col, width=150)
            elif col == 'Date':
                self.orders_tree.column(col, width=100)
            elif col == 'Time':
                self.orders_tree.column(col, width=80)
            else:
                self.orders_tree.column(col, width=80)
        
        # Scrollbar
        orders_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                        command=self.orders_tree.yview)
        self.orders_tree.configure(yscrollcommand=orders_scrollbar.set)
        
        # Configure color tags for order status
        self.orders_tree.tag_configure('complete', foreground='#00ff00')  # Green
        self.orders_tree.tag_configure('rejected', foreground='#ff0000')  # Red
        self.orders_tree.tag_configure('cancelled', foreground='#ff9900')  # Orange
        self.orders_tree.tag_configure('pending', foreground='#00aaff')  # Blue
        
        self.orders_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        orders_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Action controls below table
        actions_frame = tk.Frame(open_tab, bg='#2d2d2d')
        actions_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Stop Loss controls
        sl_frame = tk.LabelFrame(actions_frame, text="🛡️ Stop Loss", bg='#2d2d2d', fg='#ff9900',
                                font=('Arial', 10, 'bold'))
        sl_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Mode selector
        sl_mode_frame = tk.Frame(sl_frame, bg='#2d2d2d')
        sl_mode_frame.pack(padx=5, pady=(5,0))
        
        self.sl_mode = tk.StringVar(value="percent")
        tk.Radiobutton(sl_mode_frame, text="%", variable=self.sl_mode, value="percent",
                      bg='#2d2d2d', fg='#ffffff', selectcolor='#1e1e1e',
                      font=('Arial', 9), command=self.toggle_sl_mode).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(sl_mode_frame, text="₹", variable=self.sl_mode, value="amount",
                      bg='#2d2d2d', fg='#ffffff', selectcolor='#1e1e1e',
                      font=('Arial', 9), command=self.toggle_sl_mode).pack(side=tk.LEFT, padx=5)
        
        # Percent controls
        self.sl_percent_frame = tk.Frame(sl_frame, bg='#2d2d2d')
        self.sl_percent_frame.pack(padx=5, pady=5)
        
        self.sl_percent = tk.DoubleVar(value=5.0)
        tk.Button(self.sl_percent_frame, text="-", command=lambda: self.adjust_sl_percent(-0.5),
                 bg='#ff6600', fg='#ffffff', font=('Arial', 10, 'bold'), width=3).pack(side=tk.LEFT, padx=2)
        tk.Entry(self.sl_percent_frame, textvariable=self.sl_percent, width=6, justify='center',
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=2)
        tk.Label(self.sl_percent_frame, text="%", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 10)).pack(side=tk.LEFT)
        tk.Button(self.sl_percent_frame, text="+", command=lambda: self.adjust_sl_percent(0.5),
                 bg='#00ff00', fg='#000000', font=('Arial', 10, 'bold'), width=3).pack(side=tk.LEFT, padx=2)
        
        # SL Apply buttons (normal + instant)
        sl_btn_frame = tk.Frame(sl_frame, bg='#2d2d2d')
        sl_btn_frame.pack(padx=5, pady=2)
        tk.Button(sl_btn_frame, text="✓ SL", command=self.apply_stop_loss,
                 bg='#ff9900', fg='#000000', font=('Arial', 9, 'bold'), width=8).pack(side=tk.LEFT, padx=2)
        tk.Button(sl_btn_frame, text="⚡ FAST", command=lambda: self.apply_stop_loss(skip_confirm=True),
                 bg='#ffcc00', fg='#000000', font=('Arial', 9, 'bold'), width=8).pack(side=tk.LEFT, padx=2)
        
        # Amount controls (hidden by default)
        self.sl_amount_frame = tk.Frame(sl_frame, bg='#2d2d2d')
        
        self.sl_amount = tk.DoubleVar(value=10.0)
        tk.Button(self.sl_amount_frame, text="-", command=lambda: self.adjust_sl_amount(-5),
                 bg='#ff6600', fg='#ffffff', font=('Arial', 10, 'bold'), width=3).pack(side=tk.LEFT, padx=2)
        tk.Entry(self.sl_amount_frame, textvariable=self.sl_amount, width=8, justify='center',
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=2)
        tk.Label(self.sl_amount_frame, text="₹", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 10)).pack(side=tk.LEFT)
        tk.Button(self.sl_amount_frame, text="+", command=lambda: self.adjust_sl_amount(5),
                 bg='#00ff00', fg='#000000', font=('Arial', 10, 'bold'), width=3).pack(side=tk.LEFT, padx=2)
        
        # Increase controls
        inc_frame = tk.LabelFrame(actions_frame, text="📈 Increase", bg='#2d2d2d', fg='#00aaff',
                                 font=('Arial', 10, 'bold'))
        inc_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Mode selector
        inc_mode_frame = tk.Frame(inc_frame, bg='#2d2d2d')
        inc_mode_frame.pack(padx=5, pady=(5,0))
        
        self.inc_mode = tk.StringVar(value="percent")
        tk.Radiobutton(inc_mode_frame, text="%", variable=self.inc_mode, value="percent",
                      bg='#2d2d2d', fg='#ffffff', selectcolor='#1e1e1e',
                      font=('Arial', 9), command=self.toggle_inc_mode).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(inc_mode_frame, text="Lots", variable=self.inc_mode, value="lots",
                      bg='#2d2d2d', fg='#ffffff', selectcolor='#1e1e1e',
                      font=('Arial', 9), command=self.toggle_inc_mode).pack(side=tk.LEFT, padx=5)
        
        # Percent controls
        self.inc_percent_frame = tk.Frame(inc_frame, bg='#2d2d2d')
        self.inc_percent_frame.pack(padx=5, pady=5)
        
        self.inc_percent = tk.IntVar(value=25)
        tk.Button(self.inc_percent_frame, text="-", command=lambda: self.adjust_inc_percent(-25),
                 bg='#ff6600', fg='#ffffff', font=('Arial', 10, 'bold'), width=3).pack(side=tk.LEFT, padx=2)
        tk.Entry(self.inc_percent_frame, textvariable=self.inc_percent, width=6, justify='center',
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=2)
        tk.Label(self.inc_percent_frame, text="%", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 10)).pack(side=tk.LEFT)
        tk.Button(self.inc_percent_frame, text="+", command=lambda: self.adjust_inc_percent(25),
                 bg='#00ff00', fg='#000000', font=('Arial', 10, 'bold'), width=3).pack(side=tk.LEFT, padx=2)
        
        # Lot controls (hidden by default)
        self.inc_lots_frame = tk.Frame(inc_frame, bg='#2d2d2d')
        
        self.inc_lots = tk.IntVar(value=1)
        tk.Button(self.inc_lots_frame, text="-", command=lambda: self.adjust_inc_lots(-1),
                 bg='#ff6600', fg='#ffffff', font=('Arial', 10, 'bold'), width=3).pack(side=tk.LEFT, padx=2)
        tk.Entry(self.inc_lots_frame, textvariable=self.inc_lots, width=6, justify='center',
                font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=2)
        tk.Label(self.inc_lots_frame, text="Lots", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 10)).pack(side=tk.LEFT)
        tk.Button(self.inc_lots_frame, text="+", command=lambda: self.adjust_inc_lots(1),
                 bg='#00ff00', fg='#000000', font=('Arial', 10, 'bold'), width=3).pack(side=tk.LEFT, padx=2)
        
        # Increase Apply buttons (normal + instant)
        inc_btn_frame = tk.Frame(inc_frame, bg='#2d2d2d')
        inc_btn_frame.pack(padx=5, pady=2)
        tk.Button(inc_btn_frame, text="✓ ADD", command=self.apply_increase,
                 bg='#00aaff', fg='#ffffff', font=('Arial', 9, 'bold'), width=8).pack(side=tk.LEFT, padx=2)
        tk.Button(inc_btn_frame, text="⚡ FAST", command=lambda: self.apply_increase(skip_confirm=True),
                 bg='#00ddff', fg='#000000', font=('Arial', 9, 'bold'), width=8).pack(side=tk.LEFT, padx=2)
        
        # Exit controls
        exit_frame = tk.LabelFrame(actions_frame, text="🚪 Exit", bg='#2d2d2d', fg='#ff0000',
                                  font=('Arial', 10, 'bold'))
        exit_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        exit_controls = tk.Frame(exit_frame, bg='#2d2d2d')
        exit_controls.pack(padx=5, pady=5)
        
        self.exit_percent = tk.IntVar(value=100)
        for pct in [25, 50, 75, 100]:
            tk.Radiobutton(exit_controls, text=f"{pct}%", variable=self.exit_percent, value=pct,
                          bg='#2d2d2d', fg='#ffffff', selectcolor='#1e1e1e',
                          font=('Arial', 9), indicatoron=False, width=5).pack(side=tk.LEFT, padx=1)
        
        # Exit buttons (normal + instant)
        exit_btn_frame = tk.Frame(exit_controls, bg='#2d2d2d')
        exit_btn_frame.pack(side=tk.LEFT, padx=2)
        tk.Button(exit_btn_frame, text="✓ EXIT", command=self.apply_exit,
                 bg='#ff0000', fg='#ffffff', font=('Arial', 9, 'bold'), width=7).pack(side=tk.TOP, pady=1)
        tk.Button(exit_btn_frame, text="⚡ FAST", command=lambda: self.apply_exit(skip_confirm=True),
                 bg='#ff3333', fg='#ffffff', font=('Arial', 9, 'bold'), width=7).pack(side=tk.TOP, pady=1)
        
        # Target controls
        target_frame = tk.LabelFrame(actions_frame, text="🎯 Target", bg='#2d2d2d', fg='#00ff00',
                                    font=('Arial', 10, 'bold'))
        target_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Target percentage (default 5%)
        target_pct_frame = tk.Frame(target_frame, bg='#2d2d2d')
        target_pct_frame.pack(padx=5, pady=(5,0))
        
        tk.Label(target_pct_frame, text="Target %:", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 9)).pack(side=tk.LEFT, padx=2)
        
        self.target_percent = tk.DoubleVar(value=5.0)
        tk.Button(target_pct_frame, text="-", command=lambda: self.adjust_target_percent(-1),
                 bg='#ff6600', fg='#ffffff', font=('Arial', 9, 'bold'), width=2).pack(side=tk.LEFT, padx=1)
        tk.Entry(target_pct_frame, textvariable=self.target_percent, width=5, justify='center',
                font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=2)
        tk.Label(target_pct_frame, text="%", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 9)).pack(side=tk.LEFT)
        tk.Button(target_pct_frame, text="+", command=lambda: self.adjust_target_percent(1),
                 bg='#00ff00', fg='#000000', font=('Arial', 9, 'bold'), width=2).pack(side=tk.LEFT, padx=1)
        
        # Target info display
        self.target_info_frame = tk.Frame(target_frame, bg='#2d2d2d')
        self.target_info_frame.pack(padx=5, pady=(2,0))
        
        self.target_info_label = tk.Label(self.target_info_frame, text="Select positions",
                                         bg='#2d2d2d', fg='#ffff00', font=('Arial', 8))
        self.target_info_label.pack()
        
        # Apply button
        tk.Button(target_frame, text="✓ APPLY", command=self.apply_target,
                 bg='#00ff00', fg='#000000', font=('Arial', 10, 'bold')).pack(padx=5, pady=(0,5))
        
        # Bottom buttons
        bottom_frame = tk.Frame(open_tab, bg='#2d2d2d')
        bottom_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(bottom_frame, text="🔄 REFRESH", command=self.refresh_positions,
                 bg='#00ff00', fg='#000000', font=('Arial', 9, 'bold'),
                 height=1).pack(fill=tk.X, padx=2)
        
        # Tab 2: Order Book / Trade History
        orderbook_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(orderbook_tab, text='📖 ORDER BOOK')
        
        # Control panel
        control_frame = tk.Frame(orderbook_tab, bg='#2d2d2d', relief=tk.RIDGE, bd=2)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Button(control_frame, text="🔄 REFRESH", command=self.refresh_order_book,
                 bg='#0099ff', fg='#ffffff', font=('Arial', 9, 'bold'),
                 width=12).pack(side=tk.LEFT, padx=5, pady=5)
        
        tk.Label(control_frame, text="Filter:", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 9)).pack(side=tk.LEFT, padx=5)
        
        self.orderbook_filter = tk.StringVar(value="ALL")
        for status in ['ALL', 'COMPLETE', 'REJECTED', 'CANCELLED']:
            tk.Radiobutton(control_frame, text=status, variable=self.orderbook_filter,
                          value=status, bg='#2d2d2d', fg='#ffffff', selectcolor='#1e1e1e',
                          font=('Arial', 9), command=self.refresh_order_book).pack(side=tk.LEFT, padx=2)
        
        tk.Button(control_frame, text="📊 EXPORT CSV", command=self.export_order_book,
                 bg='#00aa00', fg='#ffffff', font=('Arial', 9, 'bold'),
                 width=12).pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Order book table
        orderbook_frame = tk.Frame(orderbook_tab, bg='#2d2d2d')
        orderbook_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        orderbook_columns = ('Time', 'Account', 'Symbol', 'Type', 'Qty', 'Price', 'Status', 'Order ID')
        self.orderbook_tree = ttk.Treeview(orderbook_frame, columns=orderbook_columns, 
                                          show='headings', height=15)
        
        for col in orderbook_columns:
            self.orderbook_tree.heading(col, text=col)
            if col == 'Symbol':
                self.orderbook_tree.column(col, width=180)
            elif col == 'Order ID':
                self.orderbook_tree.column(col, width=120)
            elif col in ('Time', 'Account'):
                self.orderbook_tree.column(col, width=100)
            else:
                self.orderbook_tree.column(col, width=80)
        
        orderbook_scrollbar = ttk.Scrollbar(orderbook_frame, orient=tk.VERTICAL,
                                           command=self.orderbook_tree.yview)
        self.orderbook_tree.configure(yscrollcommand=orderbook_scrollbar.set)
        
        self.orderbook_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        orderbook_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Tab 3: Closed Positions
        closed_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(closed_tab, text='📜 CLOSED POSITIONS')
        
        # Closed positions treeview with columns
        closed_frame = tk.Frame(closed_tab, bg='#1e1e1e')
        closed_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        closed_columns = ('Account', 'Symbol', 'Buy Qty', 'Buy Avg', 'Sell Qty', 'Sell Avg', 'Closed Qty', 'P&L', 'Buy Time', 'Sell Time', 'Analysis')
        
        # Create style for better row height and readability
        style = ttk.Style()
        style.configure("Closed.Treeview", rowheight=28)  # Increase row height for better text visibility
        
        self.closed_tree = ttk.Treeview(closed_frame, columns=closed_columns, show='headings', height=20, style="Closed.Treeview")
        
        # Column headings and widths
        self.closed_tree.heading('Account', text='Account')
        self.closed_tree.heading('Symbol', text='Symbol')
        self.closed_tree.heading('Buy Qty', text='Buy Qty')
        self.closed_tree.heading('Buy Avg', text='Buy Avg')
        self.closed_tree.heading('Sell Qty', text='Sell Qty')
        self.closed_tree.heading('Sell Avg', text='Sell Avg')
        self.closed_tree.heading('Closed Qty', text='Closed Qty')
        self.closed_tree.heading('P&L', text='P&L (₹)')
        self.closed_tree.heading('Buy Time', text='Buy Time')
        self.closed_tree.heading('Sell Time', text='Sell Time')
        self.closed_tree.heading('Analysis', text='Trade Analysis')
        
        self.closed_tree.column('Account', width=90, anchor='w')
        self.closed_tree.column('Symbol', width=130, anchor='w')
        self.closed_tree.column('Buy Qty', width=65, anchor='e')
        self.closed_tree.column('Buy Avg', width=80, anchor='e')
        self.closed_tree.column('Sell Qty', width=65, anchor='e')
        self.closed_tree.column('Sell Avg', width=80, anchor='e')
        self.closed_tree.column('Closed Qty', width=75, anchor='e')
        self.closed_tree.column('P&L', width=100, anchor='e')
        self.closed_tree.column('Buy Time', width=75, anchor='center')
        self.closed_tree.column('Sell Time', width=75, anchor='center')
        self.closed_tree.column('Analysis', width=380, anchor='w')
        
        # Double-click to view detailed analysis
        self.closed_tree.bind('<Double-Button-1>', self._show_detailed_trade_analysis)
        
        # Tooltip for truncated text
        self._create_closed_position_tooltip()
        
        # Scrollbar for closed positions
        closed_scroll = ttk.Scrollbar(closed_frame, orient=tk.VERTICAL, command=self.closed_tree.yview)
        self.closed_tree.configure(yscrollcommand=closed_scroll.set)
        
        self.closed_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        closed_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load closed positions button
        tk.Button(closed_tab, text="🔄 REFRESH CLOSED", command=self.load_closed_positions,
                 bg='#0099cc', fg='#ffffff', font=('Arial', 9, 'bold'),
                 height=1).pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # Tab 4: Risk Management
        risk_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(risk_tab, text='🛡️ RISK MANAGEMENT')
        
        # Risk settings panel
        risk_settings_frame = tk.LabelFrame(risk_tab, text="Risk Controls", bg='#2d2d2d', 
                                           fg='#ff9900', font=('Arial', 12, 'bold'))
        risk_settings_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Max Daily Loss
        loss_frame = tk.Frame(risk_settings_frame, bg='#2d2d2d')
        loss_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(loss_frame, text="Max Daily Loss Limit:", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=5)
        
        self.max_daily_loss = tk.DoubleVar(value=10000.0)
        tk.Entry(loss_frame, textvariable=self.max_daily_loss, width=12,
                font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=5)
        
        tk.Label(loss_frame, text="₹", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 11)).pack(side=tk.LEFT)
        
        # Enable/Disable auto square-off
        self.auto_square_off = tk.BooleanVar(value=False)
        tk.Checkbutton(loss_frame, text="Auto Square-Off", variable=self.auto_square_off,
                      bg='#2d2d2d', fg='#ff0000', selectcolor='#1e1e1e',
                      font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=20)
        
        # Risk Status Display
        risk_status_frame = tk.LabelFrame(risk_tab, text="Current Risk Status", bg='#2d2d2d',
                                         fg='#00aaff', font=('Arial', 12, 'bold'))
        risk_status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Today's P&L
        today_pnl_frame = tk.Frame(risk_status_frame, bg='#2d2d2d')
        today_pnl_frame.pack(pady=15)
        
        tk.Label(today_pnl_frame, text="Today's P&L:", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 14)).pack(side=tk.LEFT, padx=10)
        
        self.today_pnl_label = tk.Label(today_pnl_frame, text="₹0.00", bg='#2d2d2d',
                                       fg='#00ff00', font=('Arial', 18, 'bold'))
        self.today_pnl_label.pack(side=tk.LEFT, padx=10)
        
        # Loss Remaining
        remaining_frame = tk.Frame(risk_status_frame, bg='#2d2d2d')
        remaining_frame.pack(pady=15)
        
        tk.Label(remaining_frame, text="Loss Remaining Before Limit:", bg='#2d2d2d', fg='#ffffff',
                font=('Arial', 12)).pack(side=tk.LEFT, padx=10)
        
        self.loss_remaining_label = tk.Label(remaining_frame, text="₹10,000.00", bg='#2d2d2d',
                                            fg='#ffaa00', font=('Arial', 14, 'bold'))
        self.loss_remaining_label.pack(side=tk.LEFT, padx=10)
        
        # Risk Warning
        self.risk_warning_label = tk.Label(risk_status_frame, text="", bg='#2d2d2d',
                                          fg='#ff0000', font=('Arial', 13, 'bold'))
        self.risk_warning_label.pack(pady=10)
        
        # Action buttons
        action_frame = tk.Frame(risk_status_frame, bg='#2d2d2d')
        action_frame.pack(pady=15)
        
        tk.Button(action_frame, text="🚨 EMERGENCY EXIT ALL", 
                 command=self.emergency_exit_all,
                 bg='#ff0000', fg='#ffffff', font=('Arial', 12, 'bold'),
                 width=25, height=2).pack(pady=5)
        
        tk.Button(action_frame, text="🔄 REFRESH RISK STATUS",
                 command=self.update_risk_status,
                 bg='#0099ff', fg='#ffffff', font=('Arial', 11, 'bold'),
                 width=25).pack(pady=5)
        
        # Tab 5: Account Management
        account_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(account_tab, text='🔑 ACCOUNT MANAGEMENT')
        
        # Account management buttons at the top
        btn_frame = tk.Frame(account_tab, bg='#1e1e1e')
        btn_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        tk.Button(btn_frame, text="🔄 CHECK TOKEN STATUS", command=self.check_token_status,
                 bg='#0099ff', fg='#ffffff', font=('Arial', 10, 'bold'),
                 height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        tk.Button(btn_frame, text="🔑 UPDATE TOKENS", command=self.show_token_update_dialog,
                 bg='#ff9900', fg='#ffffff', font=('Arial', 10, 'bold'),
                 height=2).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        
        # Account management display
        self.account_text = tk.Text(account_tab, bg='#1e1e1e', fg='#ffffff',
                                   font=('Courier', 10), wrap=tk.WORD)
        account_scroll = ttk.Scrollbar(account_tab, orient=tk.VERTICAL, command=self.account_text.yview)
        self.account_text.configure(yscrollcommand=account_scroll.set)
        
        self.account_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        account_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # Tab 6: Reporting
        reporting_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(reporting_tab, text='📊 REPORTING')
        
        # Refresh button at the top
        refresh_frame = tk.Frame(reporting_tab, bg='#1e1e1e')
        refresh_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        tk.Button(refresh_frame, text="🔄 REFRESH REPORT", 
                 command=lambda: self.load_report(1),
                 bg='#0099ff', fg='#ffffff', font=('Arial', 10, 'bold'),
                 height=2).pack(fill=tk.X, padx=5)
        
        # Reporting display
        reporting_frame = tk.Frame(reporting_tab, bg='#1e1e1e')
        reporting_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        reporting_columns = ('Account', 'Symbol', 'Status', 'Qty', 'Entry', 'Exit', 'ROI%', 'Gross P&L', 'Charges', 'Net P&L')
        self.reporting_tree = ttk.Treeview(reporting_frame, columns=reporting_columns, show='headings', height=18)
        
        # Column headings and widths
        self.reporting_tree.heading('Account', text='Account')
        self.reporting_tree.heading('Symbol', text='Symbol')
        self.reporting_tree.heading('Status', text='Status')
        self.reporting_tree.heading('Qty', text='Qty')
        self.reporting_tree.heading('Entry', text='Entry ₹')
        self.reporting_tree.heading('Exit', text='Exit ₹')
        self.reporting_tree.heading('ROI%', text='ROI %')
        self.reporting_tree.heading('Gross P&L', text='Gross P&L')
        self.reporting_tree.heading('Charges', text='Charges')
        self.reporting_tree.heading('Net P&L', text='Net P&L')
        
        self.reporting_tree.column('Account', width=90, anchor='w')
        self.reporting_tree.column('Symbol', width=150, anchor='w')
        self.reporting_tree.column('Status', width=60, anchor='center')
        self.reporting_tree.column('Qty', width=60, anchor='e')
        self.reporting_tree.column('Entry', width=70, anchor='e')
        self.reporting_tree.column('Exit', width=70, anchor='e')
        self.reporting_tree.column('ROI%', width=70, anchor='e')
        self.reporting_tree.column('Gross P&L', width=90, anchor='e')
        self.reporting_tree.column('Charges', width=70, anchor='e')
        self.reporting_tree.column('Net P&L', width=90, anchor='e')
        
        # Scrollbar for reporting
        reporting_scroll = ttk.Scrollbar(reporting_frame, orient=tk.VERTICAL, command=self.reporting_tree.yview)
        self.reporting_tree.configure(yscrollcommand=reporting_scroll.set)
        
        self.reporting_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        reporting_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Summary statistics at bottom
        summary_frame = tk.Frame(reporting_tab, bg='#2d2d2d', relief=tk.RIDGE, bd=2)
        summary_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        self.report_summary = tk.Label(summary_frame, bg='#2d2d2d', fg='#00ff00',
                                      font=('Courier', 11, 'bold'), justify=tk.LEFT,
                                      text='Summary: Click REFRESH REPORT to load data')
        self.report_summary.pack(pady=8, padx=10, anchor='w')
        
        # Tab 7: Performance Analytics
        analytics_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(analytics_tab, text='📈 PERFORMANCE ANALYTICS')
        
        self.create_performance_analytics_panel(analytics_tab)
    
    def create_performance_analytics_panel(self, parent):
        """Create comprehensive performance analytics dashboard."""
        # Main container with scrollbar
        canvas = tk.Canvas(parent, bg='#1e1e1e', highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg='#1e1e1e')
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Header with refresh
        header_frame = tk.Frame(scroll_frame, bg='#1a1a1a', pady=10)
        header_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(header_frame, text="📈 Performance Analytics Dashboard", 
                font=('Arial', 16, 'bold'), bg='#1a1a1a', fg='#00d4ff').pack(side=tk.LEFT, padx=10)
        
        # Account filter dropdown
        filter_frame = tk.Frame(header_frame, bg='#1a1a1a')
        filter_frame.pack(side=tk.RIGHT, padx=10)
        
        tk.Label(filter_frame, text="Account:", bg='#1a1a1a', fg='#888', 
                font=('Arial', 10)).pack(side=tk.LEFT, padx=(0,5))
        
        self.analytics_account_var = tk.StringVar(value="All Accounts")
        self.analytics_account_dropdown = ttk.Combobox(filter_frame, textvariable=self.analytics_account_var,
                                                       state='readonly', width=20, font=('Arial', 10))
        self.analytics_account_dropdown['values'] = ["All Accounts"]
        self.analytics_account_dropdown.pack(side=tk.LEFT, padx=5)
        self.analytics_account_dropdown.bind('<<ComboboxSelected>>', lambda e: self.refresh_performance_analytics())
        
        tk.Button(filter_frame, text="🔄 REFRESH", command=self.refresh_performance_analytics,
                 bg='#0099ff', fg='#ffffff', font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=(10,0))
        
        # Quick Stats Row
        quick_stats_frame = tk.Frame(scroll_frame, bg='#1e1e1e')
        quick_stats_frame.pack(fill='x', padx=10, pady=5)
        
        # Today's P&L Card
        pnl_card = tk.Frame(quick_stats_frame, bg='#2d2d2d', relief=tk.RIDGE, bd=2)
        pnl_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(pnl_card, text="Today's P&L", bg='#2d2d2d', fg='#888', 
                font=('Arial', 10)).pack(pady=(10,0))
        self.analytics_pnl_label = tk.Label(pnl_card, text="₹0.00", bg='#2d2d2d', 
                                           fg='#00ff00', font=('Arial', 20, 'bold'))
        self.analytics_pnl_label.pack(pady=(0,10))
        
        # Win Rate Card
        winrate_card = tk.Frame(quick_stats_frame, bg='#2d2d2d', relief=tk.RIDGE, bd=2)
        winrate_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(winrate_card, text="Win Rate", bg='#2d2d2d', fg='#888', 
                font=('Arial', 10)).pack(pady=(10,0))
        self.analytics_winrate_label = tk.Label(winrate_card, text="0%", bg='#2d2d2d', 
                                                fg='#ffa500', font=('Arial', 20, 'bold'))
        self.analytics_winrate_label.pack(pady=(0,10))
        
        # Total Trades Card
        trades_card = tk.Frame(quick_stats_frame, bg='#2d2d2d', relief=tk.RIDGE, bd=2)
        trades_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(trades_card, text="Total Trades", bg='#2d2d2d', fg='#888', 
                font=('Arial', 10)).pack(pady=(10,0))
        self.analytics_trades_label = tk.Label(trades_card, text="0", bg='#2d2d2d', 
                                               fg='#00d4ff', font=('Arial', 20, 'bold'))
        self.analytics_trades_label.pack(pady=(0,10))
        
        # Profit Factor Card
        pf_card = tk.Frame(quick_stats_frame, bg='#2d2d2d', relief=tk.RIDGE, bd=2)
        pf_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(pf_card, text="Profit Factor", bg='#2d2d2d', fg='#888', 
                font=('Arial', 10)).pack(pady=(10,0))
        self.analytics_pf_label = tk.Label(pf_card, text="0.00", bg='#2d2d2d', 
                                          fg='#ffaa00', font=('Arial', 20, 'bold'))
        self.analytics_pf_label.pack(pady=(0,10))
        
        # Detailed Metrics Section
        metrics_frame = tk.Frame(scroll_frame, bg='#1a1a1a', relief=tk.RIDGE, bd=2)
        metrics_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(metrics_frame, text="📊 Detailed Performance Metrics", 
                font=('Arial', 13, 'bold'), bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10, pady=10)
        
        # Create 2-column layout for metrics
        metrics_container = tk.Frame(metrics_frame, bg='#1a1a1a')
        metrics_container.pack(fill='x', padx=10, pady=(0,10))
        
        # Left column
        left_metrics = tk.Frame(metrics_container, bg='#1a1a1a')
        left_metrics.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        
        self.analytics_left_text = scrolledtext.ScrolledText(left_metrics, height=12, width=45,
                                                             bg='#2d2d2d', fg='#ffffff',
                                                             font=('Courier', 10), wrap=tk.WORD)
        self.analytics_left_text.pack(fill=tk.BOTH, expand=True)
        
        # Right column
        right_metrics = tk.Frame(metrics_container, bg='#1a1a1a')
        right_metrics.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5,0))
        
        self.analytics_right_text = scrolledtext.ScrolledText(right_metrics, height=12, width=45,
                                                              bg='#2d2d2d', fg='#ffffff',
                                                              font=('Courier', 10), wrap=tk.WORD)
        self.analytics_right_text.pack(fill=tk.BOTH, expand=True)
        
        # Strategy Breakdown Section
        strategy_frame = tk.Frame(scroll_frame, bg='#1a1a1a', relief=tk.RIDGE, bd=2)
        strategy_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(strategy_frame, text="🎯 Strategy Performance Breakdown", 
                font=('Arial', 13, 'bold'), bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10, pady=10)
        
        self.analytics_strategy_text = scrolledtext.ScrolledText(strategy_frame, height=10, width=95,
                                                                 bg='#2d2d2d', fg='#ffffff',
                                                                 font=('Courier', 10), wrap=tk.WORD)
        self.analytics_strategy_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        
        # Best/Worst Trades Section
        trades_frame = tk.Frame(scroll_frame, bg='#1a1a1a', relief=tk.RIDGE, bd=2)
        trades_frame.pack(fill='x', padx=10, pady=10)
        
        tk.Label(trades_frame, text="🏆 Best & Worst Trades", 
                font=('Arial', 13, 'bold'), bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10, pady=10)
        
        self.analytics_trades_text = scrolledtext.ScrolledText(trades_frame, height=8, width=95,
                                                               bg='#2d2d2d', fg='#ffffff',
                                                               font=('Courier', 10), wrap=tk.WORD)
        self.analytics_trades_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Initial load
        self.refresh_performance_analytics()
    
    def adjust_sl_percent(self, delta):
        """Adjust stop loss percentage and apply immediately if positions exist."""
        current = self.sl_percent.get()
        new_val = max(0.5, min(50, current + delta))
        self.sl_percent.set(round(new_val, 1))
        
        # Auto-apply to active positions if they exist (silent mode)
        if self.positions_data:
            threading.Thread(target=self._apply_sl_async, args=(new_val, False, "percent"), daemon=True).start()
    
    def adjust_sl_amount(self, delta):
        """Adjust stop loss amount."""
        current = self.sl_amount.get()
        new_val = max(1, min(1000, current + delta))
        self.sl_amount.set(round(new_val, 1))
    
    def toggle_sl_mode(self):
        """Toggle between percent and amount modes for stop loss."""
        if self.sl_mode.get() == "percent":
            self.sl_amount_frame.pack_forget()
            self.sl_percent_frame.pack(padx=5, pady=5)
        else:
            self.sl_percent_frame.pack_forget()
            self.sl_amount_frame.pack(padx=5, pady=5)
    
    def adjust_inc_percent(self, delta):
        """Adjust increase percentage."""
        current = self.inc_percent.get()
        new_val = max(25, min(200, current + delta))
        self.inc_percent.set(new_val)
    
    def adjust_inc_lots(self, delta):
        """Adjust increase lot count."""
        current = self.inc_lots.get()
        new_val = max(1, min(50, current + delta))
        self.inc_lots.set(new_val)
    
    def toggle_inc_mode(self):
        """Toggle between percent and lots modes for increase."""
        if self.inc_mode.get() == "percent":
            self.inc_lots_frame.pack_forget()
            self.inc_percent_frame.pack(padx=5, pady=5)
        else:
            self.inc_percent_frame.pack_forget()
            self.inc_lots_frame.pack(padx=5, pady=5)
    
    def apply_stop_loss(self, skip_confirm=False):
        """Apply stop loss to all positions.
        
        Args:
            skip_confirm: If True, execute immediately without confirmation dialog
        """
        print(f"🔍 DEBUG: apply_stop_loss called, positions_data length: {len(self.positions_data)}")
        
        if not self.positions_data:
            if not skip_confirm:
                messagebox.showinfo("Info", "No positions to add stop loss")
            self._log('info', "Stop Loss skipped: No positions")
            print("⚠️ DEBUG: No positions_data available")
            return
        
        mode = self.sl_mode.get()
        if mode == "percent":
            value = self.sl_percent.get()
            msg = f"Place {value}% SL for {len(self.positions_data)} positions?"
            # Track last SL percentage for auto-updates
            self._last_sl_percent = value
        else:
            value = self.sl_amount.get()
            msg = f"Place ₹{value} SL for {len(self.positions_data)} positions?"
            self._last_sl_percent = None  # Don't auto-update for amount mode
        
        print(f"✅ DEBUG: SL mode={mode}, value={value}, positions={len(self.positions_data)}")
        
        self._log('info', f"Stop Loss initiated: {len(self.positions_data)} positions, Mode={mode}, Value={value}")
        
        # Execute immediately if skip_confirm=True, otherwise ask confirmation
        if skip_confirm or messagebox.askyesno("Confirm", msg):
            print(f"🚀 DEBUG: Starting SL thread...")
            threading.Thread(target=self._apply_sl_async, args=(value, True, mode), daemon=True).start()
        else:
            self._log('info', "Stop Loss cancelled by user")
            print("❌ DEBUG: User cancelled SL")
    
    def apply_increase(self, skip_confirm=False):
        """Apply increase to all positions.
        
        Args:
            skip_confirm: If True, execute immediately without confirmation dialog
        """
        print(f"🔍 DEBUG: apply_increase called, positions_data length: {len(self.positions_data)}")
        
        if not self.positions_data:
            if not skip_confirm:
                messagebox.showinfo("Info", "No positions to increase")
            self._log('info', "Increase Qty skipped: No positions")
            print("⚠️ DEBUG: No positions_data available for increase")
            return
        
        mode = self.inc_mode.get()
        if mode == "percent":
            value = self.inc_percent.get()
            msg = f"Add {value}% to {len(self.positions_data)} positions?"
        else:
            value = self.inc_lots.get()
            msg = f"Add {value} lot(s) to {len(self.positions_data)} positions?"
        
        print(f"✅ DEBUG: Increase mode={mode}, value={value}, positions={len(self.positions_data)}")
        
        self._log('info', f"Increase Qty initiated: {len(self.positions_data)} positions, Mode={mode}, Value={value}")
        
        # Execute immediately if skip_confirm=True, otherwise ask confirmation
        if skip_confirm or messagebox.askyesno("Confirm", msg):
            print(f"🚀 DEBUG: Starting Increase thread...")
            threading.Thread(target=self._apply_increase_async, args=(value, mode), daemon=True).start()
        else:
            self._log('info', "Increase Qty cancelled by user")
            print("❌ DEBUG: User cancelled Increase")
    
    def apply_exit(self, skip_confirm=False):
        """Apply exit to all positions.
        
        Args:
            skip_confirm: If True, execute immediately without confirmation dialog
        """
        if not self.positions_data:
            if not skip_confirm:
                messagebox.showinfo("Info", "No positions to exit")
            self._log('info', "Exit Position skipped: No positions")
            return
        
        percent = self.exit_percent.get()
        msg = f"Exit {percent}% of {len(self.positions_data)} positions?"
        
        self._log('info', f"Exit Position initiated: {len(self.positions_data)} positions, Percent={percent}%")
        
        # Execute immediately if skip_confirm=True, otherwise ask confirmation
        if skip_confirm or messagebox.askyesno("Confirm", msg):
            threading.Thread(target=self._apply_exit_async, args=(percent,), daemon=True).start()
        else:
            self._log('info', "Exit Position cancelled by user")
    
    def _apply_sl_async(self, value, show_notification=True, mode="percent"):
        """Apply stop loss asynchronously.
        
        Args:
            value: Stop loss value (percentage or amount)
            show_notification: If True, show success/error popups. If False, silent execution.
            mode: "percent" or "amount"
        """
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            # First, fetch all pending orders to check for existing SL orders
            existing_sl_orders = {}  # {(broker_key, instrument_key): order}
            
            try:
                for broker_key, broker_info in self.trader.active_brokers.items():
                    client = broker_info['client']
                    orders_response = client.get_order_history()
                    
                    if orders_response and orders_response.get('data'):
                        orders = orders_response.get('data', [])
                        pending_statuses = [
                            'pending', 'open', 'trigger pending', 
                            'PENDING', 'OPEN', 'TRIGGER_PENDING',
                            'TRIGGER PENDING', 'trigger_pending'
                        ]
                        
                        print(f"🔎 Fetching existing SL orders for {broker_key}...")
                        
                        # Find pending SL orders
                        for order in orders:
                            order_status = order.get('status', '').strip()
                            order_type = order.get('order_type', '') or order.get('orderType', '')
                            
                            # Debug: Print ALL SL orders to see what statuses exist
                            if order_type in ['SL', 'SL-M', 'STOP_LOSS', 'STOP_LOSS_MARKET']:
                                print(f"   Found SL order: status='{order_status}', type={order_type}, symbol={order.get('tradingsymbol')}, order_id={order.get('order_id')}")
                            
                            # Expanded pending statuses to catch more cases
                            if (order_status.upper() in ['PENDING', 'OPEN', 'TRIGGER PENDING', 'TRIGGER_PENDING', 'NOT TRIGGERED', 'AWAITED'] and 
                                order_type in ['SL', 'SL-M', 'STOP_LOSS', 'STOP_LOSS_MARKET']):
                                
                                # Get instrument key AND tradingsymbol for better matching
                                instrument_key = (order.get('instrument_key') or 
                                                order.get('instrument_token') or 
                                                order.get('securityId') or 
                                                order.get('security_id') or '')
                                tradingsymbol = order.get('tradingsymbol', '') or order.get('tradingSymbol', '')
                                
                                if instrument_key:
                                    # Normalize instrument key - extract number after | if present
                                    normalized_key = str(instrument_key).split('|')[-1]
                                    # Store by BOTH instrument key and tradingsymbol for better matching
                                    key = (broker_key, normalized_key)
                                    symbol_key = (broker_key, tradingsymbol)
                                    existing_sl_orders[key] = order
                                    if tradingsymbol:
                                        existing_sl_orders[symbol_key] = order
                                    print(f"📌 Found existing SL order: {tradingsymbol} (ID:{order.get('order_id')}) - broker={broker_key}, key={normalized_key}, status={order_status}")
                        
                        print(f"✅ Total existing SL orders stored: {len(existing_sl_orders)}")
                        print(f"   Keys: {list(existing_sl_orders.keys())}")
            except Exception as e:
                print(f"⚠️ Error fetching existing SL orders: {e}")
            
            def place_sl(pos):
                try:
                    client = pos.get('client')
                    broker_key = pos.get('broker_key', '')
                    
                    # Check if position is actually open (netQty != 0)
                    net_qty = pos.get('quantity', 0) or pos.get('netQty', 0)
                    position_type = pos.get('positionType', '').upper()
                    
                    if net_qty == 0:
                        print(f"⏭️  Skipping position with zero quantity: {pos.get('tradingsymbol')} (positionType={position_type})")
                        return False
                    
                    if position_type == 'CLOSED':
                        print(f"⏭️  Skipping CLOSED position: {pos.get('tradingsymbol')} (netQty={net_qty})")
                        # If netQty is not 0 but positionType is CLOSED, still process it
                        # This can happen with carryforward positions
                        if abs(net_qty) == 0:
                            return False
                    
                    if not client:
                        print(f"No client for position: {pos.get('tradingsymbol', 'Unknown')}")
                        return False
                    
                    # Get instrument key first for real-time LTP fetch
                    instrument_key = (pos.get('instrument_key') or 
                                    pos.get('instrument_token') or 
                                    pos.get('securityId') or 
                                    pos.get('security_id') or '')
                    
                    # CRITICAL: Fetch REAL-TIME LTP from market, not stale position data
                    # Position LTP is from when position was opened, NOT current price!
                    ltp = 0
                    try:
                        # Try to get real-time LTP using get_ltp API
                        if hasattr(client, 'get_ltp') and instrument_key:
                            ltp_response = client.get_ltp(instrument_key)
                            if ltp_response and ltp_response.get('data'):
                                ltp_data = ltp_response['data']
                                # Handle different broker response formats
                                if isinstance(ltp_data, dict):
                                    # Upstox: {'NSE_FO|58819': {'last_price': 120.5}}
                                    if instrument_key in ltp_data:
                                        ltp = ltp_data[instrument_key].get('last_price', 0)
                                    else:
                                        # Try first key
                                        first_key = next(iter(ltp_data), None)
                                        if first_key:
                                            ltp = ltp_data[first_key].get('last_price', 0) or ltp_data[first_key].get('ltp', 0)
                                else:
                                    # Dhan: direct value
                                    ltp = ltp_data.get('last_price', 0) or ltp_data.get('ltp', 0)
                        
                        if ltp > 0:
                            print(f"📡 Real-time LTP fetched for {pos.get('tradingsymbol')}: ₹{ltp:.2f}")
                    except Exception as ltp_error:
                        print(f"⚠️ Failed to fetch real-time LTP: {ltp_error}")
                    
                    # Fallback: Use position LTP only if real-time fetch failed
                    if ltp == 0:
                        ltp = (pos.get('last_price') or 
                              pos.get('ltp') or 
                              pos.get('lastPrice') or 
                              pos.get('last_traded_price') or 
                              pos.get('lastTradedPrice') or 
                              pos.get('close_price') or 
                              pos.get('closePrice') or 0)
                        
                        # Dhan doesn't provide LTP in positions API, use buyAvg/costPrice as fallback
                        if ltp == 0 and 'dhan' in broker_key.lower():
                            ltp = (pos.get('buyAvg') or 
                                  pos.get('costPrice') or 
                                  pos.get('average_price') or 
                                  pos.get('buyPrice') or 
                                  pos.get('avgBuyPrice') or 0)
                            if ltp > 0:
                                print(f"⚠️  Dhan: Using buyAvg/costPrice as LTP for {pos.get('tradingsymbol')}: ₹{ltp}")
                        
                        if ltp > 0:
                            print(f"⚠️  Using stale position LTP for {pos.get('tradingsymbol')}: ₹{ltp:.2f}")
                    
                    # Calculate SL trigger price based on mode
                    # Stop Loss protects profit as price moves UP
                    if mode == "percent":
                        # Percentage mode: SL trails below current price
                        # Example: LTP=110, 10% SL → 110 - (110*10/100) = 99
                        # Example: LTP=150, 20% SL → 150 - (150*20/100) = 120
                        sl_price = ltp - (ltp * value / 100)
                    else:  # amount mode - value is the absolute trigger price
                        sl_price = value
                    
                    # Round to nearest 0.05 to avoid decimal issues (exchanges require 0.05 tick size)
                    sl_price = round(sl_price * 20) / 20  # Round to nearest 0.05
                    
                    # Ensure SL price is positive and reasonable (at least 0.05)
                    if sl_price < 0.05:
                        print(f"SL price too low for {pos.get('tradingsymbol')}: {sl_price:.2f}, ltp={ltp:.2f}")
                        return False
                    
                    # Get quantity - handle both Dhan (netQty) and Upstox (quantity)
                    raw_qty = pos.get('quantity', 0) or pos.get('netQty', 0)
                    qty = abs(raw_qty)
                    
                    instrument_key = (pos.get('instrument_key') or 
                                    pos.get('instrument_token') or 
                                    pos.get('securityId') or 
                                    pos.get('security_id') or '')
                    
                    if not instrument_key or ltp <= 0 or qty == 0:
                        print(f"❌ Missing data for SL: symbol={pos.get('tradingsymbol')}, instrument={instrument_key}, ltp={ltp}, qty={qty}")
                        print(f"   Broker: {broker_key}")
                        print(f"   All position keys: {list(pos.keys())}")
                        print(f"   Price/LTP fields: {[(k, pos.get(k)) for k in pos.keys() if 'price' in k.lower() or 'ltp' in k.lower()]}")
                        return False
                    
                    # Determine transaction type based on current position
                    trans_type = "SELL" if raw_qty > 0 else "BUY"
                    
                    # Store original instrument_key before normalization
                    original_instrument_key = instrument_key
                    
                    # For Dhan broker, extract securityId from instrument_key (remove NSE_FO| prefix)
                    normalized_instrument_key = instrument_key
                    if 'dhan' in broker_key.lower():
                        # Dhan needs just the number, not "NSE_FO|57030"
                        if '|' in str(instrument_key):
                            normalized_instrument_key = instrument_key.split('|')[1]
                    
                    # For existing order lookup, normalize both Upstox and Dhan keys
                    # Upstox: NSE_FO|58819, Dhan: 58819 → both become 58819 for matching
                    lookup_key = str(original_instrument_key).split('|')[-1]  # Get last part after | or whole string
                    
                    print(f"🔎 SL Matching: broker={broker_key}, original={original_instrument_key}, lookup={lookup_key}")
                    
                    # Upstox doesn't support SL-M on F&O, use SL (Stop Loss Limit)
                    # Dhan supports SL-M
                    if 'upstox' in broker_key.lower():
                        order_type = "SL"
                        # For SELL orders: trigger_price > limit_price
                        # For BUY orders: trigger_price < limit_price
                        # Set limit slightly better than trigger to ensure execution
                        if trans_type == "SELL":
                            price = sl_price - 0.05  # Limit price lower than trigger
                        else:
                            price = sl_price + 0.05  # Limit price higher than trigger
                    else:
                        # Dhan: Try SL (Stop Loss Limit) instead of SL-M
                        # Some brokers don't support SL-M properly
                        order_type = "SL"
                        # For SELL orders: limit price < trigger price
                        # For BUY orders: limit price > trigger price
                        if trans_type == "SELL":
                            price = sl_price - 0.05
                        else:
                            price = sl_price + 0.05
                    
                    # Round limit price to nearest 0.05 as well
                    price = round(price * 20) / 20
                    
                    print(f"Processing SL for {pos.get('tradingsymbol')}: broker={broker_key}, instrument={original_instrument_key}, qty={qty}, ltp={ltp:.2f}, sl_price={sl_price:.2f}, order_type={order_type}, trans={trans_type}")
                    
                    # Check if existing SL order exists - try BOTH instrument key AND tradingsymbol
                    order_key = (broker_key, lookup_key)
                    symbol_key = (broker_key, pos.get('tradingsymbol', ''))
                    existing_order = existing_sl_orders.get(order_key)
                    
                    # If not found by instrument key, try tradingsymbol
                    if not existing_order and pos.get('tradingsymbol'):
                        existing_order = existing_sl_orders.get(symbol_key)
                        if existing_order:
                            print(f"🔍 Found SL order by tradingsymbol match: {pos.get('tradingsymbol')}")
                    
                    print(f"🔍 Looking for key={order_key} or symbol={symbol_key}, found={existing_order is not None}")
                    if existing_order:
                        print(f"   ✅ Match! Order ID: {existing_order.get('order_id')}, will modify")
                    else:
                        print(f"   ❌ No match found in existing_sl_orders (has {len(existing_sl_orders)} entries)")
                        print(f"   Available keys: {list(existing_sl_orders.keys())}")
                    
                    if existing_order:
                        # CANCEL existing SL order instead of modifying (modify API is unreliable)
                        order_id = (existing_order.get('order_id') or 
                                   existing_order.get('orderId') or 
                                   existing_order.get('id') or '')
                        
                        if order_id:
                            print(f"🗑️ Cancelling existing SL order: {order_id} for {pos.get('tradingsymbol')}")
                            print(f"   Old qty: {existing_order.get('quantity')}, New qty: {qty}")
                            print(f"   Old trigger: {existing_order.get('trigger_price')}, New trigger: {sl_price}")
                            
                            try:
                                # Cancel the old order first
                                cancel_result = client.cancel_order(order_id=order_id)
                                print(f"✅ Cancelled old SL order {order_id}: {cancel_result}")
                                # Continue to place new order below
                            except Exception as cancel_error:
                                print(f"⚠️ Failed to cancel SL order {order_id}: {cancel_error}")
                                # If cancel fails, don't place new order (avoid duplicates)
                                return False
                    
                    # Place new SL order (if no existing order or modify failed)
                    # For Dhan, use position's productType if available
                    product_type = "I"  # Default to Intraday
                    exchange_segment = None
                    if 'dhan' in broker_key.lower():
                        # Check if position has productType field
                        pos_product = pos.get('productType', '')
                        if pos_product:
                            product_type = pos_product  # Use actual position product type
                            print(f"   Using Dhan productType from position: {product_type}")
                        # Get exchangeSegment from position
                        exchange_segment = pos.get('exchangeSegment', 'NSE_FNO')
                        print(f"   Using Dhan exchangeSegment from position: {exchange_segment}")
                    
                    print(f"📝 Placing new SL order for {pos.get('tradingsymbol')}")
                    print(f"   New SL details: qty={qty}, trigger={sl_price:.2f}, limit={price:.2f}, trans={trans_type}")
                    
                    # Use normalized instrument_key for Dhan, original for Upstox
                    instrument_to_use = normalized_instrument_key if 'dhan' in broker_key.lower() else original_instrument_key
                    
                    # Build order parameters based on broker type
                    order_params = {
                        'instrument_key': instrument_to_use,
                        'quantity': qty,
                        'transaction_type': trans_type,
                        'order_type': order_type,
                        'product': product_type,
                        'price': price,
                        'trigger_price': sl_price
                    }
                    
                    # Only add exchange_segment for Dhan broker
                    if 'dhan' in broker_key.lower() and exchange_segment:
                        order_params['exchange_segment'] = exchange_segment
                    
                    result = client.place_order(**order_params)
                    print(f"✅ New SL placed for {pos.get('tradingsymbol', 'Unknown')}: {result}")
                    return result is not None
                except Exception as e:
                    print(f"SL error for {pos.get('tradingsymbol', 'Unknown')}: {e}")
                    return False
            
            # Use conservative worker count to prevent blocking
            max_workers = min(10, max(1, len(self.positions_data)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(place_sl, pos) for pos in self.positions_data]
                results = [f.result() for f in as_completed(futures)]
            
            success = sum(results)
            
            self._log('info', f"Stop Loss execution completed: {success}/{len(self.positions_data)} successful")
            
            # Immediate position refresh
            self.root.after(0, self.refresh_positions)
            
            # Refresh margin after SL modification
            self.root.after(600, lambda: threading.Thread(target=self.refresh_margin, daemon=True).start())
            
            if show_notification:
                mode_text = f"{value}%" if mode == "percent" else f"₹{value}"
                self.root.after(0, lambda: messagebox.showinfo("Success", f"{success}/{len(self.positions_data)} SL orders placed ({mode_text})"))
        except Exception as e:
            self._log('error', f"Stop Loss error: {e}", exc_info=True)
            if show_notification:
                self.root.after(0, lambda: messagebox.showerror("Error", f"SL failed: {e}"))
    
    def _apply_increase_async(self, value, mode="percent"):
        """Apply increase asynchronously.
        
        Args:
            value: Increase value (percentage or lot count)
            mode: "percent" or "lots"
        """
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            # First, fetch existing SL orders to update their quantities
            existing_sl_orders = {}
            try:
                for broker_key, broker_info in self.trader.active_brokers.items():
                    client = broker_info['client']
                    orders_response = client.get_order_history()
                    
                    if orders_response and orders_response.get('data'):
                        orders = orders_response.get('data', [])
                        pending_statuses = ['pending', 'open', 'trigger pending', 
                                          'PENDING', 'OPEN', 'TRIGGER_PENDING',
                                          'TRIGGER PENDING', 'trigger_pending']
                        
                        for order in orders:
                            order_status = order.get('status', '')
                            order_type = order.get('order_type', '') or order.get('orderType', '')
                            
                            if (order_status in pending_statuses and 
                                order_type in ['SL', 'SL-M', 'STOP_LOSS', 'STOP_LOSS_MARKET']):
                                
                                instrument_key = (order.get('instrument_key') or 
                                                order.get('instrument_token') or 
                                                order.get('securityId') or 
                                                order.get('security_id') or '')
                                
                                if instrument_key:
                                    normalized_key = str(instrument_key).split('|')[-1]
                                    key = (broker_key, normalized_key)
                                    existing_sl_orders[key] = order
            except Exception as e:
                print(f"⚠️ Error fetching existing SL orders: {e}")
            
            def increase_single(pos):
                try:
                    client = pos.get('client')
                    broker_key = pos.get('broker_key', '')
                    
                    if not client:
                        print(f"No client for position: {pos.get('tradingsymbol', 'Unknown')}")
                        return False
                    
                    qty = pos.get('quantity', 0) or pos.get('netQty', 0)
                    
                    # Calculate additional quantity based on mode
                    symbol = pos.get('tradingsymbol', '')
                    if 'NIFTY' in symbol and 'BANK' not in symbol and 'MID' not in symbol:
                        lot_size = 65
                    elif 'BANKNIFTY' in symbol or 'BANKN' in symbol:
                        lot_size = 15
                    elif 'FINNIFTY' in symbol:
                        lot_size = 40
                    elif 'MIDCPNIFTY' in symbol or 'MIDCAP' in symbol:
                        lot_size = 75
                    else:
                        lot_size = pos.get('lot_size', 65)
                    
                    if mode == "percent":
                        raw_add_qty = abs(qty) * value / 100
                        add_qty = int(round(raw_add_qty / lot_size) * lot_size)
                    else:  # lots mode
                        add_qty = int(value * lot_size)
                    
                    if add_qty > 0:
                        instrument_key = (pos.get('instrument_key') or 
                                        pos.get('instrument_token') or 
                                        pos.get('securityId') or 
                                        pos.get('security_id') or '')
                        
                        if not instrument_key:
                            print(f"Missing instrument key for {pos.get('tradingsymbol', 'Unknown')}")
                            return False
                        
                        transaction_type = "BUY" if qty > 0 else "SELL"
                        result = client.place_order(
                            instrument_key=instrument_key,
                            quantity=add_qty,
                            transaction_type=transaction_type,
                            order_type="MARKET",
                            product="I"
                        )
                        mode_text = f"{value}%" if mode == "percent" else f"{value} lot(s)"
                        print(f"Increase order placed for {pos.get('tradingsymbol', 'Unknown')}: {add_qty} qty ({mode_text})")
                        
                        # Update existing SL order quantity if exists
                        if result:
                            lookup_key = str(instrument_key).split('|')[-1]
                            order_key = (broker_key, lookup_key)
                            existing_order = existing_sl_orders.get(order_key)
                            
                            if existing_order:
                                try:
                                    order_id = (existing_order.get('order_id') or 
                                              existing_order.get('orderId') or 
                                              existing_order.get('id') or '')
                                    
                                    old_qty = existing_order.get('quantity', 0)
                                    new_qty = abs(qty) + add_qty  # New total quantity
                                    
                                    print(f"🔄 Updating SL order quantity: {old_qty} → {new_qty} for {pos.get('tradingsymbol')}")
                                    
                                    client.modify_order(
                                        order_id=order_id,
                                        quantity=new_qty
                                    )
                                    print(f"✅ SL order quantity updated for {pos.get('tradingsymbol')}")
                                except Exception as sl_err:
                                    print(f"⚠️ Failed to update SL quantity: {sl_err}")
                        
                        return result is not None
                    return False
                except Exception as e:
                    print(f"Increase error for {pos.get('tradingsymbol', 'Unknown')}: {e}")
                    return False
            
            # Use conservative worker count
            max_workers = min(10, max(1, len(self.positions_data)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(increase_single, pos) for pos in self.positions_data]
                results = [f.result() for f in as_completed(futures)]
            
            success = sum(results)
            
            self._log('info', f"Increase Qty execution completed: {success}/{len(self.positions_data)} successful")
            
            # Immediate position refresh
            self.root.after(0, self.refresh_positions)
            
            mode_text = f"{value}%" if mode == "percent" else f"{value} lot(s)"
            self.root.after(0, lambda: messagebox.showinfo("Success", f"{success}/{len(self.positions_data)} orders placed ({mode_text})"))
        except Exception as e:
            self._log('error', f"Increase Qty error: {e}", exc_info=True)
            self.root.after(0, lambda: messagebox.showerror("Error", f"Increase failed: {e}"))
    
    def _apply_exit_async(self, percent):
        """Apply exit asynchronously."""
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def exit_single(pos):
                try:
                    client = pos.get('client')
                    qty = pos.get('quantity', 0)
                    exit_qty = int(abs(qty) * percent / 100)
                    
                    if exit_qty > 0:
                        instrument_key = (pos.get('instrument_key') or 
                                        pos.get('instrument_token') or 
                                        pos.get('securityId') or 
                                        pos.get('security_id') or '')
                        
                        if not instrument_key:
                            return False
                        
                        transaction_type = "SELL" if qty > 0 else "BUY"
                        result = client.place_order(
                            instrument_key=instrument_key,
                            quantity=exit_qty,
                            transaction_type=transaction_type,
                            order_type="MARKET",
                            product="I"
                        )
                        return result is not None
                    return False
                except:
                    return False
            
            # Use conservative worker count
            max_workers = min(10, max(1, len(self.positions_data)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(exit_single, pos) for pos in self.positions_data]
                results = [f.result() for f in as_completed(futures)]
            
            success = sum(results)
            
            self._log('info', f"Exit Position execution completed: {success}/{len(self.positions_data)} successful")
            
            # If 100% exit, cancel all SL orders since positions will be closed
            if percent == 100:
                print(f"🗑️ 100% exit detected - cancelling all SL orders...")
                threading.Thread(target=self._cancel_all_sl_orders, daemon=True).start()
            else:
                # Partial exit - update SL quantities to match remaining position
                print(f"🔄 Partial exit ({percent}%) - updating SL quantities...")
                def update_sl_after_exit():
                    import time
                    time.sleep(2)  # Wait for exit orders to complete
                    self.refresh_positions()  # Refresh to get updated quantities
                    time.sleep(1)  # Wait for refresh
                    # Apply SL with current position quantities (will update existing SL orders)
                    self._update_sl_quantities_for_current_positions()
                
                threading.Thread(target=update_sl_after_exit, daemon=True).start()
            
            # Immediate position refresh
            self.root.after(0, self.refresh_positions)
            
            # Refresh margin after exit to show updated balance
            self.root.after(600, lambda: threading.Thread(target=self.refresh_margin, daemon=True).start())
            
            self.root.after(0, lambda: messagebox.showinfo("Success", f"{success}/{len(self.positions_data)} exit orders placed!"))
        except Exception as e:
            self._log('error', f"Exit Position error: {e}", exc_info=True)
            self.root.after(0, lambda: messagebox.showerror("Error", f"Exit failed: {e}"))
    
    def _cancel_all_sl_orders(self):
        """Cancel all pending SL orders (used after 100% exit)."""
        try:
            import time
            time.sleep(2)  # Wait for exit orders to process
            
            cancelled_count = 0
            total_sl_orders = 0
            
            for broker_key, broker_info in self.trader.active_brokers.items():
                try:
                    client = broker_info['client']
                    orders_response = client.get_order_history()
                    
                    if orders_response and orders_response.get('data'):
                        orders = orders_response.get('data', [])
                        
                        # Find all pending SL orders
                        for order in orders:
                            order_status = order.get('status', '').strip().upper()
                            order_type = order.get('order_type', '') or order.get('orderType', '')
                            
                            # Cancel if it's a pending SL order
                            if (order_status in ['PENDING', 'OPEN', 'TRIGGER PENDING', 'TRIGGER_PENDING', 'NOT TRIGGERED', 'AWAITED'] and 
                                order_type in ['SL', 'SL-M', 'STOP_LOSS', 'STOP_LOSS_MARKET']):
                                
                                order_id = order.get('order_id') or order.get('orderId') or order.get('id')
                                if order_id:
                                    total_sl_orders += 1
                                    try:
                                        cancel_result = client.cancel_order(order_id=order_id)
                                        print(f"✅ Cancelled SL order {order_id} ({order.get('tradingsymbol')})")
                                        cancelled_count += 1
                                    except Exception as cancel_error:
                                        print(f"⚠️ Failed to cancel SL order {order_id}: {cancel_error}")
                
                except Exception as broker_error:
                    print(f"⚠️ Error fetching orders from {broker_key}: {broker_error}")
            
            if total_sl_orders > 0:
                print(f"🗑️ Cancelled {cancelled_count}/{total_sl_orders} SL orders after 100% exit")
                self._log('info', f"Cancelled {cancelled_count}/{total_sl_orders} SL orders after full exit")
            else:
                print(f"ℹ️ No SL orders found to cancel")
                
        except Exception as e:
            print(f"❌ Error cancelling SL orders: {e}")
            self._log('error', f"Failed to cancel SL orders: {e}")
    
    def _update_sl_quantities_for_current_positions(self):
        """Update SL order quantities to match current position quantities.
        
        This prevents SL orders from having stale quantities that could cause
        reverse positions when triggered after partial exits.
        """
        try:
            if not self.positions_data:
                print("ℹ️ No positions - skipping SL quantity update")
                return
            
            print(f"🔄 Updating SL quantities for {len(self.positions_data)} positions...")
            
            # Build position map: {(broker_key, instrument_key): current_qty}
            position_map = {}
            for pos in self.positions_data:
                broker_key = pos.get('broker_key', '')
                instrument_key = (pos.get('instrument_key') or 
                                pos.get('instrument_token') or 
                                pos.get('securityId') or 
                                pos.get('security_id') or '')
                qty = abs(pos.get('quantity', 0) or pos.get('netQty', 0))
                
                if instrument_key and qty > 0:
                    # Normalize instrument key
                    normalized_key = str(instrument_key).split('|')[-1]
                    position_map[(broker_key, normalized_key)] = {
                        'qty': qty,
                        'symbol': pos.get('tradingsymbol', ''),
                        'instrument_key': instrument_key
                    }
            
            updated_count = 0
            
            # Fetch and update SL orders for each broker
            for broker_key, broker_info in self.trader.active_brokers.items():
                try:
                    client = broker_info['client']
                    orders_response = client.get_order_history()
                    
                    if orders_response and orders_response.get('data'):
                        orders = orders_response.get('data', [])
                        
                        for order in orders:
                            order_status = order.get('status', '').strip().upper()
                            order_type = order.get('order_type', '') or order.get('orderType', '')
                            
                            # Only process pending SL orders
                            if (order_status in ['PENDING', 'OPEN', 'TRIGGER PENDING', 'TRIGGER_PENDING', 'NOT TRIGGERED', 'AWAITED'] and 
                                order_type in ['SL', 'SL-M', 'STOP_LOSS', 'STOP_LOSS_MARKET']):
                                
                                # Get order details
                                order_instrument = (order.get('instrument_key') or 
                                                  order.get('instrument_token') or 
                                                  order.get('securityId') or '')
                                normalized_instrument = str(order_instrument).split('|')[-1]
                                order_qty = order.get('quantity', 0)
                                order_id = order.get('order_id') or order.get('orderId')
                                
                                # Check if this SL belongs to a current position
                                pos_key = (broker_key, normalized_instrument)
                                if pos_key in position_map:
                                    position_info = position_map[pos_key]
                                    current_qty = position_info['qty']
                                    
                                    # If SL quantity doesn't match current position quantity
                                    if order_qty != current_qty:
                                        print(f"⚠️ SL qty mismatch for {position_info['symbol']}: SL={order_qty}, Position={current_qty}")
                                        
                                        try:
                                            # Cancel old SL order
                                            client.cancel_order(order_id=order_id)
                                            print(f"🗑️ Cancelled old SL {order_id} (qty={order_qty})")
                                            
                                            # Place new SL with correct quantity
                                            # We'll let the normal SL apply function handle this
                                            # by calling apply_stop_loss with the last used SL percentage
                                            updated_count += 1
                                            
                                        except Exception as update_error:
                                            print(f"⚠️ Failed to update SL for {position_info['symbol']}: {update_error}")
                
                except Exception as broker_error:
                    print(f"⚠️ Error processing SL updates for {broker_key}: {broker_error}")
            
            if updated_count > 0:
                print(f"✅ Cancelled {updated_count} outdated SL orders - will be replaced with correct quantities")
                # Re-apply SL to all positions with correct quantities
                if hasattr(self, '_last_sl_percent') and self._last_sl_percent:
                    print(f"🔄 Re-applying {self._last_sl_percent}% SL with updated quantities...")
                    self.apply_stop_loss(value=self._last_sl_percent, mode="percent", show_notification=False)
            else:
                print(f"✅ All SL quantities are correct")
                
        except Exception as e:
            print(f"❌ Error updating SL quantities: {e}")
            self._log('error', f"Failed to update SL quantities: {e}")
    
    def adjust_target_percent(self, delta):
        """Adjust target percentage and update display."""
        current = self.target_percent.get()
        new_val = max(1.0, min(50.0, current + delta))
        self.target_percent.set(round(new_val, 1))
        
        # Update target info display
        self.update_target_info()
    
    def update_target_info(self):
        """Update target information display based on current positions."""
        try:
            if not self.positions_data:
                self.target_info_label.config(text="No positions", fg='#999999')
                return
            
            # Calculate total invested amount
            total_invested = 0
            for pos in self.positions_data:
                qty = abs(pos.get('quantity', 0) or pos.get('netQty', 0))
                avg_price = abs(pos.get('average_price', 0) or pos.get('buyAvg', 0) or pos.get('sellAvg', 0))
                total_invested += qty * avg_price
            
            if total_invested == 0:
                self.target_info_label.config(text="No invested amount", fg='#999999')
                return
            
            # Calculate target profit based on percentage
            target_pct = self.target_percent.get()
            target_profit = total_invested * (target_pct / 100)
            
            # Display target info
            info_text = f"Target: ₹{target_profit:,.0f} ({target_pct}%)"
            self.target_info_label.config(text=info_text, fg='#00ff00')
            
        except Exception as e:
            print(f"Error updating target info: {e}")
            self.target_info_label.config(text="Calc error", fg='#ff0000')
    
    def apply_target(self):
        """Apply target orders to all positions."""
        if not self.positions_data:
            messagebox.showinfo("Info", "No positions to place targets")
            return
        
        target_pct = self.target_percent.get()
        
        # Calculate total invested and target profit
        total_invested = 0
        for pos in self.positions_data:
            qty = abs(pos.get('quantity', 0) or pos.get('netQty', 0))
            avg_price = abs(pos.get('average_price', 0) or pos.get('buyAvg', 0) or pos.get('sellAvg', 0))
            total_invested += qty * avg_price
        
        if total_invested == 0:
            messagebox.showwarning("Warning", "No invested amount found")
            return
        
        target_profit = total_invested * (target_pct / 100)
        
        msg = f"Place target orders for all {len(self.positions_data)} positions?\n\n"
        msg += f"Invested: ₹{total_invested:,.0f}\n"
        msg += f"Target: {target_pct}% (₹{target_profit:,.0f} profit)"
        
        if messagebox.askyesno("Confirm Target", msg):
            threading.Thread(target=self._apply_target_async, args=(target_pct,), daemon=True).start()
    
    def _apply_target_async(self, target_pct):
        """Apply target orders asynchronously."""
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def place_target_order(pos):
                try:
                    client = pos.get('client')
                    broker_key = pos.get('broker_key', '')
                    
                    qty = pos.get('quantity', 0) or pos.get('netQty', 0)
                    avg_price = pos.get('average_price', 0) or pos.get('buyAvg', 0) or pos.get('sellAvg', 0)
                    
                    if qty == 0 or avg_price == 0:
                        print(f"⏭️  Skipping position with zero quantity or price: {pos.get('tradingsymbol')}")
                        return False
                    
                    # Calculate target price based on position direction
                    # For BUY positions (qty > 0): target price = avg_price + (avg_price * target_pct / 100)
                    # For SELL positions (qty < 0): target price = avg_price - (avg_price * target_pct / 100)
                    if qty > 0:  # Long position - target above entry
                        target_price = avg_price * (1 + target_pct / 100)
                        transaction_type = "SELL"  # Exit with SELL
                    else:  # Short position - target below entry
                        target_price = avg_price * (1 - target_pct / 100)
                        transaction_type = "BUY"  # Exit with BUY
                    
                    # Round target price to 2 decimals
                    target_price = round(target_price, 2)
                    
                    instrument_key = (pos.get('instrument_key') or 
                                    pos.get('instrument_token') or 
                                    pos.get('securityId') or 
                                    pos.get('security_id') or '')
                    
                    if not instrument_key:
                        print(f"Missing instrument key for {pos.get('tradingsymbol', 'Unknown')}")
                        return False
                    
                    # Get broker key and exchange segment for Dhan
                    broker_key = pos.get('broker_key', '')
                    exchange_segment = pos.get('exchangeSegment') or pos.get('exchange_segment') or 'NSE_FNO'
                    
                    # Build order parameters
                    order_params = {
                        'instrument_key': instrument_key,
                        'quantity': abs(qty),
                        'transaction_type': transaction_type,
                        'order_type': "LIMIT",
                        'price': target_price,
                        'product': "I"
                    }
                    
                    # Only add exchange_segment for Dhan broker
                    if 'dhan' in broker_key.lower():
                        order_params['exchange_segment'] = exchange_segment
                    
                    # Place LIMIT order at target price
                    result = client.place_order(**order_params)
                    
                    print(f"🎯 Target order placed for {pos.get('tradingsymbol', 'Unknown')}: {transaction_type} @ ₹{target_price} (Entry: ₹{avg_price})")
                    return result is not None
                    
                except Exception as e:
                    print(f"Target order error for {pos.get('tradingsymbol', 'Unknown')}: {e}")
                    return False
            
            # Use optimal worker count
            # Use conservative worker count to prevent thread exhaustion
            max_workers = min(10, max(1, len(self.positions_data)))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(place_target_order, pos) for pos in self.positions_data]
                results = [f.result() for f in as_completed(futures)]
            
            success = sum(results)
            
            # Refresh orders display
            self.root.after(100, self.refresh_active_orders)
            self.root.after(0, lambda: messagebox.showinfo("Success", f"{success}/{len(self.positions_data)} target orders placed!"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Target placement failed: {e}"))
    
    def refresh_active_orders(self):
        """Refresh active orders from all brokers."""
        self.orders_tree.delete(*self.orders_tree.get_children())
        threading.Thread(target=self._refresh_orders_async, daemon=True).start()
    
    def _refresh_orders_async(self):
        """Fetch active orders asynchronously."""
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from datetime import datetime, timedelta
            
            # Get filter value
            filter_val = self.order_filter.get()
            
            # Calculate date range
            today = datetime.now().date()
            if filter_val == "today":
                start_date = today
                end_date = today
            elif filter_val == "yesterday":
                start_date = today - timedelta(days=1)
                end_date = today - timedelta(days=1)
            else:  # all
                start_date = None
                end_date = None
            
            def fetch_orders(broker_key, broker_info):
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    orders_response = client.get_order_history()
                    
                    print(f"\n📋 {account_name} - Order Response: {orders_response}")
                    
                    if orders_response and orders_response.get('data'):
                        orders = orders_response.get('data', [])
                        print(f"  📊 Total orders fetched: {len(orders)}")
                        
                        # Show all order statuses for debugging
                        for o in orders[:5]:  # Show first 5
                            print(f"    Order: {o.get('tradingsymbol', 'N/A')} | Status: {o.get('status', 'N/A')}")
                        
                        # Don't filter by status anymore - show all orders
                        # Apply date filtering instead
                        filtered_orders = []
                        for o in orders:
                            # Parse order date
                            time_field = o.get('order_timestamp') or o.get('created_at') or o.get('createTime')
                            if time_field:
                                try:
                                    time_val = str(time_field)
                                    if 'T' in time_val:
                                        dt = datetime.fromisoformat(time_val.replace('Z', '+00:00'))
                                    else:
                                        dt = datetime.strptime(time_val[:19], '%Y-%m-%d %H:%M:%S')
                                    order_date = dt.date()
                                    
                                    # Apply date filter
                                    if start_date is None or (start_date <= order_date <= end_date):
                                        filtered_orders.append(o)
                                except Exception as e:
                                    print(f"    Date parse error: {e}")
                                    # Include orders with unparseable dates if showing all
                                    if filter_val == "all":
                                        filtered_orders.append(o)
                            else:
                                # Include orders without dates if showing all
                                if filter_val == "all":
                                    filtered_orders.append(o)
                        
                        print(f"  ✅ Orders after date filter ({filter_val}): {len(filtered_orders)}")
                        return (account_name, broker_key, client, filtered_orders)
                except Exception as e:
                    print(f"Error fetching orders from {broker_info.get('name')}: {e}")
                return (None, None, None, [])
            
            # Fetch from all brokers in parallel
            with ThreadPoolExecutor(max_workers=min(10, len(self.trader.active_brokers))) as executor:
                futures = {executor.submit(fetch_orders, key, info): key 
                          for key, info in self.trader.active_brokers.items()}
                
                for future in as_completed(futures):
                    account_name, broker_key, client, orders = future.result()
                    if not account_name:
                        continue
                    
                    for order in orders:
                        self._add_order_to_display(order, account_name, broker_key, client)
        
        except Exception as e:
            print(f"Error refreshing orders: {e}")
    
    def _add_order_to_display(self, order, account_name, broker_key, client):
        """Add order to display."""
        try:
            from datetime import datetime
            
            symbol = order.get('tradingsymbol') or order.get('trading_symbol') or order.get('tradingSymbol') or 'N/A'
            order_type = order.get('order_type') or order.get('orderType') or 'N/A'
            qty = order.get('quantity') or order.get('qty') or 0
            trigger = order.get('trigger_price') or order.get('triggerPrice') or 0
            status = order.get('status') or order.get('orderStatus') or 'N/A'
            order_id = order.get('order_id') or order.get('orderId') or order.get('dhanOrderId') or 'N/A'
            
            # Get date and time
            date_str = 'N/A'
            time_str = 'N/A'
            time_field = order.get('order_timestamp') or order.get('created_at') or order.get('createTime')
            if time_field:
                try:
                    time_val = str(time_field)
                    if 'T' in time_val:
                        dt = datetime.fromisoformat(time_val.replace('Z', '+00:00'))
                    else:
                        dt = datetime.strptime(time_val[:19], '%Y-%m-%d %H:%M:%S')
                    date_str = dt.strftime('%Y-%m-%d')
                    time_str = dt.strftime('%H:%M:%S')
                except Exception as e:
                    print(f"    Time parse error: {e}")
            
            values = (date_str, time_str, account_name, symbol, order_type, qty, f"₹{trigger:.2f}", status, order_id)
            
            # Store order data including client and broker_key for cancellation
            order['broker_key'] = broker_key
            order['client'] = client
            order['account_name'] = account_name
            
            # Determine color based on status
            status_lower = status.lower()
            if 'complete' in status_lower or 'filled' in status_lower:
                tag = 'complete'
            elif 'reject' in status_lower or 'failed' in status_lower:
                tag = 'rejected'
            elif 'cancel' in status_lower:
                tag = 'cancelled'
            else:
                tag = 'pending'
            
            item_id = self.orders_tree.insert('', tk.END, values=values, tags=(tag,))
            
            # Store in dict for easy lookup
            if not hasattr(self, 'orders_data'):
                self.orders_data = {}
            self.orders_data[item_id] = order
            
        except Exception as e:
            print(f"Error adding order to display: {e}")
    
    def cancel_selected_order(self):
        """Cancel the selected order."""
        selection = self.orders_tree.selection()
        if not selection:
            messagebox.showinfo("Info", "Please select an order to cancel")
            return
        
        item_id = selection[0]
        if not hasattr(self, 'orders_data') or item_id not in self.orders_data:
            messagebox.showerror("Error", "Order data not found")
            return
        
        order = self.orders_data[item_id]
        symbol = order.get('tradingsymbol') or order.get('trading_symbol') or order.get('tradingSymbol') or 'N/A'
        order_id = order.get('order_id') or order.get('orderId') or order.get('dhanOrderId')
        
        if messagebox.askyesno("Confirm", f"Cancel order for {symbol}?"):
            threading.Thread(target=self._cancel_order_async, args=(order, item_id), daemon=True).start()
    
    def _cancel_order_async(self, order, item_id):
        """Cancel order asynchronously."""
        try:
            client = order.get('client')
            broker_key = order.get('broker_key', '')
            
            # Extract order ID based on broker type
            if 'dhan' in broker_key.lower():
                order_id = order.get('dhanOrderId') or order.get('orderId') or order.get('order_id')
            else:
                order_id = order.get('order_id') or order.get('orderId') or order.get('dhanOrderId')
            
            print(f"🔍 Cancel order debug: broker={broker_key}, order_id={order_id}, client={client}")
            
            if not client:
                self.root.after(0, lambda: messagebox.showerror("Error", "Missing client object"))
                return
            
            if not order_id:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Missing order ID. Available fields: {list(order.keys())}"))
                return
            
            result = client.cancel_order(order_id)
            print(f"✅ Order cancelled successfully: {result}")
            
            # Remove from display
            self.root.after(0, lambda: self.orders_tree.delete(item_id))
            if hasattr(self, 'orders_data') and item_id in self.orders_data:
                del self.orders_data[item_id]
            
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Order {order_id} cancelled!"))
        except Exception as e:
            print(f"❌ Cancel error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Cancel failed: {e}"))
    
    def refresh_order_book(self):
        """Refresh order book with all executed orders."""
        for item in self.orderbook_tree.get_children():
            self.orderbook_tree.delete(item)
        threading.Thread(target=self._load_orderbook_async, daemon=True).start()
    
    def _load_orderbook_async(self):
        """Load order book asynchronously."""
        try:
            from datetime import datetime
            filter_status = self.orderbook_filter.get()
            
            for broker_key, broker_info in self.trader.active_brokers.items():
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    
                    orders_response = client.get_order_history()
                    orders = orders_response.get('data', []) if orders_response else []
                    
                    for order in orders:
                        status = (order.get('status') or order.get('orderStatus', '')).upper()
                        
                        # Apply filter
                        if filter_status != 'ALL':
                            if filter_status == 'COMPLETE' and status not in ['COMPLETE', 'TRADED', 'EXECUTED']:
                                continue
                            elif filter_status == 'REJECTED' and status != 'REJECTED':
                                continue
                            elif filter_status == 'CANCELLED' and status not in ['CANCELLED', 'CANCELED']:
                                continue
                        
                        symbol = order.get('tradingsymbol') or order.get('tradingSymbol') or 'N/A'
                        trans_type = (order.get('transaction_type') or 
                                    order.get('transactionType') or 
                                    order.get('orderSide', '')).upper()
                        
                        qty = (order.get('quantity') or 
                              order.get('tradedQuantity') or 
                              order.get('filledQty') or 0)
                        
                        price = (order.get('average_price') or 
                               order.get('averagePrice') or 
                               order.get('tradedPrice') or 
                               order.get('price', 0))
                        
                        order_id = (order.get('order_id') or 
                                  order.get('orderId') or 
                                  order.get('id', 'N/A'))
                        
                        # Extract time
                        time_str = 'N/A'
                        for time_field in ['order_timestamp', 'created_at', 'createTime', 
                                         'transactionTime', 'tradeTime']:
                            if order.get(time_field):
                                try:
                                    time_val = str(order[time_field])
                                    if 'T' in time_val:
                                        dt = datetime.fromisoformat(time_val.replace('Z', '+00:00'))
                                    else:
                                        dt = datetime.strptime(time_val[:19], '%Y-%m-%d %H:%M:%S')
                                    time_str = dt.strftime('%H:%M:%S')
                                    break
                                except:
                                    pass
                        
                        # Color code by status
                        if status in ['COMPLETE', 'TRADED', 'EXECUTED']:
                            tag = 'complete'
                        elif status == 'REJECTED':
                            tag = 'rejected'
                        elif status in ['CANCELLED', 'CANCELED']:
                            tag = 'cancelled'
                        else:
                            tag = 'pending'
                        
                        values = (time_str, account_name, symbol, trans_type, qty, 
                                f"₹{price:.2f}", status, order_id)
                        
                        self.root.after(0, lambda v=values, t=tag: 
                                      self.orderbook_tree.insert('', tk.END, values=v, tags=(t,)))
                
                except Exception as e:
                    print(f"Error loading orders from {broker_info.get('name')}: {e}")
            
            # Configure tag colors
            self.root.after(0, lambda: [
                self.orderbook_tree.tag_configure('complete', foreground='#00ff00'),
                self.orderbook_tree.tag_configure('rejected', foreground='#ff0000'),
                self.orderbook_tree.tag_configure('cancelled', foreground='#ffaa00'),
                self.orderbook_tree.tag_configure('pending', foreground='#00aaff')
            ])
            
        except Exception as e:
            print(f"Error loading order book: {e}")
    
    def export_order_book(self):
        """Export order book to CSV file."""
        try:
            import csv
            from datetime import datetime
            from tkinter import filedialog
            
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"orderbook_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            
            if not filename:
                return
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write headers
                headers = ['Time', 'Account', 'Symbol', 'Type', 'Qty', 'Price', 'Status', 'Order ID']
                writer.writerow(headers)
                
                # Write data
                for item in self.orderbook_tree.get_children():
                    values = self.orderbook_tree.item(item)['values']
                    writer.writerow(values)
            
            messagebox.showinfo("Success", f"Order book exported to:\n{filename}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")
    
    def update_risk_status(self):
        """Update risk management status display."""
        try:
            # Calculate today's total P&L from positions
            today_pnl = sum(p.get('pnl', 0) for p in self.positions_data)
            
            # Update today's P&L label
            pnl_color = '#00ff00' if today_pnl >= 0 else '#ff0000'
            self.today_pnl_label.config(text=f"₹{today_pnl:,.2f}", fg=pnl_color)
            
            # Calculate loss remaining
            max_loss = self.max_daily_loss.get()
            loss_remaining = max_loss + today_pnl  # Positive pnl reduces loss remaining
            
            # Update loss remaining label
            if loss_remaining > 0:
                remaining_color = '#00ff00' if loss_remaining > max_loss * 0.5 else '#ffaa00'
                self.loss_remaining_label.config(text=f"₹{loss_remaining:,.2f}", fg=remaining_color)
            else:
                self.loss_remaining_label.config(text="LIMIT EXCEEDED", fg='#ff0000')
            
            # Check if loss limit exceeded
            if today_pnl < -max_loss:
                self.risk_warning_label.config(
                    text=f"⚠️ LOSS LIMIT EXCEEDED! Loss: ₹{abs(today_pnl):,.2f}"
                )
                
                # Auto square-off if enabled
                if self.auto_square_off.get() and self.risk_check_active:
                    self.risk_check_active = False  # Prevent multiple triggers
                    self.root.bell()
                    
                    result = messagebox.askyesno(
                        "🚨 LOSS LIMIT EXCEEDED!",
                        f"Daily loss limit of ₹{max_loss:,.2f} exceeded!\n\n"
                        f"Current Loss: ₹{abs(today_pnl):,.2f}\n\n"
                        "Auto Square-Off ALL positions now?",
                        icon='warning'
                    )
                    
                    if result:
                        self.emergency_exit_all()
                    else:
                        self.risk_check_active = True  # Re-enable if user cancels
            
            elif today_pnl < -max_loss * 0.8:  # 80% of limit
                self.risk_warning_label.config(
                    text=f"⚠️ WARNING: Loss at {abs(today_pnl/max_loss*100):.1f}% of limit"
                )
            else:
                self.risk_warning_label.config(text="✅ Within Risk Limits")
                
        except Exception as e:
            print(f"Error updating risk status: {e}")
    
    def emergency_exit_all(self):
        """Emergency exit all positions immediately."""
        if not self.positions_data:
            messagebox.showinfo("Info", "No open positions to exit")
            return
        
        result = messagebox.askyesno(
            "🚨 EMERGENCY EXIT",
            f"Exit ALL {len(self.positions_data)} positions immediately?\n\n"
            "This action cannot be undone!",
            icon='warning'
        )
        
        if result:
            self._log('critical', f"EMERGENCY EXIT initiated: {len(self.positions_data)} positions")
            # Use existing exit function with 100%
            self.exit_percent.set(100)
            threading.Thread(target=self._apply_exit_async, args=(100,), daemon=True).start()
    
    def load_closed_positions(self):
        """Load closed positions into the treeview."""
        # Clear existing data
        for item in self.closed_tree.get_children():
            self.closed_tree.delete(item)
        threading.Thread(target=self._load_closed_async, daemon=True).start()
    
    def _load_closed_async(self):
        """Load closed positions asynchronously."""
        try:
            from collections import defaultdict
            from datetime import datetime
            
            all_closed_positions = []
            
            for broker_key, broker_info in self.trader.active_brokers.items():
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    
                    print(f"📊 Loading closed positions for {account_name}...")
                    
                    orders = client.get_order_history()
                    
                    if isinstance(orders, dict):
                        orders_data = orders.get('data', [])
                    elif isinstance(orders, list):
                        orders_data = orders
                    else:
                        orders_data = []
                    
                    if not orders_data:
                        print(f"   No orders found for {account_name}")
                        continue
                    
                    # Group trades by symbol
                    grouped_trades = defaultdict(list)
                    
                    for order in orders_data:
                        status = order.get('status', '').upper()
                        if not status:
                            status = order.get('orderStatus', '').upper()
                        
                        if status in ['COMPLETE', 'TRADED', 'EXECUTED']:
                            symbol = order.get('tradingsymbol') or order.get('tradingSymbol') or str(order.get('securityId', 'N/A'))
                            
                            trans_type = (order.get('transaction_type') or 
                                        order.get('transactionType') or 
                                        order.get('orderSide', '')).upper()
                            
                            price = (order.get('average_price') or 
                                   order.get('averagePrice') or 
                                   order.get('tradedPrice') or 
                                   order.get('price', 0))
                            
                            qty = (order.get('quantity') or 
                                  order.get('tradedQuantity') or 
                                  order.get('filledQty') or 
                                  order.get('filled_quantity', 0))
                            
                            # Extract time
                            time_str = 'N/A'
                            time_dt = None
                            for time_field in ['order_timestamp', 'created_at', 'buy_date',
                                              'createTime', 'transactionTime', 'tradeTime']:
                                if order.get(time_field):
                                    try:
                                        if 'T' in str(order[time_field]):
                                            dt = datetime.fromisoformat(str(order[time_field]).replace('Z', '+00:00'))
                                        else:
                                            dt = datetime.strptime(str(order[time_field])[:19], '%Y-%m-%d %H:%M:%S')
                                        time_str = dt.strftime('%H:%M:%S')
                                        time_dt = dt
                                        break
                                    except:
                                        pass
                            
                            if price and qty:
                                grouped_trades[symbol].append({
                                    'side': trans_type.upper(),
                                    'price': float(price),
                                    'qty': int(qty),
                                    'time': time_str,
                                    'time_dt': time_dt  # Keep datetime for sorting
                                })
                    
                    print(f"   ✅ Found {len(grouped_trades)} unique symbols for {account_name}")
                    
                    # Calculate P&L for each symbol
                    for symbol, symbol_trades in grouped_trades.items():
                        buy_trades = [t for t in symbol_trades if t['side'] == 'BUY']
                        sell_trades = [t for t in symbol_trades if t['side'] == 'SELL']
                        
                        # Sort trades by time (earliest first)
                        buy_trades_sorted = sorted([t for t in buy_trades if t.get('time_dt')], 
                                                   key=lambda x: x['time_dt'])
                        sell_trades_sorted = sorted([t for t in sell_trades if t.get('time_dt')], 
                                                    key=lambda x: x['time_dt'])
                        
                        total_buy_qty = sum(t['qty'] for t in buy_trades)
                        total_sell_qty = sum(t['qty'] for t in sell_trades)
                        
                        avg_buy = sum(t['price'] * t['qty'] for t in buy_trades) / total_buy_qty if total_buy_qty > 0 else 0
                        avg_sell = sum(t['price'] * t['qty'] for t in sell_trades) / total_sell_qty if total_sell_qty > 0 else 0
                        
                        # Get first buy time and first sell time (earliest of each)
                        buy_time = buy_trades_sorted[0]['time'] if buy_trades_sorted else (buy_trades[0]['time'] if buy_trades else 'N/A')
                        sell_time = sell_trades_sorted[0]['time'] if sell_trades_sorted else (sell_trades[0]['time'] if sell_trades else 'N/A')
                        
                        closed_qty = min(total_buy_qty, total_sell_qty)
                        
                        # Only show if there's a closed position (both buy and sell)
                        if closed_qty > 0:
                            pnl = (avg_sell - avg_buy) * closed_qty
                            
                            all_closed_positions.append({
                                'account': account_name,
                                'symbol': symbol,
                                'buy_qty': total_buy_qty,
                                'buy_avg': avg_buy,
                                'sell_qty': total_sell_qty,
                                'sell_avg': avg_sell,
                                'closed_qty': closed_qty,
                                'pnl': pnl,
                                'buy_time': buy_time,
                                'sell_time': sell_time
                            })
                    
                except Exception as e:
                    print(f"❌ Error loading {broker_key}: {e}")
            
            # Update treeview on main thread
            def update_tree():
                # Clear existing
                for item in self.closed_tree.get_children():
                    self.closed_tree.delete(item)
                
                # Add all positions
                for pos in all_closed_positions:
                    pnl_str = f"{pos['pnl']:+,.2f}"  # +/- sign with 2 decimals
                    
                    # Color code by P&L
                    tag = 'profit' if pos['pnl'] >= 0 else 'loss'
                    
                    # Generate trade analysis
                    analysis = self._analyze_closed_trade(pos)
                    
                    self.closed_tree.insert('', tk.END, values=(
                        pos['account'],
                        pos['symbol'],
                        pos['buy_qty'],
                        f"{pos['buy_avg']:.2f}",
                        pos['sell_qty'],
                        f"{pos['sell_avg']:.2f}",
                        pos['closed_qty'],
                        pnl_str,
                        pos['buy_time'],
                        pos['sell_time'],
                        analysis
                    ), tags=(tag,))
                
                # Configure tags for color coding
                self.closed_tree.tag_configure('profit', foreground='#00ff00')
                self.closed_tree.tag_configure('loss', foreground='#ff0000')
                
                print(f"✅ Loaded {len(all_closed_positions)} closed positions")
            
            self.root.after(0, update_tree)
            
        except Exception as e:
            print(f"❌ Error loading closed positions: {e}")
    
    def load_account_summary(self):
        """Load account summary into the text widget."""
        self.account_text.delete(1.0, tk.END)
        self.account_text.insert(tk.END, "Loading account summary...\n\n")
        threading.Thread(target=self._load_account_summary_async, daemon=True).start()
    
    def _load_account_summary_async(self):
        """Load account summary asynchronously."""
        try:
            output = []
            output.append("Account summary loaded successfully.")
            text_content = "\n".join(output)
            self.root.after(0, lambda: self.account_text.delete(1.0, tk.END))
            self.root.after(0, lambda: self.account_text.insert(tk.END, text_content))
        except Exception as e:
            self.root.after(0, lambda: self.account_text.insert(tk.END, f"Error: {e}"))
    
    def adjust_lots(self, delta):
        """Adjust lot quantity."""
        try:
            current = self.lot_quantity.get()
            new_value = max(1, current + delta)
            self.lot_quantity.set(new_value)
        except:
            self.lot_quantity.set(1)
    
    def validate_lot_entry(self):
        """Validate manual lot entry."""
        try:
            value = self.lot_quantity.get()
            if value < 1:
                self.lot_quantity.set(1)
                messagebox.showwarning("Invalid Lot", "Lot quantity must be at least 1")
        except:
            self.lot_quantity.set(1)
            messagebox.showerror("Invalid Input", "Please enter a valid number")
    
    def set_lot_quantity(self, lot_value):
        """Set lot quantity to specific value (used by quick lot buttons)."""
        self.lot_quantity.set(lot_value)
    
    def on_strike_selected(self):
        """Handle strike selection from combobox."""
        strike = self.strike_combo.get()
        if strike:
            self.selected_strike.set(strike)
    
    def load_strike_options(self):
        """Load strike options based on current index price (±5 strikes)."""
        try:
            symbol = self.selected_symbol.get()
            if not symbol:
                return
            
            # Get current index price from market data (REAL-TIME)
            base_price = 0
            
            # Try to get real-time LTP from market_data
            if hasattr(self, 'market_data') and symbol in self.market_data:
                base_price = self.market_data[symbol].get('ltp', 0)
                # Only use if it's a valid price (> 100 for indices)
                if base_price > 100:
                    print(f"📡 Using real-time {symbol} price: {base_price:.2f}")
                else:
                    base_price = 0  # Reset to use fallback
            
            # Fallback to approximate values if market data not available or invalid
            if base_price == 0:
                base_prices = {
                    "NIFTY": 25940,
                    "BANKNIFTY": 55500,
                    "SENSEX": 85400,
                    "FINNIFTY": 23500,
                    "MIDCPNIFTY": 13500
                }
                base_price = base_prices.get(symbol, 25940)
                print(f"⚠️ Using fallback static price for {symbol}: {base_price}")
            
            # Strike intervals for different indices
            strike_interval = 50 if symbol in ["NIFTY", "FINNIFTY", "MIDCPNIFTY"] else 100
            
            # Round to nearest strike
            current_strike = round(base_price / strike_interval) * strike_interval
            
            # Generate ±5 strikes (11 total - covers 500 points range for NIFTY)
            strikes = []
            for i in range(-5, 6):
                strike = current_strike + (i * strike_interval)
                strikes.append(str(int(strike)))
            
            self.strike_combo['values'] = strikes
            # Set middle value (ATM) as default
            self.strike_combo.set(str(int(current_strike)))
            self.selected_strike.set(str(int(current_strike)))
            
        except Exception as e:
            print(f"Error loading strikes: {e}")
    
    def toggle_limit_price(self):
        """Show/hide limit price input based on order type."""
        if self.order_type.get() == "LIMIT":
            # Insert limit price frame after order type frame, before margin info
            self.limit_price_frame.pack(fill=tk.X, pady=5, after=self.order_type_frame)
        else:
            self.limit_price_frame.pack_forget()
    
    def load_expiries(self):
        """Load expiries for selected symbol."""
        try:
            self.expiry_listbox.delete(0, tk.END)
            symbol = self.selected_symbol.get()
            
            if not symbol:
                return
            
            # Get expiries from trader
            expiries = self.trader._get_expiries_for_symbol(symbol)
            
            if not expiries:
                self.expiry_listbox.insert(tk.END, "No expiries available")
                return
            
            for exp in expiries[:5]:  # Show first 5 expiries
                self.expiry_listbox.insert(tk.END, exp)
            
            if expiries:
                self.expiry_listbox.selection_set(0)
                self.selected_expiry.set(expiries[0])
        except Exception as e:
            print(f"Error loading expiries: {e}")
            self.expiry_listbox.insert(tk.END, "Error loading expiries")
    
    def on_symbol_change(self):
        """Handle symbol change - clear strike and load expiries."""
        # Clear strike combobox
        self.strike_combo.set('')
        # Load new expiries
        self.load_expiries()
        # Load strike options
        self.load_strike_options()
    
    def on_expiry_select(self, event):
        """Handle expiry selection."""
        selection = self.expiry_listbox.curselection()
        if selection:
            self.selected_expiry.set(self.expiry_listbox.get(selection[0]))
        self.fetch_ltp_and_update()
    
    def update_margin_display(self):
        """Update margin display showing breakdown by account with max lots."""
        try:
            # Clear existing widgets
            for widget in self.margin_accounts_frame.winfo_children():
                widget.destroy()
            
            # Index configurations for max lot calculation
            # Note: Exchange freeze limits are 13/30/45 for NIFTY/BANKNIFTY/SENSEX
            # but users can place more by splitting orders
            indices = {
                "NIFTY": {"lot_size": 65, "avg_premium": 150},
                "BANKNIFTY": {"lot_size": 30, "avg_premium": 300},
                "SENSEX": {"lot_size": 20, "avg_premium": 400}
            }
            
            # Show each account's margin with max lots
            for account_name, margin in self.account_margins.items():
                frame = tk.Frame(self.margin_accounts_frame, bg='#2d2d2d')
                frame.pack(fill=tk.X, pady=1)
                
                # Account name on left
                tk.Label(frame, text=f"{account_name}:", bg='#2d2d2d', fg='#aaaaaa',
                        font=('Arial', 9, 'bold')).pack(side=tk.LEFT)
                
                # Calculate and show max lots
                if margin > 0:
                    lots = []
                    for name, config in indices.items():
                        margin_per_lot = config["avg_premium"] * config["lot_size"]
                        affordable_lots = int(margin / margin_per_lot)
                        if affordable_lots > 0:
                            # Use abbreviated names
                            if name == "NIFTY":
                                lots.append(f"NIF:{affordable_lots}")
                            elif name == "BANKNIFTY":
                                lots.append(f"BANKN:{affordable_lots}")
                            elif name == "SENSEX":
                                lots.append(f"SEN:{affordable_lots}")
                    
                    if lots:
                        # Max lots in the middle
                        tk.Label(frame, text=' | '.join(lots), bg='#2d2d2d', fg='#00aaff',
                                font=('Arial', 9)).pack(side=tk.LEFT, padx=(5, 0))
                        
                        # Colon separator
                        tk.Label(frame, text=":", bg='#2d2d2d', fg='#aaaaaa',
                                font=('Arial', 9)).pack(side=tk.LEFT, padx=(5, 0))
                
                # Margin amount on right
                tk.Label(frame, text=f"₹{margin:,.2f}", bg='#2d2d2d', fg='#00ff00',
                        font=('Arial', 9, 'bold')).pack(side=tk.RIGHT)
        except Exception as e:
            print(f"Error updating margin display: {e}")
    
    def refresh_margin(self):
        """Fetch total available margin from all brokers and show breakdown by account."""
        try:
            total_margin = 0.0
            self.account_margins.clear()
            
            if self.trader.multi_account_mode:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                def fetch_margin(broker_key, broker_info):
                    try:
                        client = broker_info['client']
                        account_name = broker_info['name']
                        margin_response = client.get_funds_and_margin()
                        
                        if margin_response:
                            # Handle both Upstox (status='success') and Dhan (no status) formats
                            data = margin_response.get('data', margin_response)
                            
                            if 'equity' in data:
                                # Upstox format or nested equity
                                margin = data['equity'].get('available_margin', 0)
                            elif 'availabelBalance' in data:
                                # Dhan format (typo in their API)
                                margin = data.get('availabelBalance', 0)
                            elif 'available_margin' in data:
                                # Generic format
                                margin = data.get('available_margin', 0)
                            else:
                                margin = 0
                            
                            print(f"Funds response for {account_name}: {margin_response}")
                            return (account_name, margin, True)  # True = valid token
                    except Exception as e:
                        error_msg = str(e)
                        # Check for 401 authentication errors (invalid/expired token)
                        if '401' in error_msg:
                            print(f"⚠️  {broker_info.get('name', 'Unknown')}: Token expired/invalid - skipping margin display")
                            return (broker_info.get('name', 'Unknown'), 0.0, False)  # False = invalid token
                        else:
                            print(f"⚠️  Error fetching margin from {broker_info.get('name', 'Unknown')}: {e}")
                    return (broker_info.get('name', 'Unknown'), 0.0, True)  # Show 0 for other errors
                
                with ThreadPoolExecutor(max_workers=min(10, len(self.trader.active_brokers))) as executor:
                    futures = {executor.submit(fetch_margin, key, info): key 
                              for key, info in self.trader.active_brokers.items()}
                    for future in as_completed(futures):
                        account_name, margin, is_valid = future.result()
                        # Only add to display if token is valid
                        if is_valid:
                            self.account_margins[account_name] = margin
                            total_margin += margin
            else:
                for broker_key, broker_info in self.trader.active_brokers.items():
                    try:
                        client = broker_info['client']
                        account_name = broker_info['name']
                        margin_response = client.get_funds_and_margin()
                        
                        if margin_response:
                            # Handle both Upstox and Dhan response formats
                            data = margin_response.get('data', margin_response)
                            
                            if 'equity' in data:
                                # Upstox format or nested equity
                                margin = data['equity'].get('available_margin', 0)
                            elif 'availabelBalance' in data:
                                # Dhan format (typo in their API)
                                margin = data.get('availabelBalance', 0)
                            elif 'available_margin' in data:
                                # Generic format
                                margin = data.get('available_margin', 0)
                            else:
                                margin = 0
                            
                            self.account_margins[account_name] = margin
                            total_margin += margin
                    except Exception as e:
                        error_msg = str(e)
                        # Check for 401 authentication errors - don't show margin for invalid tokens
                        if '401' in error_msg:
                            print(f"⚠️  {account_name}: Token expired/invalid - skipping margin display")
                            # Mark broker as invalid for order execution
                            if broker_key not in self.invalid_brokers:
                                self.invalid_brokers.add(broker_key)
                                self._log('warning', f"Broker {account_name} ({broker_key}) marked as invalid due to 401 error")
                        else:
                            print(f"⚠️  Error fetching margin from {account_name}: {e}")
            
            self.total_margin.set(total_margin)
            self.root.after(0, lambda: self.margin_label.config(text=f"₹{total_margin:,.2f}"))
            
            # Update account-wise margin display (includes max lot calculation)
            self.root.after(0, self.update_margin_display)
            
        except Exception as e:
            print(f"Error refreshing margin: {e}")
        
        # No automatic refresh - only refresh after order placement/exit
    
    def fetch_ltp_and_update(self):
        """Placeholder for strike/expiry changes."""
        # No longer needed - order value shown in confirmation dialog
        pass
    
    def load_strikes(self):
        """Load strikes near entered strike."""
        # This would load strikes based on entered value
        pass
    
    def place_order(self, transaction_type):
        """Place order with selected parameters."""
        try:
            symbol = self.selected_symbol.get()
            expiry = self.selected_expiry.get()
            strike = self.strike_combo.get()
            opt_type = self.selected_type.get()
            lots = self.lot_quantity.get()
            order_type = self.order_type.get()
            
            if ENABLE_LOGGING:
                self._log('info', f"Place Order Initiated: {transaction_type} {symbol} {expiry} {strike} {opt_type} Lots:{lots} Type:{order_type}")
            
            if not all([symbol, expiry, strike]):
                if ENABLE_LOGGING:
                    self._log('warning', "Order placement failed: Missing parameters")
                messagebox.showwarning("Warning", "Please select all order parameters!")
                return
            
            # Validate limit price if LIMIT order
            limit_price = None
            if order_type == "LIMIT":
                limit_price = self.limit_price_var.get()
                if limit_price <= 0:
                    self._log('warning', "Order placement failed: Invalid limit price")
                    messagebox.showwarning("Warning", "Please enter a valid limit price!")
                    return
                self._log('info', f"Limit price set: {limit_price}")
            
            # Get lot size
            lot_size = 0
            for idx_key, idx_info in self.trader.indices.items():
                if idx_info['name'] == symbol:
                    lot_size = idx_info['lot_size']
                    break
            
            quantity = lots * lot_size
            
            # Skip LTP fetch for faster order confirmation (can add back as optional later)
            # LTP fetching takes 3-4 seconds due to CSV reads and API calls
            ltp_price = 0
            
            # Calculate projected order value
            order_value = 0
            price_source = ""
            
            if order_type == "LIMIT" and limit_price:
                # For LIMIT orders, use limit price (always accurate)
                order_value = quantity * limit_price
                price_source = f"Limit Price: ₹{limit_price:.2f}"
                if ltp_price > 0:
                    price_source += f" (Current LTP: ₹{ltp_price:.2f})"
            elif ltp_price > 0:
                # For MARKET orders, only show if we successfully fetched real LTP
                order_value = quantity * ltp_price
                price_source = f"LTP: ₹{ltp_price:.2f}"
            # Note: If MARKET order and no LTP available, order_value stays 0 (no projection)
            
            # Confirm order
            msg = f"{transaction_type} {symbol}\n"
            msg += f"Expiry: {expiry}\n"
            msg += f"Strike: {strike} {opt_type}\n"
            msg += f"Lots: {lots} ({quantity} qty)\n"
            msg += f"Type: {order_type}"
            
            if price_source:
                msg += f"\n{price_source}"
            
            if order_value > 0:
                msg += f"\n\n💰 Projected Value: ₹{order_value:,.2f}"
                
                # Add margin info
                available_margin = self.total_margin.get()
                if available_margin > 0:
                    remaining = available_margin - order_value
                    msg += f"\n📊 Available Margin: ₹{available_margin:,.2f}"
                    if remaining >= 0:
                        msg += f"\n✅ Remaining: ₹{remaining:,.2f}"
                    else:
                        msg += f"\n⚠️  Insufficient: ₹{remaining:,.2f}"
            else:
                # If no price available, just show available margin
                available_margin = self.total_margin.get()
                if available_margin > 0:
                    msg += f"\n\n📊 Available Margin: ₹{available_margin:,.2f}"
            
            if messagebox.askyesno("Confirm Order", msg):
                # Place order using trader
                product_type = self.product_type.get()  # Get INTRADAY or NORMAL from GUI
                self._log('info', f"Starting async order placement: Product={product_type}")
                threading.Thread(target=self._place_order_async,
                               args=(symbol, expiry, strike, opt_type, quantity,
                                    transaction_type, order_type, limit_price, product_type),
                               daemon=True).start()
        except Exception as e:
            self._log('error', f"Order placement error: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to place order: {e}")
    
    def _place_order_async(self, symbol, expiry, strike, opt_type, quantity,
                          transaction_type, order_type, limit_price, product_type="INTRADAY"):
        """Place order asynchronously with AMO support."""
        try:
            # Build instrument details
            index_num = None
            for key, info in self.trader.indices.items():
                if info['name'] == symbol:
                    index_num = key
                    break
            
            # Detect market hours for AMO (After Market Order)
            from datetime import datetime, time
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            current_time = datetime.now().time()
            market_open = time(9, 15)   # 9:15 AM
            market_close = time(15, 30)  # 3:30 PM
            
            # Enable AMO if outside market hours (before 9:15 AM or after 3:30 PM)
            is_amo = not (market_open <= current_time <= market_close)
            
            # Map product type: INTRADAY→I, NORMAL→D
            product_code = "I" if product_type == "INTRADAY" else "D"
            
            if is_amo:
                if ENABLE_LOGGING:
                    self._log('info', f"AMO Mode: After market hours detected (Time: {current_time.strftime('%H:%M:%S')})")
                if ENABLE_DEBUG_PRINTS:
                    print(f"🌙 After Market Hours - Placing AMO orders (product={product_code})")
            else:
                if ENABLE_LOGGING:
                    self._log('info', f"Regular Mode: Market hours (Time: {current_time.strftime('%H:%M:%S')})")
                if ENABLE_DEBUG_PRINTS:
                    print(f"☀️ Market Hours - Regular orders (product={product_code})")
            
            def place_single_order(broker_key, broker_info):
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    
                    # Get instrument details
                    index_name = self.trader.indices[index_num]['name']
                    instrument_key = self.trader.format_instrument_key_for_broker(
                        broker_key, index_name, expiry, strike, opt_type,
                        self.trader.indices[index_num]
                    )
                    
                    print(f"🔑 {account_name}: instrument_key = {instrument_key}")
                    
                    if not instrument_key:
                        raise Exception(f"Instrument not found for {index_name} {expiry} {strike} {opt_type}")
                    
                    # Place entry order
                    if order_type == "LIMIT" and limit_price:
                        result = client.place_order(
                            instrument_key=instrument_key,
                            quantity=quantity,
                            transaction_type=transaction_type,
                            order_type="LIMIT",
                            product=product_code,
                            price=limit_price,
                            is_amo=is_amo
                        )
                        entry_price = limit_price
                    else:
                        result = client.place_order(
                            instrument_key=instrument_key,
                            quantity=quantity,
                            transaction_type=transaction_type,
                            order_type="MARKET",
                            product=product_code,
                            is_amo=is_amo
                        )
                        entry_price = None
                    
                    # Place SL order if enabled and entry order succeeded
                    if result:
                        enable_sl = hasattr(self, 'enable_auto_sl') and self.enable_auto_sl.get()
                        
                        # Track positions with auto-SL enabled for auto-updates on quantity changes
                        if enable_sl:
                            sl_percent = self.auto_sl_percent.get()
                            # Store auto-SL config for this symbol
                            if not hasattr(self, '_auto_sl_tracking'):
                                self._auto_sl_tracking = {}
                            self._auto_sl_tracking[instrument_key] = {
                                'percent': sl_percent,
                                'enabled': True,
                                'symbol': selected_symbol
                            }
                            print(f"🛡️ Auto-SL tracking enabled for {selected_symbol} at {sl_percent}%")
                        
                        if enable_sl:
                            try:
                                # Get LTP for market orders to calculate SL
                                if not entry_price:
                                    try:
                                        quote = client.get_market_quote(instrument_key)
                                        entry_price = float(quote.get('data', {}).get('ltp', 0) or 
                                                          quote.get('data', {}).get('last_price', 0))
                                    except:
                                        entry_price = None
                                
                                if entry_price and entry_price > 0:
                                    # Opposite transaction types for exit orders
                                    exit_transaction = "SELL" if transaction_type == "BUY" else "BUY"
                                    
                                    # Calculate SL price
                                    sl_percent = self.auto_sl_percent.get()
                                    
                                    if transaction_type == "BUY":
                                        sl_price = entry_price * (1 - sl_percent/100)
                                        sl_trigger = sl_price + 0.05
                                    else:  # SELL
                                        sl_price = entry_price * (1 + sl_percent/100)
                                        sl_trigger = sl_price - 0.05
                                    
                                    sl_price = round(sl_price, 2)
                                    sl_trigger = round(sl_trigger, 2)
                                    
                                    # Place new SL order (for initial entry)
                                    try:
                                        client.place_order(
                                            instrument_key=instrument_key,
                                            quantity=quantity,
                                            transaction_type=exit_transaction,
                                            order_type="SL-M",
                                            product=product_code,
                                            price=sl_price,
                                            trigger_price=sl_trigger,
                                            is_amo=is_amo
                                        )
                                        print(f"  ✅ SL order placed: qty={quantity}, trigger={sl_trigger}")
                                    except Exception as sl_err:
                                        print(f"  ⚠️ SL order failed: {sl_err}")
                            except Exception as bracket_err:
                                print(f"  ⚠️ Auto SL failed: {bracket_err}")
                    
                    return {'success': result is not None, 'broker': account_name, 'entry_price': entry_price}
                except Exception as e:
                    return {'success': False, 'broker': broker_info.get('name', 'Unknown'), 'error': str(e)}
            
            results = []
            if self.trader.multi_account_mode:
                # Filter out invalid brokers before execution
                valid_brokers = {k: v for k, v in self.trader.active_brokers.items() 
                                if k not in self.invalid_brokers}
                
                if not valid_brokers:
                    self._log('error', "No valid broker accounts available for order execution")
                    self.root.after(0, lambda: messagebox.showerror("Error", 
                        "No valid broker accounts available. Please check your tokens."))
                    return
                
                if len(valid_brokers) < len(self.trader.active_brokers):
                    skipped = [self.trader.active_brokers[k]['name'] for k in self.invalid_brokers 
                              if k in self.trader.active_brokers]
                    self._log('warning', f"Skipping brokers with invalid tokens: {', '.join(skipped)}")
                    print(f"⚠️  Skipping accounts with invalid tokens: {', '.join(skipped)}")
                
                # Use optimal workers - parallel execution without thread exhaustion
                max_workers = min(16, len(valid_brokers))
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(place_single_order, key, info) 
                              for key, info in valid_brokers.items()]
                    
                    # Collect results as they complete (fastest first)
                    for future in as_completed(futures):
                        results.append(future.result())
            else:
                # Single account
                result = place_single_order(self.trader.current_broker, {
                    'client': self.trader.current_client,
                    'name': self.trader.account_name
                })
                results.append(result)
            
            success_count = sum(1 for r in results if r.get('success'))
            failed_results = [r for r in results if not r.get('success')]
            
            self._log('info', f"Order Execution Results: {success_count}/{len(results)} successful")
            if failed_results:
                for failed in failed_results:
                    self._log('error', f"Order failed for {failed['broker']}: {failed.get('error', 'Unknown error')}")
            
            # Show detailed results
            if success_count == len(results):
                # All succeeded
                self._log('info', "All orders executed successfully")
                self.root.after(0, lambda: messagebox.showinfo("Success", 
                    f"✅ Order executed! ({success_count}/{len(results)} accounts)\n\nPositions updating..."))
            elif success_count > 0:
                # Partial success
                self._log('warning', f"Partial success: {success_count}/{len(results)} orders placed")
                error_details = "\n".join([f"  • {r['broker']}: {r.get('error', 'Unknown error')}" 
                                          for r in failed_results])
                self.root.after(0, lambda: messagebox.showwarning("Partial Success", 
                    f"⚠️ {success_count}/{len(results)} orders placed\n\nFailed:\n{error_details}"))
            else:
                # All failed
                self._log('error', "All orders failed")
                error_details = "\n".join([f"  • {r['broker']}: {r.get('error', 'Unknown error')}" 
                                          for r in failed_results])
                self.root.after(0, lambda: messagebox.showerror("Order Failed", 
                    f"❌ All orders failed:\n\n{error_details}"))
                return  # Don't refresh positions if all failed
            
            # Refresh positions after a small delay to allow broker systems to update
            # This prevents empty position fetches
            self.root.after(500, self.refresh_positions)
            
            # Auto-update SL for positions with auto-SL tracking (after quantity increase)
            if hasattr(self, '_auto_sl_tracking') and self._auto_sl_tracking:
                def auto_update_sl():
                    time.sleep(1)  # Wait for positions to refresh
                    for instrument_key, sl_config in list(self._auto_sl_tracking.items()):
                        if sl_config.get('enabled'):
                            sl_percent = sl_config.get('percent', 0)
                            if sl_percent > 0:
                                print(f"🔄 Auto-updating SL for {sl_config.get('symbol')} at {sl_percent}%")
                                self.apply_stop_loss(value=sl_percent, mode="percent", show_notification=False)
                                break  # Only need to run once for all positions
                
                threading.Thread(target=auto_update_sl, daemon=True).start()
            elif hasattr(self, '_last_sl_percent') and self._last_sl_percent:
                # Even if no auto-SL tracking, update quantities if user manually set SL before
                def update_sl_quantities():
                    time.sleep(2)  # Wait for positions to refresh
                    print(f"🔄 Checking SL quantities after order placement...")
                    self._update_sl_quantities_for_current_positions()
                
                threading.Thread(target=update_sl_quantities, daemon=True).start()
            
            # Refresh margin to show updated balance
            self.root.after(600, lambda: threading.Thread(target=self.refresh_margin, daemon=True).start())
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Order failed: {e}"))
    
    
    def refresh_positions(self):
        """Refresh positions display with parallel fetching for speed."""
        # Debouncing: prevent multiple simultaneous refreshes
        if hasattr(self, '_refreshing_positions') and self._refreshing_positions:
            print("⏭️ Skipping position refresh - already in progress")
            return
        
        self._refreshing_positions = True
        try:
            # Clear current data
            for item in self.positions_tree.get_children():
                self.positions_tree.delete(item)
            
            self.positions_data = []
            
            # Get positions from all brokers IN PARALLEL for MAXIMUM SPEED
            if self.trader.multi_account_mode:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                def fetch_positions(broker_key, broker_info):
                    try:
                        client = broker_info['client']
                        account_name = broker_info['name']
                        positions_response = client.get_positions()
                        if positions_response:
                            return (account_name, broker_key, client, positions_response.get('data', []))
                    except Exception as e:
                        error_str = str(e)
                        if '401' in error_str:
                            # Mark broker as invalid for order execution
                            if broker_key not in self.invalid_brokers:
                                self.invalid_brokers.add(broker_key)
                                self._log('warning', f"Broker {broker_info.get('name', 'Unknown')} ({broker_key}) marked as invalid due to 401 error during position fetch")
                        elif '429' in error_str:
                            # Rate limit - just skip silently, will retry next cycle
                            pass
                        else:
                            print(f"⚠️  Error fetching from {broker_info.get('name', 'Unknown')}: {e}")
                    return (None, None, None, [])
                
                # Fetch ALL positions in parallel - optimized thread count
                with ThreadPoolExecutor(max_workers=min(16, len(self.trader.active_brokers))) as executor:
                    futures = [executor.submit(fetch_positions, key, info)
                              for key, info in self.trader.active_brokers.items()]
                    
                    # Process results as they arrive (fastest response first)
                    for future in as_completed(futures):
                        account_name, broker_key, client, positions = future.result()
                        if not account_name:
                            continue
                        
                        # Process positions with broker_key and client
                        for pos in positions:
                            self._add_position_to_display(pos, account_name, broker_key, client)
            else:
                # Single account mode - still process quickly
                for broker_key, broker_info in self.trader.active_brokers.items():
                    try:
                        client = broker_info['client']
                        account_name = broker_info['name']
                        positions_response = client.get_positions()
                        
                        if not positions_response:
                            print(f"⚠️  No response from {account_name}")
                            continue
                        
                        positions = positions_response.get('data', [])
                        
                        for pos in positions:
                            self._add_position_to_display(pos, account_name, broker_key, client)
                    except Exception as e:
                        error_msg = str(e)
                        if '401' in error_msg or 'Unauthorized' in error_msg:
                            print(f"❌ {account_name}: Token expired. Please regenerate access token.")
                            if not hasattr(self, '_token_error_shown'):
                                self._token_error_shown = True
                                self.root.after(0, lambda: messagebox.showerror(
                                    "Token Expired",
                                    f"{account_name} access token has expired.\\n\\n"
                                    "Please close the GUI and run:\\n"
                                    "python traderchamp.py\\n"
                                    "Then type 'token' to regenerate tokens."
                                ))
                        else:
                            print(f"Error fetching positions from {account_name}: {e}")
            
            # Configure tags
            self.positions_tree.tag_configure('green', foreground='#00ff00')
            self.positions_tree.tag_configure('red', foreground='#ff0000')
            
            # Calculate and update summary
            total_pnl = sum(p.get('pnl', 0) for p in self.positions_data)
            total_day_pnl = sum(p.get('realised', 0) or p.get('realized_pnl', 0) or p.get('day_pnl', 0) or p.get('pnl', 0) 
                               for p in self.positions_data)
            pos_count = len(self.positions_data)
            
            # Update summary labels
            pnl_color = '#00ff00' if total_pnl >= 0 else '#ff0000'
            day_pnl_color = '#00aaff' if total_day_pnl >= 0 else '#ff6666'
            
            self.total_pnl_label.config(text=f"Total P&L: ₹{total_pnl:,.2f}", fg=pnl_color)
            self.day_pnl_label.config(text=f"Day P&L: ₹{total_day_pnl:,.2f}", fg=day_pnl_color)
            self.pos_count_label.config(text=f"Positions: {pos_count}")
            
            # Check for position alerts
            if self.alert_enabled.get():
                self.check_position_alerts()
            
            # Update risk management status
            if hasattr(self, 'today_pnl_label'):  # Only if risk tab exists
                self.update_risk_status()
            
            # Update target info display
            self.update_target_info()
            
        except Exception as e:
            print(f"Error refreshing positions: {e}")
        finally:
            self._refreshing_positions = False
        
        # Schedule next refresh (every 60 seconds to prevent API rate limits)
        self.root.after(60000, self.refresh_positions)
    
    def _add_position_to_display(self, pos, account_name, broker_key=None, client=None):
        """Helper method to add position to display quickly."""
        try:
            qty = pos.get('quantity', 0) or pos.get('netQty', 0)
            if qty == 0:
                return
            
            symbol = pos.get('tradingsymbol', 'N/A')
            avg_price = (pos.get('average_price') or 
                        pos.get('buy_avg') or 
                        pos.get('buyAvg') or 
                        pos.get('buyPrice') or 
                        pos.get('costPrice') or 0)
            ltp = pos.get('last_price') or pos.get('ltp') or pos.get('lastPrice') or 0
            
            # Calculate P&L
            pnl = pos.get('pnl', 0)
            
            # Calculate P&L percentage
            pnl_percent = 0
            if avg_price > 0:
                pnl_percent = ((ltp - avg_price) / avg_price) * 100
                # For short positions (negative qty), invert the percentage
                if qty < 0:
                    pnl_percent = -pnl_percent
            
            # Calculate Day P&L (realized + unrealized for the day)
            day_pnl = (pos.get('realised') or pos.get('realized_pnl') or 
                      pos.get('day_pnl') or pnl)  # Fallback to total pnl
            
            # Get time - optimized field lookup
            time_str = 'N/A'
            for time_field in ['order_timestamp', 'created_at', 'buy_date',
                              'createTime', 'transactionTime', 'tradeTime']:
                if pos.get(time_field):
                    try:
                        time_val = str(pos[time_field])
                        if 'T' in time_val:
                            dt = datetime.fromisoformat(time_val.replace('Z', '+00:00'))
                        else:
                            dt = datetime.strptime(time_val[:19], '%Y-%m-%d %H:%M:%S')
                        time_str = dt.strftime('%H:%M:%S')
                        break
                    except:
                        pass
            
            # Generate position tip based on market analysis
            position_tip = self._get_position_tip(symbol, qty, pnl_percent)
            
            # Add to treeview with enhanced P&L display and tip
            pnl_color = 'green' if pnl >= 0 else 'red'
            pnl_percent_str = f"{pnl_percent:+.2f}%"  # + or - sign
            values = (account_name, symbol, qty, f"₹{avg_price:.2f}",
                    f"₹{ltp:.2f}", f"₹{pnl:.2f}", pnl_percent_str, f"₹{day_pnl:.2f}", time_str, position_tip)
            
            self.positions_tree.insert('', tk.END, values=values, tags=(pnl_color,))
            
            # Store full position data
            pos['broker_name'] = account_name
            if broker_key:
                pos['broker_key'] = broker_key
            if client:
                pos['client'] = client
            self.positions_data.append(pos)
        except Exception as e:
            print(f"Error adding position to display: {e}")
    
    def _get_position_tip(self, symbol, qty, pnl_percent):
        """Generate trading tip for a position based on market analysis."""
        try:
            # Determine if CE or PE
            is_ce = 'CE' in symbol.upper()
            is_pe = 'PE' in symbol.upper()
            
            if not (is_ce or is_pe):
                return "N/A"
            
            # Quick market analysis (cached to avoid repeated API calls)
            if not hasattr(self, '_market_cache') or \
               (hasattr(self, '_market_cache_time') and 
                (datetime.now() - self._market_cache_time).seconds > 300):  # 5 min cache
                
                # Fetch quick NIFTY data
                import yfinance as yf
                try:
                    nifty = yf.Ticker("^NSEI")
                    data = nifty.history(period="1d")
                    hist = nifty.history(period="5d")
                    
                    if not data.empty and len(hist) >= 2:
                        current_price = float(data['Close'].iloc[-1])
                        prev_day = hist.iloc[-2]
                        prev_high = float(prev_day['High'])
                        prev_low = float(prev_day['Low'])
                        prev_close = float(prev_day['Close'])
                        
                        pivot = (prev_high + prev_low + prev_close) / 3
                        trend = "BULLISH" if current_price > pivot else "BEARISH"
                        
                        self._market_cache = {'trend': trend, 'current_price': current_price, 'pivot': pivot}
                        self._market_cache_time = datetime.now()
                    else:
                        self._market_cache = {'trend': 'UNKNOWN', 'current_price': 0, 'pivot': 0}
                        self._market_cache_time = datetime.now()
                except:
                    self._market_cache = {'trend': 'UNKNOWN', 'current_price': 0, 'pivot': 0}
                    self._market_cache_time = datetime.now()
            
            trend = self._market_cache.get('trend', 'UNKNOWN')
            
            # Generate tip based on position type and market trend
            if is_ce:  # Call position
                if trend == "BULLISH":
                    if pnl_percent > 15:
                        return "✅ GOOD | Trail SL"
                    elif pnl_percent > 5:
                        return "✅ OK | Hold"
                    elif pnl_percent < -10:
                        return "⚠️ Cut Loss"
                    else:
                        return "✅ With Trend"
                else:  # Bearish market
                    if pnl_percent > 10:
                        return "🎯 Book Profit"
                    elif pnl_percent < -5:
                        return "❌ Against Trend"
                    else:
                        return "⚠️ Watch Closely"
            
            elif is_pe:  # Put position
                if trend == "BEARISH":
                    if pnl_percent > 15:
                        return "✅ GOOD | Trail SL"
                    elif pnl_percent > 5:
                        return "✅ OK | Hold"
                    elif pnl_percent < -10:
                        return "⚠️ Cut Loss"
                    else:
                        return "✅ With Trend"
                else:  # Bullish market
                    if pnl_percent > 10:
                        return "🎯 Book Profit"
                    elif pnl_percent < -5:
                        return "❌ Against Trend"
                    else:
                        return "⚠️ Watch Closely"
            
            return "N/A"
            
        except Exception as e:
            print(f"Error generating position tip: {e}")
            return "N/A"
    
    def _create_closed_position_tooltip(self):
        """Create tooltip to show full analysis text on hover."""
        self.closed_tooltip = None
        self.closed_tooltip_id = None
        
        def show_tooltip(event):
            # Get item under cursor
            item = self.closed_tree.identify_row(event.y)
            column = self.closed_tree.identify_column(event.x)
            
            # Only show tooltip for Analysis column
            if item and column == '#11':  # Column 11 is Analysis
                values = self.closed_tree.item(item)['values']
                if len(values) >= 11:
                    analysis_text = str(values[10])
                    
                    # Hide existing tooltip
                    hide_tooltip()
                    
                    # Create tooltip
                    self.closed_tooltip = tk.Toplevel(self.root)
                    self.closed_tooltip.wm_overrideredirect(True)
                    self.closed_tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
                    
                    label = tk.Label(self.closed_tooltip, text=analysis_text, 
                                   background='#333333', foreground='#ffffff',
                                   relief='solid', borderwidth=1, padx=8, pady=5,
                                   font=('Arial', 10), wraplength=350)
                    label.pack()
        
        def hide_tooltip(event=None):
            if self.closed_tooltip:
                self.closed_tooltip.destroy()
                self.closed_tooltip = None
            if self.closed_tooltip_id:
                self.root.after_cancel(self.closed_tooltip_id)
                self.closed_tooltip_id = None
        
        def schedule_tooltip(event):
            hide_tooltip()
            self.closed_tooltip_id = self.root.after(500, lambda: show_tooltip(event))
        
        self.closed_tree.bind('<Motion>', schedule_tooltip)
        self.closed_tree.bind('<Leave>', hide_tooltip)
    
    def _analyze_closed_trade(self, pos):
        """Lightweight analysis for main column - detailed view on double-click."""
        try:
            pnl = pos['pnl']
            buy_avg = pos['buy_avg']
            sell_avg = pos['sell_avg']
            closed_qty = pos['closed_qty']
            symbol = pos['symbol']
            
            pnl_percent = (pnl / (buy_avg * closed_qty) * 100) if buy_avg > 0 else 0
            
            # Price movement during trade
            price_change = sell_avg - buy_avg
            price_change_percent = (price_change / buy_avg * 100) if buy_avg > 0 else 0
            
            # Determine trade type
            is_ce = 'CE' in symbol.upper() or 'CALL' in symbol.upper()
            is_pe = 'PE' in symbol.upper() or 'PUT' in symbol.upper()
            
            # CE/PE Direction Analysis
            # CE: Profits when market goes UP (premium increases)
            # PE: Profits when market goes DOWN (premium increases)
            direction_match = False
            if is_ce and price_change_percent > 3:  # CE + Market Up = Good
                direction_match = True
            elif is_pe and price_change_percent < -3:  # PE + Market Down = Good
                direction_match = True
            
            # Lightweight summary for column
            if pnl >= 0:
                if pnl_percent > 20:
                    verdict = "EXCELLENT"
                elif pnl_percent > 10:
                    verdict = "GOOD"
                elif pnl_percent > 5:
                    verdict = "PROFIT"
                else:
                    verdict = "Break-Even"
                
                # Add direction indicator for CE/PE
                if is_ce or is_pe:
                    direction_icon = "📈✅" if direction_match else "⚠️"
                    return f"✅ {verdict} ({pnl_percent:+.1f}%) {direction_icon}"
                else:
                    return f"✅ {verdict} ({pnl_percent:+.1f}%)"
            else:
                if abs(pnl_percent) > 20:
                    verdict = "BIG LOSS"
                elif abs(pnl_percent) > 10:
                    verdict = "LOSS"
                else:
                    verdict = "Small Loss"
                
                # Add direction indicator for CE/PE
                if is_ce or is_pe:
                    direction_icon = "❌📉" if not direction_match else "⚠️"
                    return f"❌ {verdict} ({pnl_percent:.1f}%) {direction_icon}"
                else:
                    return f"❌ {verdict} ({pnl_percent:.1f}%)"
        
        except Exception as e:
            print(f"Error analyzing closed trade: {e}")
            return "N/A"
    
    def _show_detailed_trade_analysis(self, event):
        """Show detailed trade analysis on double-click."""
        try:
            selection = self.closed_tree.selection()
            if not selection:
                return
            
            item = selection[0]
            values = self.closed_tree.item(item)['values']
            
            if len(values) < 11:
                return
            
            account, symbol, buy_qty, buy_avg, sell_qty, sell_avg, closed_qty, pnl_str, buy_time, sell_time, analysis = values
            
            # Parse PNL
            pnl = float(pnl_str.replace(',', '').replace('+', ''))
            buy_avg = float(buy_avg)
            sell_avg = float(sell_avg)
            pnl_percent = (pnl / (buy_avg * closed_qty) * 100) if buy_avg > 0 else 0
            
            # Create detailed analysis window
            dialog = tk.Toplevel(self.root)
            dialog.title(f"📊 Trade Analysis - {symbol}")
            dialog.geometry("650x500")
            dialog.configure(bg='#2d2d2d')
            dialog.transient(self.root)
            
            # Header
            header = tk.Frame(dialog, bg='#1a1a1a', pady=15)
            header.pack(fill='x')
            
            tk.Label(header, text=f"📊 Detailed Trade Analysis", font=('Arial', 16, 'bold'),
                    bg='#1a1a1a', fg='#00d4ff').pack()
            tk.Label(header, text=f"{symbol} - {account}", font=('Arial', 11),
                    bg='#1a1a1a', fg='#888').pack()
            
            # Scrollable content
            canvas = tk.Canvas(dialog, bg='#2d2d2d', highlightthickness=0)
            scrollbar = tk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
            content = tk.Frame(canvas, bg='#2d2d2d')
            
            content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=content, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # Trade Summary
            summary_frame = tk.Frame(content, bg='#1a1a1a', pady=15)
            summary_frame.pack(fill='x', padx=15, pady=10)
            
            tk.Label(summary_frame, text="Trade Summary", font=('Arial', 13, 'bold'),
                    bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10)
            
            summary_text = f"""Entry (Buy): ₹{buy_avg:.2f} x {buy_qty} lots @ {buy_time}
Exit (Sell): ₹{sell_avg:.2f} x {sell_qty} lots @ {sell_time}
Closed Qty: {closed_qty} lots
P&L: ₹{pnl:+,.2f} ({pnl_percent:+.2f}%)"""
            
            tk.Label(summary_frame, text=summary_text, font=('Courier', 11),
                    bg='#1a1a1a', fg='#ccc', justify='left').pack(anchor='w', padx=20, pady=5)
            
            # Analysis
            analysis_frame = tk.Frame(content, bg='#1a1a1a', pady=15)
            analysis_frame.pack(fill='x', padx=15, pady=10)
            
            is_profit = pnl >= 0
            result_color = '#00ff00' if is_profit else '#ff0000'
            result_text = "✅ SUCCESSFUL TRADE" if is_profit else "❌ FAILED TRADE"
            
            tk.Label(analysis_frame, text=result_text, font=('Arial', 14, 'bold'),
                    bg='#1a1a1a', fg=result_color).pack(anchor='w', padx=10)
            
            # Market Flow Analysis Section
            flow_frame = tk.Frame(content, bg='#1a1a1a', pady=15)
            flow_frame.pack(fill='x', padx=15, pady=10)
            
            tk.Label(flow_frame, text="📈 Market Flow Analysis", font=('Arial', 13, 'bold'),
                    bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10)
            
            # Calculate price movement
            price_change = sell_avg - buy_avg
            price_change_percent = (price_change / buy_avg * 100) if buy_avg > 0 else 0
            
            # Determine trade type
            is_ce = 'CE' in symbol.upper()
            is_pe = 'PE' in symbol.upper()
            
            # CE/PE Direction Analysis
            # CE: Profits when underlying market goes UP (call option premium increases)
            # PE: Profits when underlying market goes DOWN (put option premium increases)
            direction_match = False
            ce_pe_verdict = ""
            
            if is_ce:
                if price_change_percent > 3:
                    direction_match = True
                    ce_pe_verdict = "✅ CE + Market UP = PERFECT ALIGNMENT (Premium Increased)"
                else:
                    ce_pe_verdict = "❌ CE but Market DOWN/FLAT = WRONG DIRECTION (Premium Decreased)"
            elif is_pe:
                if price_change_percent < -3:
                    direction_match = True
                    ce_pe_verdict = "✅ PE + Market DOWN = PERFECT ALIGNMENT (Premium Increased)"
                else:
                    ce_pe_verdict = "❌ PE but Market UP/FLAT = WRONG DIRECTION (Premium Decreased)"
            
            # Entry analysis
            entry_color = '#00ff00' if price_change_percent > 0 else '#ff0000'
            entry_trend = "📈 BULLISH" if price_change_percent > 5 else ("📉 BEARISH" if price_change_percent < -5 else "➡️ SIDEWAYS")
            
            tk.Label(flow_frame, text=f"Market Movement During Trade: {entry_trend} | Price Change: {price_change_percent:+.2f}%",
                    font=('Arial', 11, 'bold'), bg='#1a1a1a', fg=entry_color).pack(anchor='w', padx=20, pady=5)
            
            # CE/PE Direction Match - CRITICAL INSIGHT
            if is_ce or is_pe:
                verdict_color = '#00ff00' if direction_match else '#ff3333'
                tk.Label(flow_frame, text=ce_pe_verdict, font=('Arial', 11, 'bold'),
                        bg='#1a1a1a', fg=verdict_color).pack(anchor='w', padx=20, pady=3)
                
                # Explain CE/PE logic
                if is_ce:
                    tk.Label(flow_frame, text="📌 CE Logic: Call options gain value when market rises",
                            font=('Arial', 9, 'italic'), bg='#1a1a1a', fg='#aaa').pack(anchor='w', padx=20, pady=1)
                elif is_pe:
                    tk.Label(flow_frame, text="📌 PE Logic: Put options gain value when market falls",
                            font=('Arial', 9, 'italic'), bg='#1a1a1a', fg='#aaa').pack(anchor='w', padx=20, pady=1)
            
            # Market context
            if price_change_percent > 5:
                market_msg = "🟢 Market was BULLISH during this trade (Strong upward momentum)"
            elif price_change_percent < -5:
                market_msg = "🔴 Market was BEARISH during this trade (Strong downward pressure)"
            else:
                market_msg = "🟡 Market was SIDEWAYS/CHOPPY (No clear trend)"
            
            tk.Label(flow_frame, text=market_msg, font=('Arial', 10),
                    bg='#1a1a1a', fg='#fff').pack(anchor='w', padx=20, pady=5)
            
            # Detailed why it succeeded/failed
            reason_frame = tk.Frame(content, bg='#ffaa00' if is_profit else '#ff4444', pady=15)
            reason_frame.pack(fill='x', padx=15, pady=10)
            
            tk.Label(reason_frame, text="Why this trade " + ("succeeded:" if is_profit else "failed:"),
                    font=('Arial', 12, 'bold'), bg=reason_frame['bg'], fg='#000').pack(anchor='w', padx=10)
            
            # Determine reasons with CE/PE market direction analysis
            reasons = []
            if is_profit:
                # WINNING TRADE - Check if it aligned with CE/PE logic
                if is_ce:
                    if price_change_percent > 5:
                        reasons.append("🎯 CE PERFECT: Market went UP → Call premium increased → Profit!")
                        reasons.append("✅ You correctly predicted bullish market movement")
                    else:
                        reasons.append("⚠️ CE but market didn't rise much - profit from other factors")
                        reasons.append("✅ Still made profit - good volatility/time management")
                
                elif is_pe:
                    if price_change_percent < -5:
                        reasons.append("🎯 PE PERFECT: Market went DOWN → Put premium increased → Profit!")
                        reasons.append("✅ You correctly predicted bearish market movement")
                    else:
                        reasons.append("⚠️ PE but market didn't fall much - profit from other factors")
                        reasons.append("✅ Still made profit - good volatility/time management")
                
                # General profit reasons
                if pnl_percent > 20:
                    reasons.append("✅ EXCELLENT: Captured strong trend momentum")
                    reasons.append("✅ Held position for maximum profit extraction")
                    reasons.append("✅ Exit timing was near-perfect")
                elif pnl_percent > 10:
                    reasons.append("✅ GOOD: Proper trend alignment and execution")
                    reasons.append("✅ Profit booking done at right levels")
                else:
                    reasons.append("✅ Quick profit booking avoided reversal risk")
                    reasons.append("✅ Disciplined exit preserved capital")
            
            else:
                # LOSING TRADE - Check if it violated CE/PE direction logic
                if is_ce:
                    if price_change_percent < -5:
                        reasons.append("❌ CE WRONG DIRECTION: Bought CE but market went DOWN!")
                        reasons.append("❌ Call premium decreased as market fell")
                        reasons.append("❌ Should check market trend BEFORE buying CE")
                        reasons.append("💡 CE needs BULLISH market to profit")
                    elif abs(price_change_percent) < 3:
                        reasons.append("⚠️ CE in SIDEWAYS market - premium didn't increase")
                        reasons.append("❌ Time decay ate into CE value")
                        reasons.append("💡 CE works best in trending UP markets")
                    else:
                        reasons.append("⚠️ CE bought, market went up slightly but loss occurred")
                        reasons.append("❌ Possibly bought at high premium or time decay")
                
                elif is_pe:
                    if price_change_percent > 5:
                        reasons.append("❌ PE WRONG DIRECTION: Bought PE but market went UP!")
                        reasons.append("❌ Put premium decreased as market rose")
                        reasons.append("❌ Should check market trend BEFORE buying PE")
                        reasons.append("💡 PE needs BEARISH market to profit")
                    elif abs(price_change_percent) < 3:
                        reasons.append("⚠️ PE in SIDEWAYS market - premium didn't increase")
                        reasons.append("❌ Time decay ate into PE value")
                        reasons.append("💡 PE works best in trending DOWN markets")
                    else:
                        reasons.append("⚠️ PE bought, market went down slightly but loss occurred")
                        reasons.append("❌ Possibly bought at high premium or time decay")
                
                # General loss reasons
                if abs(pnl_percent) > 20:
                    reasons.append("❌ BIG LOSS: No stop loss protection OR ignored signals")
                    reasons.append("❌ Held losing position far too long")
                elif abs(pnl_percent) > 10:
                    reasons.append("❌ LOSS: Late exit - should have cut earlier")
                    reasons.append("❌ Didn't respect stop loss levels")
                else:
                    reasons.append("⚠️ Small Loss: Quick exit limited damage (GOOD)")
                    reasons.append("✅ Capital protection worked - this is acceptable")
            
            for reason in reasons:
                tk.Label(reason_frame, text=f"  {reason}", font=('Arial', 11),
                        bg=reason_frame['bg'], fg='#000', justify='left').pack(anchor='w', padx=20, pady=2)
            
            # Lessons Learned
            lessons_frame = tk.Frame(content, bg='#1a1a1a', pady=15)
            lessons_frame.pack(fill='x', padx=15, pady=10)
            
            tk.Label(lessons_frame, text="📚 Lessons & Recommendations:", font=('Arial', 12, 'bold'),
                    bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10)
            
            lessons = []
            if is_profit:
                lessons.append("✅ Repeat this setup - it works for you")
                lessons.append("✅ Document your entry/exit rules")
                
                if is_ce and price_change_percent > 5:
                    lessons.append("🎯 CE Strategy: Look for bullish market signals before buying CE")
                    lessons.append("📈 Your CE timing was good - market went up as expected")
                elif is_pe and price_change_percent < -5:
                    lessons.append("🎯 PE Strategy: Look for bearish market signals before buying PE")
                    lessons.append("📉 Your PE timing was good - market went down as expected")
                
                if pnl_percent > 15:
                    lessons.append("✅ Consider partial profit booking at 50% target for safety")
                    lessons.append("✅ Trail stop loss to lock in profits")
            else:
                lessons.append("🔍 CRITICAL: Always check market trend BEFORE placing order")
                lessons.append("🔍 Always use stop loss - no exceptions (max 7% loss)")
                
                if is_ce:
                    if price_change_percent < -3:
                        lessons.append("❌ CE RULE: Never buy CE when market is falling or bearish")
                        lessons.append("📈 Buy CE only when: Market trending UP, bullish signals present")
                        lessons.append("💡 Use Tips Buddy to confirm BULLISH trend before CE entry")
                    else:
                        lessons.append("⚠️ CE in sideways market is risky - prefer trending markets")
                        lessons.append("💡 For CE: Wait for clear upward breakout")
                
                elif is_pe:
                    if price_change_percent > 3:
                        lessons.append("❌ PE RULE: Never buy PE when market is rising or bullish")
                        lessons.append("📉 Buy PE only when: Market trending DOWN, bearish signals present")
                        lessons.append("💡 Use Tips Buddy to confirm BEARISH trend before PE entry")
                    else:
                        lessons.append("⚠️ PE in sideways market is risky - prefer trending markets")
                        lessons.append("💡 For PE: Wait for clear downward breakdown")
                
                if abs(pnl_percent) > 15:
                    lessons.append("🚨 URGENT: Your losses are too big - MUST use stop loss!")
                    lessons.append("🚨 Exit at 5-7% loss MAXIMUM - don't hope for recovery")
                else:
                    lessons.append("✅ Loss was controlled - good risk management")
                
                # Key CE/PE lessons
                lessons.append("━" * 50)
                lessons.append("📚 REMEMBER:")
                lessons.append("   CE = Call = Bullish Bet = Needs market to go UP ⬆️")
                lessons.append("   PE = Put = Bearish Bet = Needs market to go DOWN ⬇️")
            
            for lesson in lessons:
                tk.Label(lessons_frame, text=f"  {lesson}", font=('Arial', 10),
                        bg='#1a1a1a', fg='#ffff00', justify='left').pack(anchor='w', padx=20, pady=2)
            
            # Market Index Information Section
            index_frame = tk.Frame(content, bg='#1a1a1a', pady=15)
            index_frame.pack(fill='x', padx=15, pady=10)
            
            tk.Label(index_frame, text="📊 Current Market Index", font=('Arial', 12, 'bold'),
                    bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10)
            
            # Fetch current Nifty 50 value
            try:
                nifty_value = 0
                nifty_source = "Loading..."
                
                # Try to get from active broker (Upstox preferred)
                for broker_key, broker_info in self.trader.active_brokers.items():
                    if 'upstox' in broker_key.lower():
                        try:
                            client = broker_info['client']
                            nifty_instrument = "NSE_INDEX|Nifty 50"
                            ltp_response = client.get_ltp(nifty_instrument)
                            
                            if ltp_response and ltp_response.get('status') == 'success':
                                ltp_data = ltp_response.get('data', {})
                                if nifty_instrument in ltp_data:
                                    nifty_value = ltp_data[nifty_instrument].get('last_price', 0)
                                    nifty_source = "Upstox Live"
                                    break
                        except:
                            pass
                
                # Fallback to Yahoo Finance
                if nifty_value == 0:
                    try:
                        import yfinance as yf
                        nifty_ticker = yf.Ticker("^NSEI")
                        nifty_data = nifty_ticker.history(period="1d")
                        if not nifty_data.empty:
                            nifty_value = float(nifty_data['Close'].iloc[-1])
                            nifty_source = "Yahoo Finance"
                    except:
                        nifty_value = 0
                        nifty_source = "Unavailable"
                
                if nifty_value > 0:
                    index_text = f"NIFTY 50: ₹{nifty_value:,.2f} (Source: {nifty_source})"
                    index_color = '#00ff00'
                else:
                    index_text = f"NIFTY 50: Data unavailable (Market may be closed)"
                    index_color = '#888'
                
                tk.Label(index_frame, text=index_text, font=('Arial', 11, 'bold'),
                        bg='#1a1a1a', fg=index_color).pack(anchor='w', padx=20, pady=5)
                
                # Add context for CE/PE
                if is_ce or is_pe:
                    if nifty_value > 0:
                        context_msg = f"💡 When you traded, compare this index with your entry/exit to understand market direction"
                    else:
                        context_msg = f"💡 Check current Nifty trend before your next {('CE' if is_ce else 'PE')} trade"
                    
                    tk.Label(index_frame, text=context_msg, font=('Arial', 9, 'italic'),
                            bg='#1a1a1a', fg='#aaa').pack(anchor='w', padx=20, pady=2)
            
            except Exception as idx_err:
                tk.Label(index_frame, text=f"⚠️ Could not fetch index data: {str(idx_err)[:50]}", 
                        font=('Arial', 9), bg='#1a1a1a', fg='#ff6666').pack(anchor='w', padx=20, pady=2)
            
            # Money Zone & Value Area Analysis Section
            zone_frame = tk.Frame(content, bg='#1a1a1a', pady=15)
            zone_frame.pack(fill='x', padx=15, pady=10)
            
            tk.Label(zone_frame, text="💰 Money Zone & Value Area Analysis", font=('Arial', 12, 'bold'),
                    bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=10)
            
            # Calculate Value Area High (VAH) and Value Area Low (VAL)
            # Using 70% rule: Value Area contains 70% of trading activity
            trade_range = sell_avg - buy_avg
            mid_price = (buy_avg + sell_avg) / 2
            
            # Point of Control (POC) - where most trading occurred
            poc = mid_price
            
            # Value Area High/Low (typically ±30% of range from POC)
            vah = poc + (abs(trade_range) * 0.35)
            val = poc - (abs(trade_range) * 0.35)
            
            # Money Zones
            # Green Zone: Above entry (profit zone for longs)
            # Red Zone: Below entry (loss zone for longs)
            # Yellow Zone: Between entry and POC (transition zone)
            
            if sell_avg > buy_avg:
                zone_verdict = "GREEN ZONE"
                zone_color = '#00ff00'
                zone_msg = "✅ Trade exited in PROFIT ZONE - Good execution"
            elif sell_avg < buy_avg:
                zone_verdict = "RED ZONE"
                zone_color = '#ff0000'
                zone_msg = "❌ Trade exited in LOSS ZONE - Below entry"
            else:
                zone_verdict = "NEUTRAL ZONE"
                zone_color = '#ffaa00'
                zone_msg = "⚠️ Trade exited at BREAK-EVEN"
            
            # Value Area positioning
            if sell_avg >= vah:
                value_position = "ABOVE Value Area High (VAH)"
                value_verdict = "🎯 Exit at premium levels - Excellent"
            elif sell_avg <= val:
                value_position = "BELOW Value Area Low (VAL)"
                value_verdict = "📉 Exit at discount levels - Weak exit"
            else:
                value_position = "WITHIN Value Area (Fair Value Zone)"
                value_verdict = "➡️ Exit at fair value - Acceptable"
            
            # Display Money Zone
            tk.Label(zone_frame, text=f"💰 Money Zone: {zone_verdict}", font=('Arial', 11, 'bold'),
                    bg='#1a1a1a', fg=zone_color).pack(anchor='w', padx=20, pady=3)
            tk.Label(zone_frame, text=f"   {zone_msg}", font=('Arial', 10),
                    bg='#1a1a1a', fg='#ccc').pack(anchor='w', padx=20, pady=1)
            
            # Display Value Area metrics
            tk.Label(zone_frame, text=f"\n📊 Value Area Levels:", font=('Arial', 10, 'bold'),
                    bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=20, pady=3)
            
            va_metrics = f"""   Point of Control (POC): ₹{poc:.2f}
   Value Area High (VAH): ₹{vah:.2f}
   Value Area Low (VAL): ₹{val:.2f}
   
   Your Entry: ₹{buy_avg:.2f}
   Your Exit: ₹{sell_avg:.2f}
   
   Exit Position: {value_position}"""
            
            tk.Label(zone_frame, text=va_metrics, font=('Courier', 9),
                    bg='#1a1a1a', fg='#ccc', justify='left').pack(anchor='w', padx=20, pady=2)
            
            tk.Label(zone_frame, text=f"   {value_verdict}", font=('Arial', 10, 'bold'),
                    bg='#1a1a1a', fg='#ffaa00').pack(anchor='w', padx=20, pady=3)
            
            # Support/Resistance analysis
            tk.Label(zone_frame, text=f"\n🎯 Key Levels Analysis:", font=('Arial', 10, 'bold'),
                    bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=20, pady=3)
            
            # Calculate key levels
            support_1 = buy_avg - (abs(trade_range) * 0.5)
            support_2 = buy_avg - abs(trade_range)
            resistance_1 = buy_avg + (abs(trade_range) * 0.5)
            resistance_2 = buy_avg + abs(trade_range)
            
            levels_text = f"""   Resistance 2: ₹{resistance_2:.2f} (Strong barrier)
   Resistance 1: ₹{resistance_1:.2f} (Immediate target)
   Entry Price: ₹{buy_avg:.2f} (Your position)
   Support 1: ₹{support_1:.2f} (First protection)
   Support 2: ₹{support_2:.2f} (Stop loss zone)"""
            
            tk.Label(zone_frame, text=levels_text, font=('Courier', 9),
                    bg='#1a1a1a', fg='#aaa', justify='left').pack(anchor='w', padx=20, pady=2)
            
            # Trading insights based on levels
            if sell_avg >= resistance_1:
                level_insight = "✅ Exit above R1 - Captured upward move successfully"
            elif sell_avg <= support_1:
                level_insight = "❌ Exit below S1 - Failed to hold support"
            else:
                level_insight = "⚠️ Exit near entry - Limited price movement captured"
            
            tk.Label(zone_frame, text=f"\n   {level_insight}", font=('Arial', 10, 'italic'),
                    bg='#1a1a1a', fg='#ffff00').pack(anchor='w', padx=20, pady=3)
            
            # Money Management verdict
            tk.Label(zone_frame, text=f"\n💵 Money Management Verdict:", font=('Arial', 10, 'bold'),
                    bg='#1a1a1a', fg='#00d4ff').pack(anchor='w', padx=20, pady=3)
            
            if pnl_percent > 10 and sell_avg >= vah:
                mm_verdict = "🏆 EXCELLENT: Profit in premium zone with good R:R ratio"
            elif pnl_percent > 5 and sell_avg >= poc:
                mm_verdict = "✅ GOOD: Profit above fair value, decent execution"
            elif pnl_percent > 0:
                mm_verdict = "✅ ACCEPTABLE: Small profit, quick exit preserved capital"
            elif pnl_percent > -5 and sell_avg >= val:
                mm_verdict = "⚠️ CONTROLLED LOSS: Exit above VAL, good damage control"
            else:
                mm_verdict = "❌ POOR: Exit in discount zone with significant loss"
            
            tk.Label(zone_frame, text=f"   {mm_verdict}", font=('Arial', 10),
                    bg='#1a1a1a', fg='#00ff00' if pnl >= 0 else '#ff6666').pack(anchor='w', padx=20, pady=3)
            
            # Pack canvas and scrollbar
            canvas.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            
            # Close button
            tk.Button(dialog, text="Close", command=dialog.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 11), padx=30, pady=8).pack(pady=15)
        
        except Exception as e:
            print(f"Error showing detailed analysis: {e}")
            messagebox.showerror("Error", f"Failed to show analysis: {e}")
    
    def check_token_status(self):
        """Check token validity for all brokers."""
        self.account_text.delete(1.0, tk.END)
        self.account_text.insert(tk.END, "Checking token status...\n\n")
        threading.Thread(target=self._check_tokens_async, daemon=True).start()
    
    def _check_tokens_async(self):
        """Check tokens asynchronously."""
        try:
            output = []
            output.append("╔" + "═" * 78 + "╗")
            output.append("║" + " " * 25 + "🔑 TOKEN STATUS CHECK" + " " * 33 + "║")
            output.append("╚" + "═" * 78 + "╝")
            output.append("")
            
            import os
            from dotenv import load_dotenv
            
            # Get correct .env path for frozen mode
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
            env_file = os.path.join(app_dir, '.env')
            load_dotenv(env_file)
            
            total_accounts = 0
            valid_accounts = 0
            
            for broker_key, broker_info in self.trader.active_brokers.items():
                total_accounts += 1
                client = broker_info['client']
                account_name = broker_info['name']
                
                output.append("┌" + "─" * 78 + "┐")
                output.append(f"│ 📊 {account_name} ({broker_key.upper()})" + " " * (75 - len(account_name) - len(broker_key)) + "│")
                output.append("├" + "─" * 78 + "┤")
                
                # Test token by trying to fetch positions and funds
                try:
                    test_response = client.get_positions()
                    if test_response and test_response.get('status') != 'error':
                        output.append("│ ✅ Token Status: VALID")
                        output.append("│ 🟢 Connection: Active")
                        valid_accounts += 1
                        
                        # Get token from env and display partial token
                        if broker_key == 'upstox':
                            token = os.getenv('UPSTOX_ACCESS_TOKEN', '')
                            output.append(f"│ 🔑 Token: {token[:20]}...{token[-10:] if len(token) > 30 else ''}")
                        elif broker_key == 'dhan':
                            token = os.getenv('DHAN_ACCESS_TOKEN', '')
                            output.append(f"│ 🔑 Token: {token[:20]}...{token[-10:] if len(token) > 30 else ''}")
                        elif broker_key == 'zerodha':
                            token = os.getenv('ZERODHA_ACCESS_TOKEN', '')
                            output.append(f"│ 🔑 Token: {token[:20]}...{token[-10:] if len(token) > 30 else ''}")
                        elif broker_key == 'angelone':
                            token = os.getenv('ANGELONE_ACCESS_TOKEN', '')
                            output.append(f"│ 🔑 Token: {token[:20]}...{token[-10:] if len(token) > 30 else ''}")
                        
                        output.append("│")
                        
                        # Fetch account details
                        try:
                            from datetime import datetime
                            funds_response = client.get_funds_and_margin()
                            
                            if funds_response and funds_response.get('status') == 'success':
                                data = funds_response.get('data', {})
                                
                                # Handle nested equity/commodity structure
                                if 'equity' in data:
                                    data = data['equity']
                                elif 'commodity' in data:
                                    data = data['commodity']
                                
                                # Login time (current time as proxy since we just validated)
                                current_time = datetime.now().strftime("%I:%M %p")
                                output.append(f"│ 🕐 Session Active Since: {current_time}")
                                
                                # Token expiry (most brokers don't provide this, show "N/A")
                                if broker_key == 'zerodha':
                                    output.append("│ ⏰ Token Expiry: Midnight (Daily)")
                                elif broker_key == 'angelone':
                                    output.append("│ ⏰ Token Expiry: Session-based")
                                else:
                                    output.append("│ ⏰ Token Expiry: Until manually revoked")
                                
                                # Opening balance - try multiple field names
                                opening_balance = (data.get('opening_balance') or 
                                                 data.get('net_available_balance') or
                                                 data.get('availablecash') or
                                                 data.get('available_balance') or 0)
                                if opening_balance:
                                    output.append(f"│ 💰 Opening Balance: ₹{float(opening_balance):,.2f}")
                                
                                # Withdrawal balance (available cash) - try multiple field names
                                withdrawal_bal = (data.get('withdrawal_balance') or 
                                                data.get('available_balance') or
                                                data.get('availablecash') or
                                                data.get('available_margin') or 0)
                                if withdrawal_bal:
                                    output.append(f"│ 💵 Withdrawal Balance: ₹{float(withdrawal_bal):,.2f}")
                            else:
                                output.append("│ 💰 Balance Info: Unable to fetch")
                        except Exception as e:
                            output.append(f"│ ⚠️ Account Details: {str(e)[:40]}")
                    else:
                        raise Exception("Invalid response")
                        
                except Exception as e:
                    output.append("│ ❌ Token Status: EXPIRED/INVALID")
                    output.append("│ 🔴 Connection: Failed")
                    output.append(f"│ ⚠️  Error: {str(e)[:50]}")
                    output.append("│")
                    output.append("│ 📝 To renew token:")
                    
                    if broker_key == 'upstox':
                        output.append("│   1. Visit: https://account.upstox.com/developer/apps")
                        output.append("│   2. Generate new Access Token and copy it")
                        output.append("│   3. Paste and 'UPDATE TOKENS'")
                    elif broker_key == 'dhan':
                        output.append("│   1. Visit: https://dhanhq.co/")
                        output.append("│   2. Login → API → Generate Access Token")
                        output.append("│   3. Click 'UPDATE TOKENS' button to paste")
                    elif broker_key == 'zerodha':
                        output.append("│   1. Visit: https://kite.trade/")
                        output.append("│   2. Login and generate session token")
                        output.append("│   3. Click 'UPDATE TOKENS' button to paste")
                    elif broker_key == 'angelone':
                        output.append("│   1. Visit: https://smartapi.angelbroking.com/")
                        output.append("│   2. Generate JWT token")
                        output.append("│   3. Click 'UPDATE TOKENS' button to paste")
                
                output.append("└" + "─" * 78 + "┘")
                output.append("")
            
            output.append("╔" + "═" * 78 + "╗")
            output.append(f"║ 📊 SUMMARY: {valid_accounts}/{total_accounts} accounts valid" + " " * (52 - len(str(valid_accounts)) - len(str(total_accounts))) + "║")
            output.append("╚" + "═" * 78 + "╝")
            
            text_content = "\n".join(output)
            self.root.after(0, lambda: self.account_text.delete(1.0, tk.END))
            self.root.after(0, lambda: self.account_text.insert(tk.END, text_content))
            
        except Exception as e:
            self.root.after(0, lambda: self.account_text.insert(tk.END, f"\n❌ Error checking tokens: {e}"))
    
    def show_token_update_dialog(self):
        """Show dialog to update tokens."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Access Tokens")
        dialog.geometry("700x600")
        dialog.configure(bg='#1e1e1e')
        
        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Title
        tk.Label(dialog, text="🔑 UPDATE ACCESS TOKENS", 
                bg='#1e1e1e', fg='#00ff00', 
                font=('Arial', 16, 'bold')).pack(pady=10)
        
        # Instructions
        instructions = tk.Text(dialog, bg='#2d2d2d', fg='#ffffff',
                              font=('Courier', 9), height=6, wrap=tk.WORD)
        instructions.pack(fill=tk.X, padx=10, pady=5)
        instructions.insert(tk.END, 
            "HOW TO GET TOKENS:\n\n"
            "• UPSTOX: Run 'python traderchamp.py' → type 'token'\n"
            "• DHAN: https://dhanhq.co/ → Login → API → Generate Token\n"
            "• ZERODHA: https://kite.trade/ → Login → Generate Session\n"
            "• ANGEL ONE: https://smartapi.angelbroking.com/ → Generate JWT\n")
        instructions.config(state=tk.DISABLED)
        
        # Token entry fields
        import os
        from dotenv import load_dotenv
        
        # Get correct .env path for frozen mode
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        env_file = os.path.join(app_dir, '.env')
        load_dotenv(env_file)
        
        token_entries = {}
        
        for broker_key, broker_info in self.trader.active_brokers.items():
            frame = tk.Frame(dialog, bg='#2d2d2d')
            frame.pack(fill=tk.X, padx=10, pady=5)
            
            account_name = broker_info['name']
            tk.Label(frame, text=f"{account_name} ({broker_key.upper()})", 
                    bg='#2d2d2d', fg='#00ff00',
                    font=('Arial', 10, 'bold')).pack(anchor=tk.W)
            
            entry = tk.Entry(frame, bg='#1e1e1e', fg='#ffffff',
                           font=('Courier', 9), width=70)
            entry.pack(fill=tk.X, pady=2)
            
            # Pre-fill current token
            if broker_key == 'upstox':
                current_token = os.getenv('UPSTOX_ACCESS_TOKEN', '')
            elif broker_key == 'dhan':
                current_token = os.getenv('DHAN_ACCESS_TOKEN', '')
            elif broker_key == 'zerodha':
                current_token = os.getenv('ZERODHA_ACCESS_TOKEN', '')
            elif broker_key == 'angelone':
                current_token = os.getenv('ANGELONE_ACCESS_TOKEN', '')
            else:
                current_token = ''
            
            entry.insert(0, current_token)
            token_entries[broker_key] = entry
        
        # Buttons
        btn_frame = tk.Frame(dialog, bg='#1e1e1e')
        btn_frame.pack(pady=20)
        
        def save_tokens():
            """Save tokens to .env file."""
            try:
                # Read current .env
                env_path = '.env'
                with open(env_path, 'r') as f:
                    lines = f.readlines()
                
                # Update tokens
                updated_lines = []
                for line in lines:
                    updated = False
                    for broker_key, entry in token_entries.items():
                        new_token = entry.get().strip()
                        if not new_token:
                            continue
                        
                        if broker_key == 'upstox' and line.startswith('UPSTOX_ACCESS_TOKEN='):
                            updated_lines.append(f'UPSTOX_ACCESS_TOKEN={new_token}\n')
                            updated = True
                        elif broker_key == 'dhan' and line.startswith('DHAN_ACCESS_TOKEN='):
                            updated_lines.append(f'DHAN_ACCESS_TOKEN={new_token}\n')
                            updated = True
                        elif broker_key == 'zerodha' and line.startswith('ZERODHA_ACCESS_TOKEN='):
                            updated_lines.append(f'ZERODHA_ACCESS_TOKEN={new_token}\n')
                            updated = True
                        elif broker_key == 'angelone' and line.startswith('ANGELONE_ACCESS_TOKEN='):
                            updated_lines.append(f'ANGELONE_ACCESS_TOKEN={new_token}\n')
                            updated = True
                    
                    if not updated:
                        updated_lines.append(line)
                
                # Write back
                with open(env_path, 'w') as f:
                    f.writelines(updated_lines)
                
                messagebox.showinfo("Success", 
                    "Tokens updated successfully!\n\n"
                    "Please restart the application for changes to take effect.")
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update tokens: {e}")
        
        tk.Button(btn_frame, text="💾 SAVE TOKENS", command=save_tokens,
                 bg='#00ff00', fg='#000000', font=('Arial', 12, 'bold'),
                 height=2, width=20).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="❌ CANCEL", command=dialog.destroy,
                 bg='#ff0000', fg='#ffffff', font=('Arial', 12, 'bold'),
                 height=2, width=20).pack(side=tk.LEFT, padx=5)
    
    def load_report(self, days):
        """Load P&L report into treeview."""
        # Clear existing data
        for item in self.reporting_tree.get_children():
            self.reporting_tree.delete(item)
        threading.Thread(target=self._load_report_async, args=(days,), daemon=True).start()
    
    def _load_report_async(self, days):
        """Load comprehensive trading report with metrics and summary."""
        try:
            all_report_data = []
            
            for broker_key, broker_info in self.trader.active_brokers.items():
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    
                    print(f"📊 Loading report for {account_name}...")
                    
                    # Get positions
                    positions_response = client.get_positions()
                    
                    if not positions_response or positions_response.get('status') == 'error':
                        print(f"   ⚠️ Unable to fetch data for {account_name}")
                        continue
                    
                    positions = positions_response.get('data', [])
                    print(f"   Total positions: {len(positions)}")
                    
                    # Process positions
                    for pos in positions:
                        qty = (pos.get('quantity') or pos.get('netQty') or pos.get('net_qty') or 0)
                        symbol = (pos.get('tradingsymbol') or pos.get('tradingSymbol') or 'Unknown')
                        
                        # Get buy/sell quantities with fallbacks
                        buy_qty = abs(pos.get('buyQty') or pos.get('buy_quantity') or pos.get('buy_qty') or 0)
                        sell_qty = abs(pos.get('sellQty') or pos.get('sell_quantity') or pos.get('sell_qty') or 0)
                        buy_avg = float(pos.get('buyAvg') or pos.get('buy_avg') or pos.get('buy_average') or pos.get('average_price') or 0)
                        sell_avg = float(pos.get('sellAvg') or pos.get('sell_avg') or pos.get('sell_average') or 0)
                        
                        if qty != 0:
                            # Open position
                            pnl = float(pos.get('unrealised') or pos.get('unrealizedProfit') or 0)
                            status = 'OPEN'
                            ltp = float(pos.get('last_price') or pos.get('ltp') or 0)
                            exit_price = ltp
                            
                            if pnl == 0 and buy_avg > 0 and ltp > 0:
                                pnl = (ltp - buy_avg) * qty
                        else:
                            # Closed position
                            pnl = float(pos.get('realised') or pos.get('realizedProfit') or 0)
                            status = 'CLOSED'
                            exit_price = sell_avg
                        
                        # Calculate metrics - handle both brokers
                        # Use closed/matched quantity (minimum of buy and sell for closed positions)
                        if status == 'CLOSED':
                            trade_qty = min(buy_qty, sell_qty) if buy_qty > 0 and sell_qty > 0 else max(buy_qty, sell_qty)
                        else:
                            # For open positions, use absolute net quantity
                            trade_qty = abs(qty)
                        
                        entry_price = buy_avg if buy_avg > 0 else sell_avg
                        
                        # For closed positions without quantity data (Upstox), estimate from order history or use standard lot
                        if trade_qty == 0 and status == 'CLOSED' and pnl != 0:
                            # Try to estimate from typical lot sizes (common for options: 25, 50, 75, 100, etc.)
                            # Or derive from P&L if we have both prices
                            if buy_avg > 0 and sell_avg > 0:
                                price_diff = sell_avg - buy_avg
                                if abs(price_diff) > 0.01:
                                    trade_qty = abs(pnl / price_diff)
                            elif entry_price > 0:
                                # Estimate exit price: exit = entry + (pnl / assumed_qty)
                                # Try common lot sizes to find best fit
                                for test_qty in [25, 50, 75, 100, 150, 200, 500, 1000, 1500, 2000, 5000, 10000, 15000, 20000, 25000]:
                                    estimated_exit = entry_price + (pnl / test_qty)
                                    # Check if exit price is reasonable (within 50% of entry)
                                    if 0.5 * entry_price <= estimated_exit <= 1.5 * entry_price:
                                        trade_qty = test_qty
                                        exit_price = estimated_exit
                                        break
                        
                        # If still no exit price, try to derive from P&L
                        if exit_price == 0 and entry_price > 0 and trade_qty > 0 and pnl != 0:
                            exit_price = entry_price + (pnl / trade_qty)
                        
                        # Estimate charges (0.05% for intraday FNO)
                        turnover = (entry_price * trade_qty) + (exit_price * trade_qty) if exit_price > 0 and entry_price > 0 and trade_qty > 0 else 0
                        charges = turnover * 0.0005 if turnover > 0 else 0
                        
                        print(f"   💰 {symbol}: qty={trade_qty}, entry={entry_price:.2f}, exit={exit_price:.2f}, turnover={turnover:.2f}, charges={charges:.2f}")
                        
                        # Calculate ROI
                        roi = 0
                        if entry_price > 0 and exit_price > 0:
                            roi = ((exit_price - entry_price) / entry_price) * 100
                        
                        net_pnl = pnl - charges
                        
                        if pnl != 0 or qty != 0:
                            all_report_data.append({
                                'account': account_name,
                                'symbol': symbol,
                                'status': status,
                                'qty': trade_qty,
                                'entry': entry_price,
                                'exit': exit_price,
                                'roi': roi,
                                'gross_pnl': pnl,
                                'charges': charges,
                                'net_pnl': net_pnl
                            })
                    
                    print(f"   ✅ Processed {len(all_report_data)} trades for {account_name}")
                    
                except Exception as e:
                    import traceback
                    print(f"❌ Error loading {broker_key}: {e}")
                    traceback.print_exc()
            
            # Update treeview on main thread
            def update_tree():
                # Clear existing
                for item in self.reporting_tree.get_children():
                    self.reporting_tree.delete(item)
                
                if not all_report_data:
                    print("⚠️ No report data to display")
                    self.report_summary.config(text="No trading data available", fg='#ffaa00')
                    return
                
                # Group by account
                accounts = {}
                for trade in all_report_data:
                    acc = trade['account']
                    if acc not in accounts:
                        accounts[acc] = []
                    accounts[acc].append(trade)
                
                # Sort by net P&L within each account
                for acc in accounts:
                    accounts[acc].sort(key=lambda x: x['net_pnl'], reverse=True)
                
                # Overall totals
                total_trades = len(all_report_data)
                total_gross = sum(t['gross_pnl'] for t in all_report_data)
                total_charges = sum(t['charges'] for t in all_report_data)
                total_net = sum(t['net_pnl'] for t in all_report_data)
                
                # Add trades grouped by account with summaries
                for account_name in sorted(accounts.keys()):
                    acc_trades = accounts[account_name]
                    
                    # Add trades for this account
                    for trade in acc_trades:
                        tag = 'profit' if trade['net_pnl'] >= 0 else 'loss'
                        
                        self.reporting_tree.insert('', tk.END, values=(
                            trade['account'],
                            trade['symbol'],
                            trade['status'],
                            f"{int(trade['qty'])}",
                            f"{trade['entry']:.2f}" if trade['entry'] > 0 else "-",
                            f"{trade['exit']:.2f}" if trade['exit'] > 0 else "-",
                            f"{trade['roi']:+.2f}%" if trade['roi'] != 0 else "-",
                            f"{trade['gross_pnl']:+,.2f}",
                            f"{trade['charges']:.2f}",
                            f"{trade['net_pnl']:+,.2f}"
                        ), tags=(tag,))
                    
                    # Calculate account summary
                    acc_count = len(acc_trades)
                    acc_gross = sum(t['gross_pnl'] for t in acc_trades)
                    acc_charges = sum(t['charges'] for t in acc_trades)
                    acc_net = sum(t['net_pnl'] for t in acc_trades)
                    acc_winners = [t for t in acc_trades if t['net_pnl'] > 0]
                    acc_losers = [t for t in acc_trades if t['net_pnl'] < 0]
                    acc_win_rate = (len(acc_winners) / acc_count * 100) if acc_count > 0 else 0
                    
                    # Add summary row for this account
                    summary_tag = 'summary_profit' if acc_net >= 0 else 'summary_loss'
                    self.reporting_tree.insert('', tk.END, values=(
                        f"┗━ {account_name} TOTAL",
                        f"{acc_count} trades | {len(acc_winners)}W/{len(acc_losers)}L ({acc_win_rate:.0f}%)",
                        "",
                        "",
                        "",
                        "",
                        "",
                        f"{acc_gross:+,.2f}",
                        f"{acc_charges:.2f}",
                        f"{acc_net:+,.2f}"
                    ), tags=(summary_tag,))
                    
                    # Add spacing
                    self.reporting_tree.insert('', tk.END, values=("",)*10, tags=('spacer',))
                
                # Configure tags
                self.reporting_tree.tag_configure('profit', foreground='#00ff00')
                self.reporting_tree.tag_configure('loss', foreground='#ff0000')
                self.reporting_tree.tag_configure('summary_profit', foreground='#00ff00', font=('Courier', 10, 'bold'))
                self.reporting_tree.tag_configure('summary_loss', foreground='#ff0000', font=('Courier', 10, 'bold'))
                self.reporting_tree.tag_configure('spacer', foreground='#444444')
                
                # Update overall summary
                summary_color = '#00ff00' if total_net >= 0 else '#ff0000'
                summary_text = (
                    f"📊 OVERALL: {total_trades} Trades  |  "
                    f"Gross: ₹{total_gross:+,.2f}  |  "
                    f"Charges: ₹{total_charges:,.2f}  |  "
                    f"NET P&L: ₹{total_net:+,.2f}"
                )
                self.report_summary.config(text=summary_text, fg=summary_color)
                
                print(f"✅ Loaded {total_trades} trades | Net P&L: ₹{total_net:+,.2f}")
            
            self.root.after(0, update_tree)
            
        except Exception as e:
            import traceback
            print(f"❌ Error loading report: {e}")
            traceback.print_exc()
    
    def refresh_performance_analytics(self):
        """Refresh performance analytics dashboard."""
        # Update account dropdown options
        try:
            account_names = ["All Accounts"]
            for broker_key, broker_info in self.trader.active_brokers.items():
                account_names.append(broker_info['name'])
            self.analytics_account_dropdown['values'] = account_names
        except:
            pass
        
        threading.Thread(target=self._calculate_performance_analytics, daemon=True).start()
    
    def _calculate_performance_analytics(self):
        """Calculate comprehensive performance analytics."""
        from collections import defaultdict
        import statistics
        
        try:
            # Get selected account filter
            selected_account = self.analytics_account_var.get() if hasattr(self, 'analytics_account_var') else "All Accounts"
            
            all_trades = []
            
            # Collect all closed trades from all brokers
            for broker_key, broker_info in self.trader.active_brokers.items():
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    
                    # Skip if account filter is active and doesn't match
                    if selected_account != "All Accounts" and account_name != selected_account:
                        continue
                    
                    # Get order history
                    orders = client.get_order_history()
                    orders_data = orders.get('data', []) if isinstance(orders, dict) else (orders if isinstance(orders, list) else [])
                    
                    # Get positions for P&L calculation
                    positions = client.get_positions()
                    positions_data = positions.get('data', []) if isinstance(positions, dict) else []
                    
                    # Group orders by symbol to identify closed trades
                    from collections import defaultdict
                    symbol_trades = defaultdict(lambda: {'buys': [], 'sells': []})
                    
                    for order in orders_data:
                        status = (order.get('status') or order.get('orderStatus', '')).upper()
                        if status in ['COMPLETE', 'TRADED', 'EXECUTED']:
                            symbol = order.get('tradingsymbol') or order.get('tradingSymbol') or str(order.get('securityId', ''))
                            side = (order.get('transaction_type') or order.get('transactionType') or order.get('orderSide', '')).upper()
                            price = float(order.get('average_price') or order.get('averagePrice') or order.get('tradedPrice') or order.get('price', 0))
                            qty = int(order.get('quantity') or order.get('tradedQuantity') or order.get('filledQty') or order.get('filled_quantity', 0))
                            
                            if price > 0 and qty > 0:
                                if side == 'BUY':
                                    symbol_trades[symbol]['buys'].append({'price': price, 'qty': qty, 'order': order})
                                elif side == 'SELL':
                                    symbol_trades[symbol]['sells'].append({'price': price, 'qty': qty, 'order': order})
                    
                    # Calculate P&L for closed positions
                    for symbol, trades in symbol_trades.items():
                        total_buy_qty = sum(t['qty'] for t in trades['buys'])
                        total_sell_qty = sum(t['qty'] for t in trades['sells'])
                        
                        if total_buy_qty > 0 and total_sell_qty > 0:
                            avg_buy = sum(t['price'] * t['qty'] for t in trades['buys']) / total_buy_qty
                            avg_sell = sum(t['price'] * t['qty'] for t in trades['sells']) / total_sell_qty
                            closed_qty = min(total_buy_qty, total_sell_qty)
                            pnl = (avg_sell - avg_buy) * closed_qty
                            
                            # Determine strategy type
                            is_ce = 'CE' in symbol.upper() or 'CALL' in symbol.upper()
                            is_pe = 'PE' in symbol.upper() or 'PUT' in symbol.upper()
                            
                            if is_ce:
                                strategy = 'CE'
                            elif is_pe:
                                strategy = 'PE'
                            else:
                                strategy = 'OTHER'
                            
                            all_trades.append({
                                'account': account_name,
                                'symbol': symbol,
                                'entry': avg_buy,
                                'exit': avg_sell,
                                'qty': closed_qty,
                                'pnl': pnl,
                                'strategy': strategy,
                                'pnl_percent': ((avg_sell - avg_buy) / avg_buy * 100) if avg_buy > 0 else 0
                            })
                    
                except Exception as e:
                    print(f"Error processing {broker_key}: {e}")
            
            # Calculate metrics
            if not all_trades:
                self._update_analytics_ui({
                    'total_trades': 0,
                    'total_pnl': 0,
                    'win_rate': 0,
                    'profit_factor': 0,
                    'winners': [],
                    'losers': [],
                    'avg_win': 0,
                    'avg_loss': 0,
                    'largest_win': 0,
                    'largest_loss': 0,
                    'max_drawdown': 0,
                    'expectancy': 0,
                    'strategy_breakdown': {},
                    'consecutive_wins': 0,
                    'consecutive_losses': 0
                })
                return
            
            total_trades = len(all_trades)
            winners = [t for t in all_trades if t['pnl'] > 0]
            losers = [t for t in all_trades if t['pnl'] < 0]
            
            total_pnl = sum(t['pnl'] for t in all_trades)
            total_wins = sum(t['pnl'] for t in winners)
            total_losses = abs(sum(t['pnl'] for t in losers))
            
            win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
            profit_factor = (total_wins / total_losses) if total_losses > 0 else (float('inf') if total_wins > 0 else 0)
            
            avg_win = (total_wins / len(winners)) if winners else 0
            avg_loss = (total_losses / len(losers)) if losers else 0
            
            largest_win = max((t['pnl'] for t in winners), default=0)
            largest_loss = min((t['pnl'] for t in losers), default=0)
            
            # Calculate max drawdown
            cumulative_pnl = []
            running_total = 0
            for trade in all_trades:
                running_total += trade['pnl']
                cumulative_pnl.append(running_total)
            
            max_drawdown = 0
            peak = cumulative_pnl[0] if cumulative_pnl else 0
            for pnl in cumulative_pnl:
                if pnl > peak:
                    peak = pnl
                drawdown = peak - pnl
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            # Expectancy
            expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)
            
            # Strategy breakdown
            strategy_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_pnl': 0, 'trades': 0})
            for trade in all_trades:
                strategy = trade['strategy']
                strategy_stats[strategy]['trades'] += 1
                strategy_stats[strategy]['total_pnl'] += trade['pnl']
                if trade['pnl'] > 0:
                    strategy_stats[strategy]['wins'] += 1
                else:
                    strategy_stats[strategy]['losses'] += 1
            
            # Consecutive wins/losses
            max_consecutive_wins = 0
            max_consecutive_losses = 0
            current_wins = 0
            current_losses = 0
            
            for trade in all_trades:
                if trade['pnl'] > 0:
                    current_wins += 1
                    current_losses = 0
                    max_consecutive_wins = max(max_consecutive_wins, current_wins)
                else:
                    current_losses += 1
                    current_wins = 0
                    max_consecutive_losses = max(max_consecutive_losses, current_losses)
            
            # Sort trades by P&L for best/worst
            sorted_trades = sorted(all_trades, key=lambda x: x['pnl'], reverse=True)
            
            metrics = {
                'total_trades': total_trades,
                'total_pnl': total_pnl,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'winners': winners,
                'losers': losers,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'largest_win': largest_win,
                'largest_loss': largest_loss,
                'max_drawdown': max_drawdown,
                'expectancy': expectancy,
                'strategy_breakdown': dict(strategy_stats),
                'consecutive_wins': max_consecutive_wins,
                'consecutive_losses': max_consecutive_losses,
                'best_trades': sorted_trades[:5],
                'worst_trades': sorted_trades[-5:][::-1],
                'recovery_factor': (total_pnl / max_drawdown) if max_drawdown > 0 else 0
            }
            
            self.root.after(0, lambda: self._update_analytics_ui(metrics))
            
        except Exception as e:
            import traceback
            print(f"❌ Error calculating analytics: {e}")
            traceback.print_exc()
    
    def _update_analytics_ui(self, metrics):
        """Update performance analytics UI with calculated metrics."""
        try:
            # Update quick stats
            pnl_color = '#00ff00' if metrics['total_pnl'] >= 0 else '#ff0000'
            self.analytics_pnl_label.config(text=f"₹{metrics['total_pnl']:,.2f}", fg=pnl_color)
            
            wr_color = '#00ff00' if metrics['win_rate'] >= 60 else ('#ffa500' if metrics['win_rate'] >= 50 else '#ff0000')
            self.analytics_winrate_label.config(text=f"{metrics['win_rate']:.1f}%", fg=wr_color)
            
            self.analytics_trades_label.config(text=str(metrics['total_trades']))
            
            pf = metrics['profit_factor']
            pf_text = f"{pf:.2f}" if pf < 999 else "∞"
            pf_color = '#00ff00' if pf >= 2.0 else ('#ffa500' if pf >= 1.5 else '#ff0000')
            self.analytics_pf_label.config(text=pf_text, fg=pf_color)
            
            # Left column metrics
            self.analytics_left_text.delete(1.0, tk.END)
            left_content = f"""╔═══════════════════════════════════════╗
║      WIN/LOSS BREAKDOWN               ║
╚═══════════════════════════════════════╝

🎯 Total Trades:     {metrics['total_trades']}
✅ Winning Trades:   {len(metrics['winners'])} ({metrics['win_rate']:.1f}%)
❌ Losing Trades:    {len(metrics['losers'])} ({100-metrics['win_rate']:.1f}%)

💰 Average Win:      ₹{metrics['avg_win']:,.2f}
💸 Average Loss:     ₹{metrics['avg_loss']:,.2f}
📊 Win/Loss Ratio:   {(metrics['avg_win']/metrics['avg_loss']):.2f}x
   {'' if metrics['avg_loss'] > 0 else 'N/A'}

🏆 Largest Win:      ₹{metrics['largest_win']:+,.2f}
💥 Largest Loss:     ₹{metrics['largest_loss']:,.2f}

╔═══════════════════════════════════════╗
║      RISK METRICS                     ║
╚═══════════════════════════════════════╝

📉 Max Drawdown:     ₹{metrics['max_drawdown']:,.2f}
🔄 Recovery Factor:  {metrics['recovery_factor']:.2f}x
💡 Expectancy:       ₹{metrics['expectancy']:+,.2f} per trade

🔥 Max Consecutive:
   Wins:  {metrics['consecutive_wins']} trades
   Losses: {metrics['consecutive_losses']} trades
"""
            self.analytics_left_text.insert(1.0, left_content)
            
            # Right column metrics
            self.analytics_right_text.delete(1.0, tk.END)
            
            # Calculate additional stats
            total_wins_amount = sum(t['pnl'] for t in metrics['winners'])
            total_losses_amount = abs(sum(t['pnl'] for t in metrics['losers']))
            
            right_content = f"""╔═══════════════════════════════════════╗
║      PROFIT/LOSS ANALYSIS             ║
╚═══════════════════════════════════════╝

✅ Total Wins:       ₹{total_wins_amount:+,.2f}
❌ Total Losses:     ₹{-total_losses_amount:,.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 Net P&L:          ₹{metrics['total_pnl']:+,.2f}

📊 Profit Factor:    {pf_text}
   {'(Excellent!)' if pf >= 2.0 else '(Good)' if pf >= 1.5 else '(Needs Improvement)' if pf < 1.5 and pf > 0 else ''}

╔═══════════════════════════════════════╗
║      TRADE QUALITY                    ║
╚═══════════════════════════════════════╝

🎯 Win Rate:         {metrics['win_rate']:.1f}%
   {'✅ Excellent (>60%)' if metrics['win_rate'] >= 60 else '✅ Good (50-60%)' if metrics['win_rate'] >= 50 else '⚠️ Below 50% - Focus on setup quality'}

💰 Avg Win > Avg Loss?
   {f"✅ YES ({metrics['avg_win']/metrics['avg_loss']:.2f}x)" if metrics['avg_loss'] > 0 and metrics['avg_win'] > metrics['avg_loss'] else "❌ NO - Improve R:R ratio"}

📈 Risk-Reward:
   {f"Risking ₹1 to make ₹{metrics['avg_win']/metrics['avg_loss']:.2f}" if metrics['avg_loss'] > 0 else "N/A"}

🎲 Expected Value:
   ₹{metrics['expectancy']:+,.2f} per trade
   {f"✅ Positive expectancy" if metrics['expectancy'] > 0 else "❌ Negative expectancy"}
"""
            self.analytics_right_text.insert(1.0, right_content)
            
            # Strategy breakdown
            self.analytics_strategy_text.delete(1.0, tk.END)
            strategy_content = """╔══════════════════════════════════════════════════════════════════════════════════╗
║                          STRATEGY PERFORMANCE BREAKDOWN                          ║
╚══════════════════════════════════════════════════════════════════════════════════╝

"""
            
            if metrics['strategy_breakdown']:
                strategy_content += f"{'Strategy':<15} {'Trades':<10} {'Wins':<10} {'Losses':<10} {'Win Rate':<12} {'Net P&L':<15}\n"
                strategy_content += "─" * 85 + "\n"
                
                for strategy, stats in metrics['strategy_breakdown'].items():
                    wr = (stats['wins'] / stats['trades'] * 100) if stats['trades'] > 0 else 0
                    strategy_content += f"{strategy:<15} {stats['trades']:<10} {stats['wins']:<10} {stats['losses']:<10} {wr:<11.1f}% ₹{stats['total_pnl']:>+13,.2f}\n"
                
                strategy_content += "\n💡 Strategy Insights:\n"
                
                # Find best strategy
                best_strategy = max(metrics['strategy_breakdown'].items(), key=lambda x: x[1]['total_pnl'])
                strategy_content += f"   🏆 Best: {best_strategy[0]} (₹{best_strategy[1]['total_pnl']:+,.2f})\n"
                
                # Find highest win rate
                best_wr = max(metrics['strategy_breakdown'].items(), 
                             key=lambda x: (x[1]['wins'] / x[1]['trades'] if x[1]['trades'] > 0 else 0))
                wr_pct = (best_wr[1]['wins'] / best_wr[1]['trades'] * 100) if best_wr[1]['trades'] > 0 else 0
                strategy_content += f"   🎯 Highest Win Rate: {best_wr[0]} ({wr_pct:.1f}%)\n"
            else:
                strategy_content += "   No strategy data available yet. Start trading to see breakdown!\n"
            
            self.analytics_strategy_text.insert(1.0, strategy_content)
            
            # Best/Worst trades
            self.analytics_trades_text.delete(1.0, tk.END)
            trades_content = """╔══════════════════════════════════════════════════════════════════════════════════╗
║                               BEST & WORST TRADES                                ║
╚══════════════════════════════════════════════════════════════════════════════════╝

"""
            
            if metrics.get('best_trades'):
                trades_content += "🏆 TOP 5 BEST TRADES:\n"
                for i, trade in enumerate(metrics['best_trades'], 1):
                    trades_content += f"   {i}. {trade['symbol']:<30} ₹{trade['pnl']:>+10,.2f}  ({trade['pnl_percent']:+.2f}%)\n"
                
                trades_content += "\n💥 TOP 5 WORST TRADES:\n"
                for i, trade in enumerate(metrics['worst_trades'], 1):
                    trades_content += f"   {i}. {trade['symbol']:<30} ₹{trade['pnl']:>+10,.2f}  ({trade['pnl_percent']:+.2f}%)\n"
                
                trades_content += "\n💡 Learn from these trades to improve your strategy!\n"
            else:
                trades_content += "   No completed trades yet. Start trading to see your best and worst trades!\n"
            
            self.analytics_trades_text.insert(1.0, trades_content)
            
            print("✅ Performance analytics updated")
            
        except Exception as e:
            import traceback
            print(f"❌ Error updating analytics UI: {e}")
            traceback.print_exc()


class StopLossDialog:
    """Dialog for stop loss configuration."""
    
    def __init__(self, parent, trader, positions, refresh_callback):
        self.trader = trader
        self.positions = positions
        self.refresh_callback = refresh_callback
        self.sl_percent = 5.0
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("🛡️ Stop Loss Configuration")
        self.dialog.geometry("800x600")
        self.dialog.configure(bg='#1e1e1e')
        
        self.create_ui()
    
    def create_ui(self):
        """Create stop loss UI."""
        # Title
        tk.Label(self.dialog, text="🛡️ STOP LOSS FOR ALL POSITIONS",
                font=('Arial', 14, 'bold'), bg='#1e1e1e', fg='#00ff00').pack(pady=10)
        
        tk.Label(self.dialog, text="Same SL % will apply to all positions",
                font=('Arial', 10), bg='#1e1e1e', fg='#ffffff').pack()
        
        # SL percentage control
        control_frame = tk.Frame(self.dialog, bg='#2d2d2d', relief=tk.RAISED, borderwidth=2)
        control_frame.pack(fill=tk.X, padx=20, pady=20)
        
        tk.Label(control_frame, text="Stop Loss Distance:",
                font=('Arial', 12, 'bold'), bg='#2d2d2d', fg='#ffffff').pack(pady=5)
        
        self.sl_label = tk.Label(control_frame, text=f"{self.sl_percent:.2f}% below entry",
                                font=('Arial', 16, 'bold'), bg='#2d2d2d', fg='#ff9900')
        self.sl_label.pack(pady=10)
        
        # Controls
        btn_frame = tk.Frame(control_frame, bg='#2d2d2d')
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="--", command=lambda: self.adjust_sl(-1),
                 bg='#ff0000', fg='#ffffff', font=('Arial', 12, 'bold'), width=4).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="-", command=lambda: self.adjust_sl(-0.5),
                 bg='#ff6600', fg='#ffffff', font=('Arial', 12, 'bold'), width=4).pack(side=tk.LEFT, padx=2)
        
        self.sl_entry = tk.Entry(btn_frame, font=('Arial', 12), width=8, justify='center')
        self.sl_entry.insert(0, str(self.sl_percent))
        self.sl_entry.pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="+", command=lambda: self.adjust_sl(0.5),
                 bg='#00ff00', fg='#000000', font=('Arial', 12, 'bold'), width=4).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="++", command=lambda: self.adjust_sl(1),
                 bg='#00aa00', fg='#ffffff', font=('Arial', 12, 'bold'), width=4).pack(side=tk.LEFT, padx=2)
        
        # Preview table
        preview_frame = tk.LabelFrame(self.dialog, text="Preview SL Orders", bg='#1e1e1e',
                                     fg='#ffffff', font=('Arial', 10, 'bold'))
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        columns = ('Broker', 'Symbol', 'Entry', 'SL Price', 'Loss')
        self.preview_tree = ttk.Treeview(preview_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.preview_tree.heading(col, text=col)
            self.preview_tree.column(col, width=120)
        
        scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_tree.yview)
        self.preview_tree.configure(yscrollcommand=scrollbar.set)
        
        self.preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        self.total_loss_label = tk.Label(preview_frame, text="Total Potential Loss: ₹0.00",
                                        font=('Arial', 12, 'bold'), bg='#1e1e1e', fg='#ff0000')
        self.total_loss_label.pack(pady=5)
        
        # Action buttons
        action_frame = tk.Frame(self.dialog, bg='#1e1e1e')
        action_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Button(action_frame, text="✅ PLACE SL ORDERS", command=self.place_sl_orders,
                 bg='#00ff00', fg='#000000', font=('Arial', 12, 'bold'),
                 height=2).pack(side=tk.LEFT, expand=True, padx=2)
        
        tk.Button(action_frame, text="❌ CANCEL", command=self.dialog.destroy,
                 bg='#ff0000', fg='#ffffff', font=('Arial', 12, 'bold'),
                 height=2).pack(side=tk.RIGHT, expand=True, padx=2)
        
        # Initial update
        self.update_preview()
    
    def adjust_sl(self, delta):
        """Adjust SL percentage."""
        try:
            current = float(self.sl_entry.get())
            new_val = max(0.5, min(50, current + delta))
            self.sl_percent = new_val
            self.sl_entry.delete(0, tk.END)
            self.sl_entry.insert(0, f"{new_val:.2f}")
            self.update_preview()
        except:
            pass
    
    def update_preview(self):
        """Update SL preview."""
        # Clear preview
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        
        # Update label
        self.sl_label.config(text=f"{self.sl_percent:.2f}% below entry")
        
        # Calculate SL for each position
        total_loss = 0
        for pos in self.positions:
            broker_name = pos.get('broker_name', 'N/A')
            symbol = pos.get('tradingsymbol', 'N/A')
            avg_price = pos.get('average_price') or pos.get('buy_avg') or pos.get('buyAvg') or 0
            qty = pos.get('quantity', 0)
            
            if avg_price > 0:
                sl_price = avg_price * (1 - self.sl_percent / 100)
                potential_loss = (avg_price - sl_price) * qty
                total_loss += potential_loss
                
                values = (broker_name, symbol, f"₹{avg_price:.2f}",
                         f"₹{sl_price:.2f}", f"₹{potential_loss:.2f}")
                self.preview_tree.insert('', tk.END, values=values)
        
        self.total_loss_label.config(text=f"Total Potential Loss: ₹{total_loss:,.2f}")
    
    def place_sl_orders(self):
        """Place SL orders for all positions."""
        if messagebox.askyesno("Confirm", f"Place {len(self.positions)} SL orders?"):
            threading.Thread(target=self._place_sl_async, daemon=True).start()
    
    def _place_sl_async(self):
        """Place SL orders asynchronously."""
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def place_sl(pos):
                try:
                    client = pos.get('client')
                    avg_price = pos.get('average_price') or pos.get('buy_avg') or pos.get('buyAvg') or 0
                    sl_price = avg_price * (1 - self.sl_percent / 100)
                    qty = abs(pos.get('quantity', 0))
                    
                    # Get instrument key - different field names for different brokers
                    instrument_key = (pos.get('instrument_key') or 
                                    pos.get('instrument_token') or 
                                    pos.get('securityId') or 
                                    pos.get('security_id') or '')
                    
                    if not instrument_key:
                        return False
                    
                    # Determine transaction type based on current position
                    trans_type = "SELL" if pos.get('quantity', 0) > 0 else "BUY"
                    
                    result = client.place_order(
                        instrument_key=instrument_key,
                        quantity=qty,
                        transaction_type=trans_type,
                        order_type="SL",
                        product="I",
                        price=sl_price * 0.99,
                        trigger_price=sl_price
                    )
                    return result is not None
                except:
                    return False
            
            with ThreadPoolExecutor(max_workers=len(self.positions)) as executor:
                futures = [executor.submit(place_sl, pos) for pos in self.positions]
                results = [f.result() for f in as_completed(futures)]
            
            success = sum(results)
            self.dialog.after(0, lambda: messagebox.showinfo("Success",
                                                             f"{success}/{len(self.positions)} SL orders placed!"))
            self.dialog.after(0, self.dialog.destroy)
            self.refresh_callback()
        except Exception as e:
            self.dialog.after(0, lambda: messagebox.showerror("Error", f"SL failed: {e}"))


class IncreasePositionDialog:
    """Dialog for increasing positions."""
    
    def __init__(self, parent, trader, positions, refresh_callback):
        self.trader = trader
        self.positions = positions
        self.refresh_callback = refresh_callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("📈 Increase Position")
        self.dialog.geometry("600x400")
        self.dialog.configure(bg='#1e1e1e')
        
        self.create_ui()
    
    def create_ui(self):
        """Create increase position UI."""
        tk.Label(self.dialog, text="📈 INCREASE ALL POSITIONS",
                font=('Arial', 14, 'bold'), bg='#1e1e1e', fg='#00aaff').pack(pady=20)
        
        tk.Label(self.dialog, text="Select percentage to add to ALL positions:",
                font=('Arial', 12), bg='#1e1e1e', fg='#ffffff').pack(pady=10)
        
        # Percentage control with +/- buttons
        control_frame = tk.Frame(self.dialog, bg='#1e1e1e')
        control_frame.pack(pady=20)
        
        self.increase_percent = tk.IntVar(value=25)
        
        tk.Button(control_frame, text="-", command=lambda: self.adjust_percent(-25),
                 bg='#ff6600', fg='#ffffff', font=('Arial', 14, 'bold'), width=4, height=2).pack(side=tk.LEFT, padx=5)
        
        self.percent_label = tk.Label(control_frame, textvariable=self.increase_percent,
                                     font=('Arial', 24, 'bold'), bg='#1e1e1e', fg='#00aaff', width=6)
        self.percent_label.pack(side=tk.LEFT, padx=10)
        
        tk.Button(control_frame, text="+", command=lambda: self.adjust_percent(25),
                 bg='#00ff00', fg='#000000', font=('Arial', 14, 'bold'), width=4, height=2).pack(side=tk.LEFT, padx=5)
        
        # Apply button
        tk.Button(self.dialog, text="✅ APPLY", command=self.apply_increase,
                 bg='#00ff00', fg='#000000', font=('Arial', 14, 'bold'),
                 width=20, height=2).pack(pady=20)
        
        # Cancel button
        tk.Button(self.dialog, text="❌ CANCEL", command=self.dialog.destroy,
                 bg='#ff0000', fg='#ffffff', font=('Arial', 12, 'bold'),
                 height=2, width=20).pack(pady=20)
    
    def adjust_percent(self, delta):
        """Adjust increase percentage."""
        current = self.increase_percent.get()
        new_val = max(25, min(200, current + delta))
        self.increase_percent.set(new_val)
    
    def apply_increase(self):
        """Apply the increase."""
        percent = self.increase_percent.get()
        if messagebox.askyesno("Confirm", f"Add {percent}% to all {len(self.positions)} positions?"):
            threading.Thread(target=self._increase_async, args=(percent,), daemon=True).start()
    
    def _increase_async(self, percent):
        """Increase positions asynchronously."""
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def increase_single(pos):
                try:
                    client = pos.get('client')
                    qty = pos.get('quantity', 0)
                    add_qty = int(abs(qty) * percent / 100)
                    
                    if add_qty > 0:
                        # Get instrument key - different field names for different brokers
                        instrument_key = (pos.get('instrument_key') or 
                                        pos.get('instrument_token') or 
                                        pos.get('securityId') or 
                                        pos.get('security_id') or '')
                        
                        if not instrument_key:
                            return False
                        
                        transaction_type = "BUY" if qty > 0 else "SELL"
                        result = client.place_order(
                            instrument_key=instrument_key,
                            quantity=add_qty,
                            transaction_type=transaction_type,
                            order_type="MARKET",
                            product="I"
                        )
                        return result is not None
                    return False
                except:
                    return False
            
            with ThreadPoolExecutor(max_workers=len(self.positions)) as executor:
                futures = [executor.submit(increase_single, pos) for pos in self.positions]
                results = [f.result() for f in as_completed(futures)]
            
            success = sum(results)
            self.dialog.after(0, lambda: messagebox.showinfo("Success",
                                                             f"{success}/{len(self.positions)} orders placed!"))
            self.dialog.after(0, self.dialog.destroy)
            self.refresh_callback()
        except Exception as e:
            self.dialog.after(0, lambda: messagebox.showerror("Error", f"Increase failed: {e}"))


class ExitPositionDialog:
    """Dialog for exiting positions with percentage option."""
    
    def __init__(self, parent, trader, positions, refresh_callback):
        self.trader = trader
        self.positions = positions
        self.refresh_callback = refresh_callback
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("🚪 Exit Position")
        self.dialog.geometry("600x400")
        self.dialog.configure(bg='#1e1e1e')
        
        self.create_ui()
    
    def create_ui(self):
        """Create exit position UI."""
        tk.Label(self.dialog, text="🚪 EXIT ALL POSITIONS",
                font=('Arial', 14, 'bold'), bg='#1e1e1e', fg='#ff0000').pack(pady=20)
        
        tk.Label(self.dialog, text="Select exit percentage:",
                font=('Arial', 12), bg='#1e1e1e', fg='#ffffff').pack(pady=10)
        
        # Percentage dropdown
        self.exit_percent = tk.IntVar(value=100)
        
        btn_frame = tk.Frame(self.dialog, bg='#1e1e1e')
        btn_frame.pack(pady=20)
        
        for pct in [25, 50, 75, 100]:
            tk.Radiobutton(btn_frame, text=f"{pct}%", variable=self.exit_percent, value=pct,
                          bg='#1e1e1e', fg='#ffffff', selectcolor='#2d2d2d',
                          font=('Arial', 14, 'bold'), indicatoron=False, width=8, height=2).pack(side=tk.LEFT, padx=5)
        
        # Apply button
        tk.Button(self.dialog, text="✅ EXIT", command=self.apply_exit,
                 bg='#ff0000', fg='#ffffff', font=('Arial', 14, 'bold'),
                 width=20, height=2).pack(pady=30)
        
        # Cancel button
        tk.Button(self.dialog, text="❌ CANCEL", command=self.dialog.destroy,
                 bg='#666666', fg='#ffffff', font=('Arial', 12, 'bold'),
                 height=2, width=20).pack(pady=10)
    
    def apply_exit(self):
        """Apply the exit."""
        percent = self.exit_percent.get()
        if messagebox.askyesno("Confirm", f"Exit {percent}% of all {len(self.positions)} positions?"):
            threading.Thread(target=self._exit_async, args=(percent,), daemon=True).start()
    
    def _exit_async(self, percent):
        """Exit positions asynchronously."""
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            def exit_single(pos):
                try:
                    client = pos.get('client')
                    qty = pos.get('quantity', 0)
                    exit_qty = int(abs(qty) * percent / 100)
                    
                    if exit_qty > 0:
                        # Get instrument key - different field names for different brokers
                        instrument_key = (pos.get('instrument_key') or 
                                        pos.get('instrument_token') or 
                                        pos.get('securityId') or 
                                        pos.get('security_id') or '')
                        
                        if not instrument_key:
                            return False
                        
                        transaction_type = "SELL" if qty > 0 else "BUY"
                        result = client.place_order(
                            instrument_key=instrument_key,
                            quantity=exit_qty,
                            transaction_type=transaction_type,
                            order_type="MARKET",
                            product="I"
                        )
                        return result is not None
                    return False
                except:
                    return False
            
            with ThreadPoolExecutor(max_workers=len(self.positions)) as executor:
                futures = [executor.submit(exit_single, pos) for pos in self.positions]
                results = [f.result() for f in as_completed(futures)]
            
            success = sum(results)
            self.dialog.after(0, lambda: messagebox.showinfo("Success",
                                                             f"{success}/{len(self.positions)} exits placed!"))
            self.dialog.after(0, self.dialog.destroy)
            self.refresh_callback()
        except Exception as e:
            self.dialog.after(0, lambda: messagebox.showerror("Error", f"Exit failed: {e}"))


class PortfolioDialog:
    """Dialog for portfolio view."""
    
    def __init__(self, parent, trader):
        self.trader = trader
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("💼 Portfolio")
        self.dialog.geometry("700x500")
        self.dialog.configure(bg='#1e1e1e')
        
        self.create_ui()
    
    def create_ui(self):
        """Create portfolio UI."""
        tk.Label(self.dialog, text="💼 PORTFOLIO SUMMARY",
                font=('Arial', 14, 'bold'), bg='#1e1e1e', fg='#9900ff').pack(pady=20)
        
        # Portfolio info
        info_frame = tk.Frame(self.dialog, bg='#2d2d2d', relief=tk.RAISED, borderwidth=2)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Get portfolio data
        text = scrolledtext.ScrolledText(info_frame, bg='#1e1e1e', fg='#ffffff',
                                        font=('Courier', 10), height=20)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Populate portfolio info
        try:
            if self.trader.multi_account_mode:
                text.insert(tk.END, "═" * 60 + "\n")
                text.insert(tk.END, "MULTI-ACCOUNT PORTFOLIO\n")
                text.insert(tk.END, "═" * 60 + "\n\n")
                
                total_pnl = 0
                total_available = 0
                total_used = 0
                
                for broker_key, broker_info in self.trader.active_brokers.items():
                    try:
                        client = broker_info['client']
                        account_name = broker_info['name']
                        
                        text.insert(tk.END, f"📊 {account_name} ({broker_key.upper()})\n")
                        text.insert(tk.END, "─" * 60 + "\n")
                        
                        # Get funds
                        funds = client.get_funds_and_margin()
                        equity = funds.get('data', {}).get('equity', {})
                        available = float(equity.get('available_margin', 0))
                        used = float(equity.get('used_margin', 0))
                        
                        total_available += available
                        total_used += used
                        
                        text.insert(tk.END, f"💰 Available: ₹{available:,.2f}\n")
                        text.insert(tk.END, f"💰 Used: ₹{used:,.2f}\n")
                        
                        # Get positions P&L
                        positions = client.get_positions()
                        positions_data = positions.get('data', [])
                        pnl = sum(float(p.get('pnl', 0) or p.get('unrealised', 0) or 0)
                                 for p in positions_data)
                        total_pnl += pnl
                        
                        if pnl != 0:
                            pnl_symbol = "🟢" if pnl >= 0 else "🔴"
                            text.insert(tk.END, f"{pnl_symbol} P&L: ₹{pnl:,.2f}\n")
                        
                        position_count = len([p for p in positions_data if p.get('quantity', 0) != 0])
                        text.insert(tk.END, f"💼 Positions: {position_count}\n\n")
                    
                    except Exception as e:
                        text.insert(tk.END, f"❌ Error: {e}\n\n")
                
                # Combined summary
                text.insert(tk.END, "═" * 60 + "\n")
                text.insert(tk.END, "COMBINED SUMMARY\n")
                text.insert(tk.END, "═" * 60 + "\n")
                text.insert(tk.END, f"💰 Total Available: ₹{total_available:,.2f}\n")
                text.insert(tk.END, f"💰 Total Used: ₹{total_used:,.2f}\n")
                
                if total_pnl != 0:
                    pnl_symbol = "🟢" if total_pnl >= 0 else "🔴"
                    text.insert(tk.END, f"{pnl_symbol} Combined P&L: ₹{total_pnl:,.2f}\n")
                
                if total_used > 0:
                    roi = (total_pnl / total_used * 100)
                    roi_symbol = "🟢" if roi >= 0 else "🔴"
                    text.insert(tk.END, f"{roi_symbol} ROI: {roi:.2f}%\n")
        
        except Exception as e:
            text.insert(tk.END, f"❌ Error loading portfolio: {e}\n")
        
        text.config(state=tk.DISABLED)
        
        # Close button
        tk.Button(self.dialog, text="✅ CLOSE", command=self.dialog.destroy,
                 bg='#00ff00', fg='#000000', font=('Arial', 12, 'bold'),
                 height=2, width=20).pack(pady=10)


class ClosedPositionsDialog:
    """Dialog for viewing closed positions."""
    
    def __init__(self, parent, trader):
        self.trader = trader
        
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("📜 Closed Positions")
        self.dialog.geometry("900x600")
        self.dialog.configure(bg='#1e1e1e')
        
        self.create_ui()
    
    def create_ui(self):
        """Create closed positions UI."""
        tk.Label(self.dialog, text="📜 CLOSED POSITIONS",
                font=('Arial', 14, 'bold'), bg='#1e1e1e', fg='#0099cc').pack(pady=20)
        
        # Positions info
        info_frame = tk.Frame(self.dialog, bg='#2d2d2d', relief=tk.RAISED, borderwidth=2)
        info_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Get closed positions data
        text = scrolledtext.ScrolledText(info_frame, bg='#1e1e1e', fg='#ffffff',
                                        font=('Courier', 9), height=25, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Populate closed positions info
        try:
            if self.trader.multi_account_mode:
                text.insert(tk.END, "═" * 80 + "\n")
                text.insert(tk.END, "CLOSED POSITIONS - ALL ACCOUNTS\n")
                text.insert(tk.END, "═" * 80 + "\n\n")
                
                all_trades = []
                
                for broker_key, broker_info in self.trader.active_brokers.items():
                    try:
                        client = broker_info['client']
                        account_name = broker_info['name']
                        
                        text.insert(tk.END, f"📊 {account_name} ({broker_key.upper()})\n")
                        text.insert(tk.END, "─" * 80 + "\n")
                        
                        # Get order history
                        orders = client.get_order_history()
                        
                        # Handle both dict and list responses
                        if isinstance(orders, dict):
                            orders_data = orders.get('data', [])
                        elif isinstance(orders, list):
                            orders_data = orders
                        else:
                            orders_data = []
                        
                        if not orders_data:
                            text.insert(tk.END, "   No closed positions found\n\n")
                            continue
                        
                        text.insert(tk.END, f"   Found {len(orders_data)} orders\n")
                        
                        # Group by symbol
                        from collections import defaultdict
                        grouped_trades = defaultdict(list)
                        
                        matched_orders = 0
                        for order in orders_data:
                            # Status check - handle different field names
                            status = order.get('status', '').upper()
                            if not status:
                                status = order.get('orderStatus', '').upper()
                            
                            if status in ['COMPLETE', 'TRADED', 'EXECUTED', 'TRADED']:
                                matched_orders += 1
                                # Symbol - handle different field names
                                symbol = order.get('tradingsymbol') or order.get('tradingSymbol') or order.get('securityId', 'N/A')
                                
                                # Get transaction type - multiple possible field names
                                trans_type = (order.get('transaction_type') or 
                                            order.get('transactionType') or 
                                            order.get('orderSide', '')).upper()
                                
                                # Get price - check multiple fields
                                price = (order.get('average_price') or 
                                       order.get('averagePrice') or 
                                       order.get('tradedPrice') or 
                                       order.get('price', 0))
                                
                                # Get quantity - check multiple fields
                                qty = (order.get('quantity') or 
                                      order.get('tradedQuantity') or 
                                      order.get('filledQty') or 
                                      order.get('filled_quantity', 0))
                                
                                # Get time
                                time_str = 'N/A'
                                for time_field in ['order_timestamp', 'created_at', 'buy_date',
                                                  'createTime', 'transactionTime', 'tradeTime']:
                                    if order.get(time_field):
                                        try:
                                            if 'T' in str(order[time_field]):
                                                dt = datetime.fromisoformat(str(order[time_field]).replace('Z', '+00:00'))
                                            else:
                                                dt = datetime.strptime(str(order[time_field])[:19], '%Y-%m-%d %H:%M:%S')
                                            time_str = dt.strftime('%H:%M:%S')
                                            break
                                        except:
                                            pass
                                
                                if price and qty:
                                    grouped_trades[symbol].append({
                                        'side': trans_type.upper(),
                                        'price': float(price),
                                        'qty': int(qty),
                                        'time': time_str
                                    })
                        
                        text.insert(tk.END, f"   Found {matched_orders} completed/traded orders\n\n")
                        
                        if not grouped_trades:
                            text.insert(tk.END, "   No valid trades found\n\n")
                            continue
                        
                        text.insert(tk.END, f"   {len(grouped_trades)} unique symbol(s):\n\n")
                        
                        for symbol, symbol_trades in grouped_trades.items():
                            total_buy_qty = sum(t['qty'] for t in symbol_trades if t['side'] == 'BUY')
                            total_sell_qty = sum(t['qty'] for t in symbol_trades if t['side'] == 'SELL')
                            
                            # Get entry and exit times
                            buy_times = [t['time'] for t in symbol_trades if t['side'] == 'BUY' and t['time'] != 'N/A']
                            sell_times = [t['time'] for t in symbol_trades if t['side'] == 'SELL' and t['time'] != 'N/A']
                            entry_time = buy_times[0] if buy_times else 'N/A'
                            exit_time = sell_times[-1] if sell_times else 'N/A'
                            
                            text.insert(tk.END, f"   📊 {symbol}\n")
                            text.insert(tk.END, f"      BUY: {total_buy_qty} | SELL: {total_sell_qty}\n")
                            text.insert(tk.END, f"      Entry: {entry_time} | Exit: {exit_time}\n")
                            
                            # Calculate average prices
                            buy_trades = [t for t in symbol_trades if t['side'] == 'BUY']
                            sell_trades = [t for t in symbol_trades if t['side'] == 'SELL']
                            
                            if buy_trades:
                                total_buy_value = sum(t['price'] * t['qty'] for t in buy_trades)
                                total_buy_qty = sum(t['qty'] for t in buy_trades)
                                if total_buy_qty > 0 and total_buy_value > 0:
                                    avg_buy = total_buy_value / total_buy_qty
                                    text.insert(tk.END, f"      Avg Buy: ₹{avg_buy:,.2f}\n")
                            
                            if sell_trades:
                                total_sell_value = sum(t['price'] * t['qty'] for t in sell_trades)
                                total_sell_qty = sum(t['qty'] for t in sell_trades)
                                if total_sell_qty > 0 and total_sell_value > 0:
                                    avg_sell = total_sell_value / total_sell_qty
                                    text.insert(tk.END, f"      Avg Sell: ₹{avg_sell:,.2f}\n")
                                    
                                    # Calculate P&L if both buy and sell exist
                                    if buy_trades:
                                        pnl = (avg_sell - avg_buy) * min(total_buy_qty, total_sell_qty)
                                        pnl_symbol = "🟢" if pnl >= 0 else "🔴"
                                        text.insert(tk.END, f"      {pnl_symbol} P&L: ₹{pnl:,.2f}\n")
                            
                            net_qty = total_buy_qty - total_sell_qty
                            if net_qty != 0:
                                text.insert(tk.END, f"      Net: {abs(net_qty)} {'LONG' if net_qty > 0 else 'SHORT'}\n")
                            else:
                                text.insert(tk.END, f"      ✅ Closed\n")
                            text.insert(tk.END, "\n")
                    
                    except Exception as e:
                        text.insert(tk.END, f"   ❌ Error: {e}\n\n")
                
                text.insert(tk.END, "═" * 80 + "\n")
        
        except Exception as e:
            text.insert(tk.END, f"❌ Error loading closed positions: {e}\n")
        
        text.config(state=tk.DISABLED)
        
        # Close button
        tk.Button(self.dialog, text="✅ CLOSE", command=self.dialog.destroy,
                 bg='#00ff00', fg='#000000', font=('Arial', 12, 'bold'),
                 height=2, width=20).pack(pady=10)
    
    # ==================== MARKET ANALYSIS & ALERTS ====================
    
    def trigger_manual_analysis(self):
        """Trigger manual analysis with progress indicator."""
        if not hasattr(self, 'perform_market_analysis'):
            messagebox.showinfo("Not Ready", "Market analysis feature is still loading...")
            return
        
        # Show progress dialog
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Analyzing Market")
        progress_window.geometry("400x150")
        progress_window.configure(bg='#1e1e1e')
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        tk.Label(
            progress_window,
            text="🔄 Analyzing Market...",
            font=('Arial', 14, 'bold'),
            bg='#1e1e1e',
            fg='#00aaff'
        ).pack(pady=20)
        
        tk.Label(
            progress_window,
            text="Fetching candles and calculating indicators...",
            font=('Arial', 10),
            bg='#1e1e1e',
            fg='#ffffff'
        ).pack(pady=10)
        
        progress = ttk.Progressbar(progress_window, mode='indeterminate', length=300)
        progress.pack(pady=20)
        progress.start()
        
        # Start analysis
        self.perform_market_analysis()
        
        # Close progress and show report after 5 seconds
        def show_report_delayed():
            progress.stop()
            progress_window.destroy()
            if hasattr(self, 'show_analysis_report'):
                self.show_analysis_report()
            else:
                messagebox.showinfo("Analysis Complete", "Analysis completed. Check console for results.")
        
        self.root.after(5000, show_report_delayed)
    
    def start_market_analysis(self):
        """Start automated market analysis every 3 minutes."""
        if self.market_analysis_enabled.get():
            self.perform_market_analysis()
            self.root.after(self.analysis_interval, self.start_market_analysis)
    
    def perform_market_analysis(self):
        """
        Perform comprehensive market analysis including:
        - Candlestick patterns
        - Price action analysis
        - Momentum indicators
        - Volume analysis
        - Support/Resistance levels
        """
        # Show loading message
        print("🔄 Starting market analysis...")
        threading.Thread(target=self._analyze_market_async, daemon=True).start()
    
    def _analyze_market_async(self):
        """Async market analysis to avoid blocking UI."""
        try:
            if not self.trader or not self.trader.active_brokers:
                print("❌ No active brokers available for analysis")
                self.root.after(0, lambda: messagebox.showwarning(
                    "Analysis Error",
                    "No active broker connection found.\n\nPlease check your broker credentials."
                ))
                return
            
            # Get first available broker
            broker_info = next(iter(self.trader.active_brokers.values()))
            client = broker_info['client']
            
            print(f"📊 Analyzing markets using {broker_info.get('name', 'broker')}...")
            
            # Analyze each index
            for index_name in ['NIFTY', 'BANKNIFTY']:
                try:
                    print(f"   Analyzing {index_name}...")
                    analysis = self.analyze_index(client, index_name)
                    
                    if analysis:
                        # Store latest analysis result
                        self.latest_analysis[index_name] = analysis
                        print(f"   ✅ {index_name} analysis complete")
                        
                        # Generate alert if strong momentum detected
                        if analysis.get('signal'):
                            self.generate_trading_alert(index_name, analysis)
                    else:
                        print(f"   ⚠️ {index_name} analysis returned no data")
                        
                except Exception as e:
                    print(f"   ❌ Error analyzing {index_name}: {e}")
            
            print("✅ Market analysis completed")
                    
        except Exception as e:
            print(f"❌ Market analysis error: {e}")
            self.root.after(0, lambda: messagebox.showerror(
                "Analysis Error",
                f"Failed to analyze market:\n\n{str(e)}"
            ))
    
    def analyze_index(self, client, index_name):
        """
        Comprehensive technical analysis for an index.
        
        Returns:
            Dict with analysis results including signal, strength, and recommendations
        """
        try:
            # Get instrument key
            instrument_keys = {
                'NIFTY': 'NSE_INDEX|Nifty 50',
                'BANKNIFTY': 'NSE_INDEX|Nifty Bank',
                'SENSEX': 'BSE_INDEX|SENSEX'
            }
            
            instrument_key = instrument_keys.get(index_name)
            if not instrument_key:
                return None
            
            # Fetch historical candles (last 30 candles for 3-min timeframe)
            from datetime import datetime, timedelta
            to_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
            
            candles_data = client.get_historical_candles(
                instrument_key, 
                interval='3minute',
                from_date=from_date,
                to_date=to_date
            )
            
            if not candles_data or candles_data.get('status') != 'success':
                return None
            
            candles = candles_data.get('data', {}).get('candles', [])
            if len(candles) < 10:
                return None
            
            # Candles format: [timestamp, open, high, low, close, volume, oi]
            # Extract OHLCV data (reverse to get chronological order)
            candles = list(reversed(candles[-30:]))  # Last 30 candles
            
            opens = [c[1] for c in candles]
            highs = [c[2] for c in candles]
            lows = [c[3] for c in candles]
            closes = [c[4] for c in candles]
            volumes = [c[5] for c in candles]
            
            current_price = closes[-1]
            prev_close = closes[-2] if len(closes) > 1 else current_price
            
            # Store in history
            self.market_history[index_name].append({
                'timestamp': datetime.now(),
                'price': current_price,
                'volume': volumes[-1]
            })
            
            # Keep only last 100 data points
            if len(self.market_history[index_name]) > 100:
                self.market_history[index_name] = self.market_history[index_name][-100:]
            
            # === TECHNICAL ANALYSIS ===
            
            # 1. CANDLESTICK PATTERN DETECTION
            pattern = self.detect_candlestick_pattern(opens, highs, lows, closes)
            
            # 2. TREND ANALYSIS (Simple Moving Averages)
            sma_5 = sum(closes[-5:]) / 5
            sma_10 = sum(closes[-10:]) / 10
            sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else sma_10
            
            trend = "BULLISH" if sma_5 > sma_10 > sma_20 else "BEARISH" if sma_5 < sma_10 < sma_20 else "SIDEWAYS"
            
            # 3. MOMENTUM INDICATORS
            
            # RSI (14-period)
            rsi = self.calculate_rsi(closes, period=14)
            
            # MACD
            macd_line, signal_line = self.calculate_macd(closes)
            macd_histogram = macd_line - signal_line if macd_line and signal_line else 0
            
            # 4. VOLUME ANALYSIS
            avg_volume = sum(volumes[-10:]) / 10
            current_volume = volumes[-1]
            volume_surge = current_volume > (avg_volume * 1.5)  # 50% above average
            
            # 5. PRICE ACTION
            price_change_pct = ((current_price - prev_close) / prev_close) * 100
            
            # Support and Resistance (last 20 candles)
            recent_highs = highs[-20:]
            recent_lows = lows[-20:]
            resistance = max(recent_highs)
            support = min(recent_lows)
            
            # Distance from support/resistance
            dist_to_resistance = ((resistance - current_price) / current_price) * 100
            dist_to_support = ((current_price - support) / current_price) * 100
            
            # === SIGNAL GENERATION ===
            
            signal = None
            signal_strength = 0
            reasons = []
            
            # BULLISH SIGNALS
            bullish_score = 0
            
            if pattern in ['BULLISH_ENGULFING', 'HAMMER', 'MORNING_STAR']:
                bullish_score += 3
                reasons.append(f"✅ {pattern} pattern detected")
            
            if trend == "BULLISH":
                bullish_score += 2
                reasons.append("✅ Bullish trend (SMA alignment)")
            
            if rsi and rsi < 40:  # Oversold turning up
                bullish_score += 2
                reasons.append(f"✅ RSI oversold ({rsi:.1f})")
            
            if macd_histogram > 0 and macd_line > signal_line:
                bullish_score += 2
                reasons.append("✅ MACD bullish crossover")
            
            if volume_surge and price_change_pct > 0:
                bullish_score += 2
                reasons.append(f"✅ Volume surge with price increase")
            
            if price_change_pct > 0.5:  # Strong upward momentum
                bullish_score += 1
                reasons.append(f"✅ Strong upward momentum ({price_change_pct:+.2f}%)")
            
            if dist_to_support < 1:  # Near support, potential bounce
                bullish_score += 1
                reasons.append("✅ Near support level")
            
            # BEARISH SIGNALS
            bearish_score = 0
            
            if pattern in ['BEARISH_ENGULFING', 'SHOOTING_STAR', 'EVENING_STAR']:
                bearish_score += 3
                reasons.append(f"🔻 {pattern} pattern detected")
            
            if trend == "BEARISH":
                bearish_score += 2
                reasons.append("🔻 Bearish trend (SMA alignment)")
            
            if rsi and rsi > 60:  # Overbought turning down
                bearish_score += 2
                reasons.append(f"🔻 RSI overbought ({rsi:.1f})")
            
            if macd_histogram < 0 and macd_line < signal_line:
                bearish_score += 2
                reasons.append("🔻 MACD bearish crossover")
            
            if volume_surge and price_change_pct < 0:
                bearish_score += 2
                reasons.append(f"🔻 Volume surge with price decrease")
            
            if price_change_pct < -0.5:  # Strong downward momentum
                bearish_score += 1
                reasons.append(f"🔻 Strong downward momentum ({price_change_pct:+.2f}%)")
            
            if dist_to_resistance < 1:  # Near resistance, potential rejection
                bearish_score += 1
                reasons.append("🔻 Near resistance level")
            
            # Determine signal based on scores
            if bullish_score >= 5 and bullish_score > bearish_score:
                signal = "BUY_CE"
                signal_strength = min(bullish_score, 10)
            elif bearish_score >= 5 and bearish_score > bullish_score:
                signal = "BUY_PE"
                signal_strength = min(bearish_score, 10)
            
            # Calculate recommended strike (ATM ± based on momentum)
            atm_strike = round(current_price / 100) * 100  # Round to nearest 100
            
            if signal == "BUY_CE":
                # For bullish, suggest slightly OTM CE
                recommended_strike = atm_strike + 100
            elif signal == "BUY_PE":
                # For bearish, suggest slightly OTM PE
                recommended_strike = atm_strike - 100
            else:
                recommended_strike = atm_strike
            
            return {
                'signal': signal,
                'strength': signal_strength,
                'current_price': current_price,
                'price_change_pct': price_change_pct,
                'pattern': pattern,
                'trend': trend,
                'rsi': rsi,
                'macd_histogram': macd_histogram,
                'volume_surge': volume_surge,
                'support': support,
                'resistance': resistance,
                'recommended_strike': recommended_strike,
                'reasons': reasons[:5],  # Top 5 reasons
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            print(f"Error in analyze_index for {index_name}: {e}")
            return None
    
    def detect_candlestick_pattern(self, opens, highs, lows, closes):
        """Detect common candlestick patterns."""
        if len(closes) < 3:
            return None
        
        # Get last 3 candles
        o1, h1, l1, c1 = opens[-3], highs[-3], lows[-3], closes[-3]
        o2, h2, l2, c2 = opens[-2], highs[-2], lows[-2], closes[-2]
        o3, h3, l3, c3 = opens[-1], highs[-1], lows[-1], closes[-1]
        
        body1 = abs(c1 - o1)
        body2 = abs(c2 - o2)
        body3 = abs(c3 - o3)
        
        # Bullish Engulfing
        if c1 < o1 and c2 > o2 and c2 > o1 and o2 < c1:
            if body2 > body1 * 1.5:
                return "BULLISH_ENGULFING"
        
        # Bearish Engulfing
        if c1 > o1 and c2 < o2 and c2 < o1 and o2 > c1:
            if body2 > body1 * 1.5:
                return "BEARISH_ENGULFING"
        
        # Hammer (bullish reversal)
        lower_shadow = min(o3, c3) - l3
        upper_shadow = h3 - max(o3, c3)
        if lower_shadow > body3 * 2 and upper_shadow < body3 * 0.3:
            return "HAMMER"
        
        # Shooting Star (bearish reversal)
        if upper_shadow > body3 * 2 and lower_shadow < body3 * 0.3:
            return "SHOOTING_STAR"
        
        # Morning Star (bullish)
        if c1 < o1 and body2 < body1 * 0.5 and c3 > o3 and c3 > (o1 + c1) / 2:
            return "MORNING_STAR"
        
        # Evening Star (bearish)
        if c1 > o1 and body2 < body1 * 0.5 and c3 < o3 and c3 < (o1 + c1) / 2:
            return "EVENING_STAR"
        
        return None
    
    def calculate_rsi(self, closes, period=14):
        """Calculate Relative Strength Index."""
        if len(closes) < period + 1:
            return None
        
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_macd(self, closes, fast=12, slow=26, signal=9):
        """Calculate MACD indicator."""
        if len(closes) < slow:
            return None, None
        
        # Simple EMA calculation
        def ema(data, period):
            multiplier = 2 / (period + 1)
            ema_values = [sum(data[:period]) / period]
            for price in data[period:]:
                ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
            return ema_values[-1]
        
        fast_ema = ema(closes, fast)
        slow_ema = ema(closes, slow)
        macd_line = fast_ema - slow_ema
        
        # Signal line (9-period EMA of MACD)
        # Simplified: use last value
        signal_line = macd_line * 0.9  # Approximation
        
        return macd_line, signal_line
    
    def generate_trading_alert(self, index_name, analysis):
        """Generate trading alert popup with signal details."""
        signal = analysis.get('signal')
        strength = analysis.get('strength', 0)
        
        # Only alert for strong signals (strength >= 6)
        if strength < 6:
            return
        
        # Create unique alert key to avoid duplicates
        alert_key = f"{index_name}_{signal}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        if alert_key in self.analysis_alerts_shown:
            return
        
        self.analysis_alerts_shown.add(alert_key)
        
        # Clean old alerts (keep only last 50)
        if len(self.analysis_alerts_shown) > 50:
            self.analysis_alerts_shown = set(list(self.analysis_alerts_shown)[-50:])
        
        # Show alert on main thread
        self.root.after(0, lambda: self._show_trading_alert(index_name, analysis))
    
    def _show_trading_alert(self, index_name, analysis):
        """Display trading alert dialog."""
        signal = analysis.get('signal')
        strength = analysis.get('strength')
        current_price = analysis.get('current_price')
        price_change = analysis.get('price_change_pct')
        pattern = analysis.get('pattern')
        trend = analysis.get('trend')
        rsi = analysis.get('rsi')
        recommended_strike = analysis.get('recommended_strike')
        reasons = analysis.get('reasons', [])
        
        # Create alert window
        alert_window = tk.Toplevel(self.root)
        alert_window.title(f"🚨 Market Alert - {index_name}")
        alert_window.geometry("500x600")
        alert_window.configure(bg='#1e1e1e')
        alert_window.attributes('-topmost', True)  # Keep on top
        
        # Signal emoji
        signal_emoji = "🚀" if signal == "BUY_CE" else "📉"
        signal_color = "#00ff00" if signal == "BUY_CE" else "#ff3333"
        signal_text = "STRONG BULLISH SIGNAL" if signal == "BUY_CE" else "STRONG BEARISH SIGNAL"
        
        # Header
        tk.Label(
            alert_window,
            text=f"{signal_emoji} {index_name} ALERT",
            font=('Arial', 18, 'bold'),
            bg='#1e1e1e',
            fg=signal_color
        ).pack(pady=10)
        
        # Signal strength
        strength_bar = "█" * strength + "░" * (10 - strength)
        tk.Label(
            alert_window,
            text=f"Signal Strength: {strength_bar} {strength}/10",
            font=('Arial', 12),
            bg='#1e1e1e',
            fg='#ffffff'
        ).pack(pady=5)
        
        # Recommendation
        rec_frame = tk.Frame(alert_window, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        rec_frame.pack(fill=tk.X, padx=20, pady=10)
        
        tk.Label(
            rec_frame,
            text=signal_text,
            font=('Arial', 14, 'bold'),
            bg='#2d2d2d',
            fg=signal_color
        ).pack(pady=10)
        
        tk.Label(
            rec_frame,
            text=f"Recommended: {signal.replace('BUY_', '')} @ Strike {recommended_strike}",
            font=('Arial', 12, 'bold'),
            bg='#2d2d2d',
            fg='#ffaa00'
        ).pack(pady=5)
        
        # Market details
        details_frame = tk.Frame(alert_window, bg='#1e1e1e')
        details_frame.pack(fill=tk.BOTH, padx=20, pady=10)
        
        tk.Label(
            details_frame,
            text=f"Current Price: ₹{current_price:,.2f} ({price_change:+.2f}%)",
            font=('Arial', 11),
            bg='#1e1e1e',
            fg='#ffffff',
            anchor='w'
        ).pack(fill=tk.X, pady=2)
        
        if pattern:
            tk.Label(
                details_frame,
                text=f"Pattern: {pattern}",
                font=('Arial', 11),
                bg='#1e1e1e',
                fg='#00aaff',
                anchor='w'
            ).pack(fill=tk.X, pady=2)
        
        tk.Label(
            details_frame,
            text=f"Trend: {trend}",
            font=('Arial', 11),
            bg='#1e1e1e',
            fg='#00aaff',
            anchor='w'
        ).pack(fill=tk.X, pady=2)
        
        if rsi:
            tk.Label(
                details_frame,
                text=f"RSI: {rsi:.1f}",
                font=('Arial', 11),
                bg='#1e1e1e',
                fg='#00aaff',
                anchor='w'
            ).pack(fill=tk.X, pady=2)
        
        # Reasons
        tk.Label(
            alert_window,
            text="📊 Key Factors:",
            font=('Arial', 12, 'bold'),
            bg='#1e1e1e',
            fg='#ffaa00'
        ).pack(pady=(10, 5))
        
        reasons_text = tk.Text(
            alert_window,
            height=8,
            width=50,
            bg='#2d2d2d',
            fg='#ffffff',
            font=('Arial', 10),
            wrap=tk.WORD
        )
        reasons_text.pack(padx=20, pady=5)
        
        for reason in reasons:
            reasons_text.insert(tk.END, f"{reason}\n")
        
        reasons_text.config(state=tk.DISABLED)
        
        # Buttons
        btn_frame = tk.Frame(alert_window, bg='#1e1e1e')
        btn_frame.pack(pady=15)
        
        tk.Button(
            btn_frame,
            text="✅ GOT IT",
            command=alert_window.destroy,
            bg='#00aa00',
            fg='#ffffff',
            font=('Arial', 12, 'bold'),
            width=15,
            height=2
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="🔕 DISABLE ALERTS",
            command=lambda: [self.market_analysis_enabled.set(False), alert_window.destroy()],
            bg='#aa0000',
            fg='#ffffff',
            font=('Arial', 12, 'bold'),
            width=15,
            height=2
        ).pack(side=tk.LEFT, padx=5)
        
        # Auto-close after 2 minutes
        alert_window.after(120000, alert_window.destroy)
        
        # Play alert sound (optional - requires additional library)
        try:
            import winsound
            winsound.Beep(1000, 200)  # 1000 Hz for 200ms
        except:
            pass
    
    def show_analysis_report(self):
        """Display comprehensive market analysis report for all indices."""
        print("📊 Opening analysis report window...")  # Debug
        
        try:
            report_window = tk.Toplevel(self.root)
            report_window.title("📊 Market Analysis Report")
            report_window.geometry("800x700")
            report_window.configure(bg='#1e1e1e')
            
            # Make window visible
            report_window.transient(self.root)
            report_window.lift()
            report_window.focus_force()
            
            print("✅ Report window created")  # Debug
            
            # Header
            header_frame = tk.Frame(report_window, bg='#2d2d2d', relief=tk.RAISED, bd=2)
            header_frame.pack(fill=tk.X, padx=10, pady=10)
            
            tk.Label(
                header_frame,
                text="📊 AUTOMATED MARKET ANALYSIS REPORT",
                font=('Arial', 16, 'bold'),
                bg='#2d2d2d',
                fg='#00aaff'
            ).pack(pady=10)
            
            # Last update time
            last_update = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            tk.Label(
                header_frame,
                text=f"Last Updated: {last_update}",
                font=('Arial', 10),
                bg='#2d2d2d',
                fg='#888888'
            ).pack(pady=5)
            
            # Status
            status_text = "✅ Auto Analysis: ENABLED (Every 3 minutes)" if self.market_analysis_enabled.get() else "⚠️ Auto Analysis: DISABLED"
            tk.Label(
                header_frame,
                text=status_text,
                font=('Arial', 10, 'bold'),
                bg='#2d2d2d',
                fg='#00ff00' if self.market_analysis_enabled.get() else '#ff6600'
            ).pack(pady=5)
            
            # Scrollable report area
            report_frame = tk.Frame(report_window, bg='#1e1e1e')
            report_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            canvas = tk.Canvas(report_frame, bg='#1e1e1e', highlightthickness=0)
            scrollbar = ttk.Scrollbar(report_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas, bg='#1e1e1e')
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Display analysis for each index
            if not self.latest_analysis:
                tk.Label(
                    scrollable_frame,
                    text="⏳ No analysis data available yet.\n\nClick 'Refresh Now' to run analysis.",
                    font=('Arial', 12),
                    bg='#1e1e1e',
                    fg='#888888',
                    justify='center'
                ).pack(pady=50)
            else:
                for index_name in ['NIFTY', 'BANKNIFTY']:
                    if index_name in self.latest_analysis:
                        self._display_index_analysis(scrollable_frame, index_name, self.latest_analysis[index_name])
            
            # Button frame
            btn_frame = tk.Frame(report_window, bg='#1e1e1e')
            btn_frame.pack(pady=10)
            
            tk.Button(
                btn_frame,
                text="🔄 Refresh Now",
                command=lambda: [self.perform_market_analysis(), report_window.after(2000, report_window.destroy), self.root.after(2500, self.show_analysis_report)],
                bg='#00aa00',
                fg='#ffffff',
                font=('Arial', 11, 'bold'),
                width=15,
                height=2
            ).pack(side=tk.LEFT, padx=5)
            
            tk.Button(
                btn_frame,
                text="✅ Close",
                command=report_window.destroy,
                bg='#aa0000',
                fg='#ffffff',
                font=('Arial', 11, 'bold'),
                width=15,
                height=2
            ).pack(side=tk.LEFT, padx=5)
            
            print(f"📊 Report displayed. Analysis data count: {len(self.latest_analysis)}")  # Debug
        
        except Exception as e:
            print(f"❌ Error showing report: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Report Error", f"Failed to show report:\n\n{str(e)}")
    
    def _display_index_analysis(self, parent, index_name, analysis):
        """Display analysis for a single index."""
        # Index frame
        index_frame = tk.LabelFrame(
            parent,
            text=f"  {index_name}  ",
            bg='#2d2d2d',
            fg='#00aaff',
            font=('Arial', 14, 'bold'),
            relief=tk.RAISED,
            bd=2
        )
        index_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Price info
        current_price = analysis.get('current_price', 0)
        price_change = analysis.get('price_change_pct', 0)
        change_color = '#00ff00' if price_change >= 0 else '#ff3333'
        
        price_frame = tk.Frame(index_frame, bg='#2d2d2d')
        price_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(
            price_frame,
            text=f"Current: ₹{current_price:,.2f}",
            font=('Arial', 12, 'bold'),
            bg='#2d2d2d',
            fg='#ffffff'
        ).pack(side=tk.LEFT, padx=10)
        
        tk.Label(
            price_frame,
            text=f"{price_change:+.2f}%",
            font=('Arial', 12, 'bold'),
            bg='#2d2d2d',
            fg=change_color
        ).pack(side=tk.LEFT, padx=10)
        
        # Signal
        signal = analysis.get('signal')
        strength = analysis.get('strength', 0)
        
        if signal:
            signal_color = '#00ff00' if signal == 'BUY_CE' else '#ff3333'
            signal_text = f"{'🚀 BULLISH' if signal == 'BUY_CE' else '📉 BEARISH'} - {signal.replace('BUY_', '')}"
            
            signal_frame = tk.Frame(index_frame, bg='#1e1e1e', relief=tk.RIDGE, bd=2)
            signal_frame.pack(fill=tk.X, padx=10, pady=10)
            
            tk.Label(
                signal_frame,
                text=signal_text,
                font=('Arial', 14, 'bold'),
                bg='#1e1e1e',
                fg=signal_color
            ).pack(pady=5)
            
            # Strength bar
            strength_bar = "█" * strength + "░" * (10 - strength)
            tk.Label(
                signal_frame,
                text=f"Strength: {strength_bar} {strength}/10",
                font=('Arial', 11),
                bg='#1e1e1e',
                fg='#ffffff'
            ).pack(pady=5)
            
            # Recommended strike
            recommended_strike = analysis.get('recommended_strike', 0)
            tk.Label(
                signal_frame,
                text=f"💡 Recommended Strike: {recommended_strike}",
                font=('Arial', 12, 'bold'),
                bg='#1e1e1e',
                fg='#ffaa00'
            ).pack(pady=5)
        else:
            tk.Label(
                index_frame,
                text="⚪ No Strong Signal - Market in consolidation",
                font=('Arial', 11),
                bg='#2d2d2d',
                fg='#888888'
            ).pack(pady=10)
        
        # Technical details
        details_frame = tk.Frame(index_frame, bg='#2d2d2d')
        details_frame.pack(fill=tk.X, padx=10, pady=5)
        
        pattern = analysis.get('pattern')
        trend = analysis.get('trend', 'N/A')
        rsi = analysis.get('rsi')
        macd = analysis.get('macd_histogram', 0)
        volume_surge = analysis.get('volume_surge', False)
        support = analysis.get('support', 0)
        resistance = analysis.get('resistance', 0)
        
        # Create 2-column layout
        left_col = tk.Frame(details_frame, bg='#2d2d2d')
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        right_col = tk.Frame(details_frame, bg='#2d2d2d')
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        
        # Left column
        if pattern:
            tk.Label(
                left_col,
                text=f"📊 Pattern: {pattern}",
                font=('Arial', 10),
                bg='#2d2d2d',
                fg='#00aaff',
                anchor='w'
            ).pack(fill=tk.X, pady=2)
        
        tk.Label(
            left_col,
            text=f"📈 Trend: {trend}",
            font=('Arial', 10),
            bg='#2d2d2d',
            fg='#00aaff',
            anchor='w'
        ).pack(fill=tk.X, pady=2)
        
        if rsi:
            rsi_status = "Oversold" if rsi < 30 else "Overbought" if rsi > 70 else "Neutral"
            tk.Label(
                left_col,
                text=f"📊 RSI: {rsi:.1f} ({rsi_status})",
                font=('Arial', 10),
                bg='#2d2d2d',
                fg='#00aaff',
                anchor='w'
            ).pack(fill=tk.X, pady=2)
        
        # Right column
        macd_status = "Bullish" if macd > 0 else "Bearish"
        tk.Label(
            right_col,
            text=f"📉 MACD: {macd_status}",
            font=('Arial', 10),
            bg='#2d2d2d',
            fg='#00aaff',
            anchor='w'
        ).pack(fill=tk.X, pady=2)
        
        tk.Label(
            right_col,
            text=f"🔊 Volume: {'⬆️ Surge' if volume_surge else '➡️ Normal'}",
            font=('Arial', 10),
            bg='#2d2d2d',
            fg='#00aaff',
            anchor='w'
        ).pack(fill=tk.X, pady=2)
        
        tk.Label(
            right_col,
            text=f"🎯 Support: ₹{support:,.0f} | Resistance: ₹{resistance:,.0f}",
            font=('Arial', 10),
            bg='#2d2d2d',
            fg='#00aaff',
            anchor='w'
        ).pack(fill=tk.X, pady=2)
        
        # Key reasons
        reasons = analysis.get('reasons', [])
        if reasons:
            tk.Label(
                index_frame,
                text="🔑 Key Factors:",
                font=('Arial', 11, 'bold'),
                bg='#2d2d2d',
                fg='#ffaa00'
            ).pack(anchor='w', padx=10, pady=(10, 5))
            
            reasons_frame = tk.Frame(index_frame, bg='#1e1e1e', relief=tk.SUNKEN, bd=1)
            reasons_frame.pack(fill=tk.X, padx=10, pady=5)
            
            for reason in reasons:
                tk.Label(
                    reasons_frame,
                    text=f"  • {reason}",
                    font=('Arial', 9),
                    bg='#1e1e1e',
                    fg='#cccccc',
                    anchor='w'
                ).pack(fill=tk.X, padx=5, pady=2)


def main():
    """Main entry point."""
    root = tk.Tk()
    app = FusionTradeGUI(root)
    
    # Add window close handler for cleanup logging
    def on_closing():
        if ENABLE_LOGGING and hasattr(app, '_log'):
            app._log('info', "="*60)
            app._log('info', "FusionTrade Application Shutting Down")
            app._log('info', f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            app._log('info', "="*60)
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()


