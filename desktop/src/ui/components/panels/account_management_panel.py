"""Account Management Panel - Displays account info, balance, and positions."""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AccountInfo:
    """Account information."""
    account_id: str
    account_name: str
    balance: float = 0.0
    buying_power: float = 0.0
    margin_level: float = 0.0  # 0-100%
    cash: float = 0.0
    positions_value: float = 0.0
    day_trading_buying_power: float = 0.0
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Position:
    """Trading position."""
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    side: str  # 'long' or 'short'
    account: str  # account_id
    opened_at: datetime = field(default_factory=datetime.utcnow)


class AccountManagementPanel(ttk.Frame):
    """Panel for account management and monitoring."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.callbacks: Dict[str, List[Callable]] = {
            'close_position': [],
            'adjust_position': []
        }
        self.accounts: Dict[str, AccountInfo] = {}
        self.positions: Dict[str, List[Position]] = {}
        self.current_account: Optional[str] = None
        
        self._create_ui()
    
    def _create_ui(self):
        """Create UI elements."""
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Label(toolbar, text="Account:").pack(side=tk.LEFT, padx=5)
        self.account_combo = ttk.Combobox(toolbar, state='readonly', width=30)
        self.account_combo.pack(side=tk.LEFT, padx=5)
        self.account_combo.bind('<<ComboboxSelected>>', self._on_account_selected)
        
        ttk.Button(toolbar, text="Refresh", command=self._refresh_display).pack(side=tk.LEFT, padx=5)
        
        # Main content
        content = ttk.Frame(self)
        content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Account info
        left_frame = ttk.LabelFrame(content, text="Account Information", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)
        
        self._create_account_info_panel(left_frame)
        
        # Right panel - Positions
        right_frame = ttk.LabelFrame(content, text="Open Positions", padding=5)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self._create_positions_panel(right_frame)
    
    def _create_account_info_panel(self, parent):
        """Create account info display."""
        # Account name
        self.account_name_label = ttk.Label(parent, text="", font=('Arial', 11, 'bold'))
        self.account_name_label.pack(anchor=tk.W, pady=5)
        
        # Separator
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # Account stats
        stats = [
            ('Balance', 'balance_label'),
            ('Cash', 'cash_label'),
            ('Positions Value', 'positions_label'),
            ('Buying Power', 'buying_power_label'),
            ('Day Trading BP', 'day_trading_bp_label'),
            ('Margin Level', 'margin_label'),
        ]
        
        for label_text, attr_name in stats:
            frame = ttk.Frame(parent)
            frame.pack(fill=tk.X, pady=3)
            
            ttk.Label(frame, text=label_text + ":", width=18).pack(side=tk.LEFT)
            label = ttk.Label(frame, text="$0.00", font=('Arial', 10, 'bold'))
            label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            setattr(self, attr_name, label)
        
        # Separator
        ttk.Separator(parent, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # Account P/L
        pl_frame = ttk.LabelFrame(parent, text="Performance", padding=5)
        pl_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(pl_frame, text="Realized P/L:", width=15).pack(side=tk.LEFT)
        self.realized_pl_label = ttk.Label(pl_frame, text="$0.00", font=('Arial', 10, 'bold'))
        self.realized_pl_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(pl_frame, text="Unrealized P/L:", width=15).pack(side=tk.LEFT)
        self.unrealized_pl_label = ttk.Label(pl_frame, text="$0.00", font=('Arial', 10, 'bold'))
        self.unrealized_pl_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
    def _create_positions_panel(self, parent):
        """Create positions list."""
        columns = ('Symbol', 'Qty', 'Entry', 'Current', 'P/L', 'P/L %', 'Side', 'Actions')
        self.positions_tree = ttk.Treeview(parent, columns=columns, height=10)
        self.positions_tree.column('#0', width=0, stretch=tk.NO)
        self.positions_tree.column('Symbol', anchor=tk.W, width=70)
        self.positions_tree.column('Qty', anchor=tk.CENTER, width=60)
        self.positions_tree.column('Entry', anchor=tk.CENTER, width=70)
        self.positions_tree.column('Current', anchor=tk.CENTER, width=70)
        self.positions_tree.column('P/L', anchor=tk.CENTER, width=80)
        self.positions_tree.column('P/L %', anchor=tk.CENTER, width=70)
        self.positions_tree.column('Side', anchor=tk.CENTER, width=50)
        self.positions_tree.column('Actions', anchor=tk.CENTER, width=60)
        
        self.positions_tree.heading('#0', text='', anchor=tk.W)
        self.positions_tree.heading('Symbol', text='Symbol', anchor=tk.W)
        self.positions_tree.heading('Qty', text='Qty', anchor=tk.CENTER)
        self.positions_tree.heading('Entry', text='Entry', anchor=tk.CENTER)
        self.positions_tree.heading('Current', text='Current', anchor=tk.CENTER)
        self.positions_tree.heading('P/L', text='P/L', anchor=tk.CENTER)
        self.positions_tree.heading('P/L %', text='P/L %', anchor=tk.CENTER)
        self.positions_tree.heading('Side', text='Side', anchor=tk.CENTER)
        self.positions_tree.heading('Actions', text='Actions', anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.positions_tree.yview)
        self.positions_tree.configure(yscroll=scrollbar.set)
        
        self.positions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.positions_tree.bind('<Button-3>', self._on_position_right_click)
        self.positions_tree.bind('<Double-1>', self._on_position_double_click)
    
    def _on_account_selected(self, event=None):
        """Handle account selection."""
        selected = self.account_combo.get()
        if selected:
            # Extract account ID from display name
            self.current_account = selected.split(' - ')[0] if ' - ' in selected else selected
            self._refresh_display()
    
    def _refresh_display(self):
        """Refresh account display."""
        if not self.current_account or self.current_account not in self.accounts:
            return
        
        account = self.accounts[self.current_account]
        
        # Update account info
        self.account_name_label.config(text=f"{account.account_name} ({account.account_id})")
        self.balance_label.config(text=f"${account.balance:,.2f}")
        self.cash_label.config(text=f"${account.cash:,.2f}")
        self.positions_label.config(text=f"${account.positions_value:,.2f}")
        self.buying_power_label.config(text=f"${account.buying_power:,.2f}")
        self.day_trading_bp_label.config(text=f"${account.day_trading_buying_power:,.2f}")
        
        # Update margin level with color
        margin_color = 'green' if account.margin_level < 30 else 'orange' if account.margin_level < 60 else 'red'
        self.margin_label.config(
            text=f"{account.margin_level:.1f}%",
            foreground=margin_color
        )
        
        # Update positions
        self._refresh_positions()
    
    def _refresh_positions(self):
        """Refresh positions list."""
        # Clear existing
        for item in self.positions_tree.get_children():
            self.positions_tree.delete(item)
        
        if not self.current_account:
            return
        
        positions = self.positions.get(self.current_account, [])
        
        for position in positions:
            pl_color = 'green' if position.unrealized_pnl >= 0 else 'red'
            side_abbr = 'L' if position.side == 'long' else 'S'
            
            self.positions_tree.insert('', tk.END, iid=position.symbol, values=(
                position.symbol,
                f"{position.quantity:.0f}",
                f"${position.entry_price:.2f}",
                f"${position.current_price:.2f}",
                f"${position.unrealized_pnl:,.2f}",
                f"{position.unrealized_pnl_pct:+.2f}%",
                side_abbr,
                'Close'
            ), tags=(pl_color,))
        
        self.positions_tree.tag_configure('green', foreground='green')
        self.positions_tree.tag_configure('red', foreground='red')
    
    def _on_position_right_click(self, event):
        """Handle right-click on position."""
        item = self.positions_tree.identify('item', event.x, event.y)
        if not item:
            return
        
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Close Position", command=lambda: self._close_position(item))
        menu.add_command(label="Adjust Size", command=lambda: self._adjust_position(item))
        menu.post(event.x_root, event.y_root)
    
    def _on_position_double_click(self, event):
        """Handle double-click on position."""
        item = self.positions_tree.identify('item', event.x, event.y)
        if item:
            # TODO: Open position details dialog
            pass
    
    def _close_position(self, symbol: str):
        """Close a position."""
        for callback in self.callbacks.get('close_position', []):
            callback(symbol)
    
    def _adjust_position(self, symbol: str):
        """Adjust position size."""
        for callback in self.callbacks.get('adjust_position', []):
            callback(symbol)
    
    def add_account(self, account: AccountInfo):
        """Add account to the list."""
        self.accounts[account.account_id] = account
        
        # Update combo box
        account_displays = [
            f"{acc.account_id} - {acc.account_name}"
            for acc in self.accounts.values()
        ]
        self.account_combo['values'] = account_displays
        
        if self.current_account is None and account_displays:
            self.account_combo.current(0)
            self._on_account_selected()
    
    def update_account(self, account: AccountInfo):
        """Update account information."""
        self.accounts[account.account_id] = account
        if self.current_account == account.account_id:
            self._refresh_display()
    
    def set_positions(self, account_id: str, positions: List[Position]):
        """Set positions for account."""
        self.positions[account_id] = positions
        if self.current_account == account_id:
            self._refresh_positions()
    
    def register_callback(self, event: str, callback: Callable):
        """Register a callback."""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)
