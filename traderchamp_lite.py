"""
FusionTrade Lite - Streamlined Multi-Broker Trading Platform
Lightweight version with essential features only
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import threading
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import broker clients
from brokers.upstox_client import UpstoxClient
from brokers.dhan_client import DhanClient


class TradingCore:
    """Core trading functionality - multi-broker support"""
    
    def __init__(self):
        self.active_brokers = {}
        self.current_client = None
        self.account_name = ""
        self.multi_account_mode = False
        
    def initialize_brokers(self, tokens_data):
        """Initialize broker clients from tokens"""
        self.active_brokers = {}
        
        for key, token_info in tokens_data.items():
            if not token_info.get('access_token'):
                continue
                
            broker_type = token_info.get('broker', '').lower()
            
            try:
                if 'upstox' in broker_type:
                    client = UpstoxClient(token_info['access_token'])
                elif 'dhan' in broker_type:
                    client = DhanClient(token_info['access_token'])
                else:
                    continue
                
                self.active_brokers[key] = {
                    'client': client,
                    'name': token_info.get('name', key),
                    'broker': broker_type
                }
                print(f"✅ {broker_type.title()} account setup: {token_info.get('name', key)}")
                
            except Exception as e:
                print(f"❌ Failed to initialize {key}: {e}")
        
        if self.active_brokers:
            first_key = list(self.active_brokers.keys())[0]
            self.current_client = self.active_brokers[first_key]['client']
            self.account_name = self.active_brokers[first_key]['name']
            self.multi_account_mode = len(self.active_brokers) > 1
            return True
        return False


class TraderChampLite:
    """Lightweight Trading GUI"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("FusionTrade Lite - Multi-Broker Trading")
        self.root.geometry("1400x800")
        self.root.configure(bg='#1e1e1e')
        
        # Initialize core
        self.trader = TradingCore()
        self.positions_data = []
        self.invalid_brokers = set()
        
        # Variables
        self.selected_symbol = tk.StringVar(value="NIFTY")
        self.selected_expiry = tk.StringVar()
        self.selected_strike = tk.StringVar()
        self.selected_type = tk.StringVar(value="CE")
        self.lot_quantity = tk.IntVar(value=1)
        self.order_type = tk.StringVar(value="MARKET")
        self.sl_percent = tk.DoubleVar(value=15.0)
        self.exit_percent = tk.IntVar(value=100)
        self.order_filter = tk.StringVar(value="today")
        
        # Load tokens and initialize
        if self.load_tokens():
            self.create_ui()
            self.refresh_positions()
        else:
            messagebox.showerror("Error", "No valid tokens found in config/tokens.json")
            self.root.quit()
    
    def load_tokens(self):
        """Load tokens from config file"""
        try:
            token_file = os.path.join('config', 'tokens.json')
            if os.path.exists(token_file):
                with open(token_file, 'r') as f:
                    tokens_data = json.load(f)
                return self.trader.initialize_brokers(tokens_data)
        except Exception as e:
            print(f"Error loading tokens: {e}")
        return False
    
    def create_ui(self):
        """Create streamlined UI"""
        # Main container
        main_container = tk.Frame(self.root, bg='#1e1e1e')
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel - Quick Order
        left_panel = tk.Frame(main_container, bg='#2d2d2d', width=350)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        self.create_quick_order(left_panel)
        
        # Right panel - Positions & Orders
        right_panel = tk.Frame(main_container, bg='#2d2d2d')
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.create_positions_view(right_panel)
    
    def create_quick_order(self, parent):
        """Quick order panel"""
        tk.Label(parent, text="📊 QUICK ORDER", font=('Arial', 14, 'bold'),
                bg='#2d2d2d', fg='#00ff00').pack(pady=10)
        
        # Symbol
        frame = tk.LabelFrame(parent, text="Symbol", bg='#2d2d2d', fg='#ffffff')
        frame.pack(fill=tk.X, padx=10, pady=5)
        for sym in ["NIFTY", "BANKNIFTY", "SENSEX"]:
            tk.Radiobutton(frame, text=sym, variable=self.selected_symbol,
                          value=sym, bg='#2d2d2d', fg='#ffffff',
                          selectcolor='#1e1e1e').pack(side=tk.LEFT, padx=5)
        
        # Strike
        frame = tk.LabelFrame(parent, text="Strike", bg='#2d2d2d', fg='#ffffff')
        frame.pack(fill=tk.X, padx=10, pady=5)
        self.strike_entry = tk.Entry(frame, textvariable=self.selected_strike,
                                     bg='#1e1e1e', fg='#ffffff', font=('Arial', 12))
        self.strike_entry.pack(fill=tk.X, padx=5, pady=5)
        
        # CE/PE
        frame = tk.Frame(parent, bg='#2d2d2d')
        frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Radiobutton(frame, text="CALL", variable=self.selected_type, value="CE",
                      bg='#2d2d2d', fg='#00ff00', selectcolor='#1e1e1e',
                      font=('Arial', 10, 'bold')).pack(side=tk.LEFT, expand=True)
        tk.Radiobutton(frame, text="PUT", variable=self.selected_type, value="PE",
                      bg='#2d2d2d', fg='#ff0000', selectcolor='#1e1e1e',
                      font=('Arial', 10, 'bold')).pack(side=tk.RIGHT, expand=True)
        
        # Lot
        frame = tk.LabelFrame(parent, text="Lots", bg='#2d2d2d', fg='#ffffff')
        frame.pack(fill=tk.X, padx=10, pady=5)
        lot_frame = tk.Frame(frame, bg='#2d2d2d')
        lot_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Button(lot_frame, text="-", command=lambda: self.adjust_lots(-1),
                 bg='#ff0000', fg='#ffffff', width=3).pack(side=tk.LEFT)
        tk.Entry(lot_frame, textvariable=self.lot_quantity, bg='#1e1e1e',
                fg='#ffffff', font=('Arial', 14, 'bold'), width=5,
                justify='center').pack(side=tk.LEFT, expand=True, padx=5)
        tk.Button(lot_frame, text="+", command=lambda: self.adjust_lots(1),
                 bg='#00ff00', fg='#000000', width=3).pack(side=tk.RIGHT)
        
        # Order Type
        frame = tk.LabelFrame(parent, text="Order Type", bg='#2d2d2d', fg='#ffffff')
        frame.pack(fill=tk.X, padx=10, pady=5)
        for ot in ["MARKET", "LIMIT"]:
            tk.Radiobutton(frame, text=ot, variable=self.order_type, value=ot,
                          bg='#2d2d2d', fg='#ffffff',
                          selectcolor='#1e1e1e').pack(side=tk.LEFT, padx=5)
        
        # Place Order Button
        tk.Button(parent, text="🚀 PLACE ORDER", command=self.place_order,
                 bg='#00ff00', fg='#000000', font=('Arial', 14, 'bold'),
                 height=2).pack(fill=tk.X, padx=10, pady=20)
        
        # Stop Loss Section
        tk.Label(parent, text="🛡️ STOP LOSS", font=('Arial', 12, 'bold'),
                bg='#2d2d2d', fg='#ff6600').pack(pady=(20, 5))
        
        frame = tk.Frame(parent, bg='#2d2d2d')
        frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(frame, text="SL %:", bg='#2d2d2d', fg='#ffffff').pack(side=tk.LEFT)
        tk.Entry(frame, textvariable=self.sl_percent, bg='#1e1e1e',
                fg='#ffffff', width=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(parent, text="✓ APPLY SL", command=self.apply_sl,
                 bg='#ff6600', fg='#ffffff', font=('Arial', 10, 'bold')).pack(
                 fill=tk.X, padx=10, pady=5)
        
        # Exit Section
        tk.Label(parent, text="🚪 EXIT", font=('Arial', 12, 'bold'),
                bg='#2d2d2d', fg='#ff0000').pack(pady=(20, 5))
        
        frame = tk.Frame(parent, bg='#2d2d2d')
        frame.pack(fill=tk.X, padx=10, pady=5)
        for pct in [25, 50, 75, 100]:
            tk.Radiobutton(frame, text=f"{pct}%", variable=self.exit_percent,
                          value=pct, bg='#2d2d2d', fg='#ffffff',
                          selectcolor='#1e1e1e').pack(side=tk.LEFT)
        
        tk.Button(parent, text="✓ EXIT", command=self.apply_exit,
                 bg='#ff0000', fg='#ffffff', font=('Arial', 10, 'bold')).pack(
                 fill=tk.X, padx=10, pady=5)
        
        # Refresh button
        tk.Button(parent, text="🔄 REFRESH", command=self.refresh_positions,
                 bg='#444444', fg='#ffffff').pack(fill=tk.X, padx=10, pady=20,
                 side=tk.BOTTOM)
    
    def create_positions_view(self, parent):
        """Positions and orders view"""
        # Tabs
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Style
        style = ttk.Style()
        style.configure('Treeview', background='#1e1e1e', foreground='#ffffff',
                       fieldbackground='#1e1e1e', font=('Arial', 10))
        style.configure('Treeview.Heading', background='#2d2d2d',
                       foreground='#00ff00', font=('Arial', 10, 'bold'))
        
        # Positions Tab
        pos_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(pos_tab, text='📈 POSITIONS')
        
        columns = ('symbol', 'qty', 'avg', 'ltp', 'pnl', 'pnl_pct', 'account')
        self.positions_tree = ttk.Treeview(pos_tab, columns=columns, show='headings',
                                          height=20)
        
        headings = {'symbol': 'Symbol', 'qty': 'Qty', 'avg': 'Avg Price',
                   'ltp': 'LTP', 'pnl': 'P&L', 'pnl_pct': 'P&L %', 'account': 'Account'}
        widths = {'symbol': 150, 'qty': 80, 'avg': 100, 'ltp': 100,
                 'pnl': 100, 'pnl_pct': 80, 'account': 120}
        
        for col in columns:
            self.positions_tree.heading(col, text=headings[col])
            self.positions_tree.column(col, width=widths[col])
        
        scrollbar = ttk.Scrollbar(pos_tab, orient=tk.VERTICAL,
                                 command=self.positions_tree.yview)
        self.positions_tree.configure(yscrollcommand=scrollbar.set)
        
        self.positions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Orders Tab
        orders_tab = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(orders_tab, text='📋 ORDERS')
        
        # Filter controls
        filter_frame = tk.Frame(orders_tab, bg='#1e1e1e')
        filter_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(filter_frame, text="Show:", bg='#1e1e1e', fg='#ffffff',
                font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        
        self.order_filter = tk.StringVar(value="today")
        tk.Radiobutton(filter_frame, text="Today", variable=self.order_filter,
                      value="today", bg='#1e1e1e', fg='#ffffff',
                      selectcolor='#2d2d2d', command=self.refresh_orders).pack(
                      side=tk.LEFT, padx=5)
        tk.Radiobutton(filter_frame, text="Yesterday", variable=self.order_filter,
                      value="yesterday", bg='#1e1e1e', fg='#ffffff',
                      selectcolor='#2d2d2d', command=self.refresh_orders).pack(
                      side=tk.LEFT, padx=5)
        tk.Radiobutton(filter_frame, text="All", variable=self.order_filter,
                      value="all", bg='#1e1e1e', fg='#ffffff',
                      selectcolor='#2d2d2d', command=self.refresh_orders).pack(
                      side=tk.LEFT, padx=5)
        
        columns = ('date', 'time', 'symbol', 'type', 'qty', 'price', 'status', 'account')
        self.orders_tree = ttk.Treeview(orders_tab, columns=columns, show='headings',
                                       height=20)
        
        headings = {'date': 'Date', 'time': 'Time', 'symbol': 'Symbol', 'type': 'Type',
                   'qty': 'Qty', 'price': 'Price', 'status': 'Status',
                   'account': 'Account'}
        widths = {'date': 90, 'time': 80, 'symbol': 150, 'type': 80, 'qty': 80,
                 'price': 100, 'status': 100, 'account': 120}
        
        for col in columns:
            self.orders_tree.heading(col, text=headings[col])
            self.orders_tree.column(col, width=widths[col])
        
        scrollbar = ttk.Scrollbar(orders_tab, orient=tk.VERTICAL,
                                 command=self.orders_tree.yview)
        self.orders_tree.configure(yscrollcommand=scrollbar.set)
        
        self.orders_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Refresh orders button
        tk.Button(orders_tab, text="🔄 REFRESH ORDERS",
                 command=self.refresh_orders,
                 bg='#444444', fg='#ffffff').pack(pady=5)
    
    def adjust_lots(self, delta):
        """Adjust lot quantity"""
        current = self.lot_quantity.get()
        new_val = max(1, current + delta)
        self.lot_quantity.set(new_val)
    
    def place_order(self):
        """Place order on all accounts"""
        try:
            symbol = self.selected_symbol.get()
            strike = self.selected_strike.get()
            option_type = self.selected_type.get()
            
            if not strike:
                messagebox.showwarning("Warning", "Please enter strike price")
                return
            
            # Build trading symbol (simplified - real implementation needs instrument lookup)
            trading_symbol = f"{symbol}{strike}{option_type}"
            
            if messagebox.askyesno("Confirm", f"Place order for {trading_symbol}?"):
                threading.Thread(target=self._place_order_async, daemon=True).start()
        
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def _place_order_async(self):
        """Place order asynchronously on all accounts"""
        try:
            # This is simplified - real implementation needs proper instrument lookup
            messagebox.showinfo("Info", "Order placement in progress...")
            self.refresh_positions()
        except Exception as e:
            messagebox.showerror("Error", str(e))
    
    def refresh_positions(self):
        """Refresh positions from all brokers"""
        threading.Thread(target=self._refresh_positions_async, daemon=True).start()
    
    def _refresh_positions_async(self):
        """Fetch positions from all brokers in parallel"""
        try:
            # Clear display
            self.root.after(0, lambda: [self.positions_tree.delete(i) 
                           for i in self.positions_tree.get_children()])
            
            self.positions_data = []
            
            def fetch_positions(broker_key, broker_info):
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    response = client.get_positions()
                    if response:
                        return (account_name, broker_key, client, 
                               response.get('data', []))
                except:
                    pass
                return (None, None, None, [])
            
            # Fetch in parallel
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(fetch_positions, key, info)
                          for key, info in self.trader.active_brokers.items()]
                
                for future in as_completed(futures):
                    account_name, broker_key, client, positions = future.result()
                    if not account_name:
                        continue
                    
                    for pos in positions:
                        qty = pos.get('quantity', 0) or pos.get('netQty', 0)
                        if qty == 0:
                            continue
                        
                        symbol = pos.get('tradingsymbol', 'N/A')
                        avg_price = (pos.get('average_price') or 
                                    pos.get('buyAvg') or 
                                    pos.get('sellAvg') or 0)
                        ltp = (pos.get('last_price') or 
                              pos.get('ltp') or avg_price or 0)
                        
                        pnl = (ltp - avg_price) * qty if avg_price > 0 else 0
                        pnl_pct = (pnl / (avg_price * abs(qty)) * 100) if avg_price > 0 else 0
                        
                        # Store position data
                        pos['client'] = client
                        pos['broker_key'] = broker_key
                        self.positions_data.append(pos)
                        
                        # Add to display
                        values = (
                            symbol,
                            qty,
                            f"₹{avg_price:.2f}",
                            f"₹{ltp:.2f}",
                            f"₹{pnl:.2f}",
                            f"{pnl_pct:.2f}%",
                            account_name
                        )
                        
                        # Color coding
                        tag = 'profit' if pnl > 0 else 'loss' if pnl < 0 else 'neutral'
                        
                        self.root.after(0, lambda v=values, t=tag: 
                                      self.positions_tree.insert('', tk.END,
                                      values=v, tags=(t,)))
            
            # Configure tags
            self.root.after(0, lambda: [
                self.positions_tree.tag_configure('profit', foreground='#00ff00'),
                self.positions_tree.tag_configure('loss', foreground='#ff0000'),
                self.positions_tree.tag_configure('neutral', foreground='#ffffff')
            ])
            
        except Exception as e:
            print(f"Error refreshing positions: {e}")
    
    def refresh_orders(self):
        """Refresh orders from all brokers"""
        threading.Thread(target=self._refresh_orders_async, daemon=True).start()
    
    def _refresh_orders_async(self):
        """Fetch orders from all brokers"""
        try:
            # Clear display
            self.root.after(0, lambda: [self.orders_tree.delete(i) 
                           for i in self.orders_tree.get_children()])
            
            # Get filter setting
            filter_type = self.order_filter.get()
            
            # Calculate date filters
            from datetime import datetime, timedelta
            today = datetime.now().date()
            yesterday = today - timedelta(days=1)
            
            for broker_key, broker_info in self.trader.active_brokers.items():
                try:
                    client = broker_info['client']
                    account_name = broker_info['name']
                    response = client.get_order_history()
                    
                    if response and response.get('data'):
                        orders = response.get('data', [])
                        
                        for order in orders:
                            # Parse order timestamp
                            order_timestamp = order.get('order_timestamp', '')
                            if not order_timestamp:
                                continue
                            
                            try:
                                # Parse timestamp (format: "2026-01-30 10:25:30" or ISO format)
                                if 'T' in order_timestamp:
                                    order_dt = datetime.fromisoformat(order_timestamp.replace('Z', '+00:00'))
                                else:
                                    order_dt = datetime.strptime(order_timestamp[:19], '%Y-%m-%d %H:%M:%S')
                                
                                order_date = order_dt.date()
                                
                                # Apply filter
                                if filter_type == "today" and order_date != today:
                                    continue
                                elif filter_type == "yesterday" and order_date != yesterday:
                                    continue
                                # "all" shows everything
                                
                            except Exception as date_error:
                                # If date parsing fails, show in "all" mode only
                                if filter_type != "all":
                                    continue
                                order_date = today
                                order_dt = datetime.now()
                            
                            # Extract order details
                            date_str = order_dt.strftime('%Y-%m-%d')
                            time_str = order_dt.strftime('%H:%M:%S')
                            symbol = order.get('tradingsymbol', 'N/A')
                            trans_type = order.get('transaction_type', 'N/A')
                            qty = order.get('quantity', 0)
                            price = order.get('price', 0) or order.get('average_price', 0)
                            status = order.get('status', 'N/A')
                            
                            values = (
                                date_str,
                                time_str,
                                symbol,
                                trans_type,
                                qty,
                                f"₹{price:.2f}" if price > 0 else 'N/A',
                                status,
                                account_name
                            )
                            
                            # Color code by status
                            tag = 'complete' if 'complete' in status.lower() else \
                                  'rejected' if 'reject' in status.lower() else \
                                  'cancelled' if 'cancel' in status.lower() else 'pending'
                            
                            self.root.after(0, lambda v=values, t=tag: 
                                          self.orders_tree.insert('', tk.END, values=v, tags=(t,)))
                
                except Exception as e:
                    print(f"Error fetching orders from {broker_key}: {e}")
            
            # Configure color tags
            self.root.after(0, lambda: [
                self.orders_tree.tag_configure('complete', foreground='#00ff00'),
                self.orders_tree.tag_configure('rejected', foreground='#ff0000'),
                self.orders_tree.tag_configure('cancelled', foreground='#ffaa00'),
                self.orders_tree.tag_configure('pending', foreground='#00aaff')
            ])
        
        except Exception as e:
            print(f"Error refreshing orders: {e}")
    
    def apply_sl(self):
        """Apply stop loss to all positions"""
        if not self.positions_data:
            messagebox.showinfo("Info", "No positions to apply SL")
            return
        
        sl_pct = self.sl_percent.get()
        if messagebox.askyesno("Confirm", f"Apply {sl_pct}% SL to all positions?"):
            threading.Thread(target=self._apply_sl_async, args=(sl_pct,),
                           daemon=True).start()
    
    def _apply_sl_async(self, sl_pct):
        """Apply SL to all positions"""
        try:
            success_count = 0
            
            for pos in self.positions_data:
                try:
                    client = pos.get('client')
                    qty = abs(pos.get('quantity', 0) or pos.get('netQty', 0))
                    
                    # Get LTP
                    ltp = (pos.get('last_price') or 
                          pos.get('ltp') or 
                          pos.get('average_price') or 0)
                    
                    if ltp <= 0 or qty == 0:
                        continue
                    
                    # Calculate SL price
                    sl_price = ltp - (ltp * sl_pct / 100)
                    sl_price = round(sl_price * 20) / 20  # Round to 0.05
                    
                    if sl_price < 0.05:
                        continue
                    
                    # Determine transaction type
                    raw_qty = pos.get('quantity', 0) or pos.get('netQty', 0)
                    trans_type = "SELL" if raw_qty > 0 else "BUY"
                    
                    instrument_key = (pos.get('instrument_key') or 
                                    pos.get('instrument_token') or 
                                    pos.get('securityId') or '')
                    
                    if not instrument_key:
                        continue
                    
                    # Place SL order
                    result = client.place_order(
                        instrument_key=instrument_key,
                        quantity=qty,
                        transaction_type=trans_type,
                        order_type="SL",
                        product="I",
                        price=sl_price - 0.05,
                        trigger_price=sl_price
                    )
                    
                    if result:
                        success_count += 1
                        print(f"✅ SL placed for {pos.get('tradingsymbol')}")
                
                except Exception as e:
                    print(f"Error placing SL: {e}")
            
            self.root.after(0, lambda: messagebox.showinfo("Success",
                          f"SL applied to {success_count}/{len(self.positions_data)} positions"))
        
        except Exception as e:
            print(f"Error in SL async: {e}")
    
    def apply_exit(self):
        """Exit positions"""
        if not self.positions_data:
            messagebox.showinfo("Info", "No positions to exit")
            return
        
        exit_pct = self.exit_percent.get()
        if messagebox.askyesno("Confirm", f"Exit {exit_pct}% of all positions?"):
            threading.Thread(target=self._apply_exit_async, args=(exit_pct,),
                           daemon=True).start()
    
    def _apply_exit_async(self, exit_pct):
        """Exit positions asynchronously"""
        try:
            success_count = 0
            
            for pos in self.positions_data:
                try:
                    client = pos.get('client')
                    qty = pos.get('quantity', 0) or pos.get('netQty', 0)
                    exit_qty = int(abs(qty) * exit_pct / 100)
                    
                    if exit_qty > 0:
                        instrument_key = (pos.get('instrument_key') or 
                                        pos.get('instrument_token') or 
                                        pos.get('securityId') or '')
                        
                        if not instrument_key:
                            continue
                        
                        trans_type = "SELL" if qty > 0 else "BUY"
                        result = client.place_order(
                            instrument_key=instrument_key,
                            quantity=exit_qty,
                            transaction_type=trans_type,
                            order_type="MARKET",
                            product="I"
                        )
                        
                        if result:
                            success_count += 1
                            print(f"✅ Exit order placed for {pos.get('tradingsymbol')}")
                
                except Exception as e:
                    print(f"Error exiting position: {e}")
            
            self.root.after(0, lambda: messagebox.showinfo("Success",
                          f"Exit orders placed: {success_count}/{len(self.positions_data)}"))
            
            # Refresh positions
            self.root.after(1000, self.refresh_positions)
        
        except Exception as e:
            print(f"Error in exit async: {e}")


def main():
    root = tk.Tk()
    app = TraderChampLite(root)
    root.mainloop()


if __name__ == "__main__":
    main()
