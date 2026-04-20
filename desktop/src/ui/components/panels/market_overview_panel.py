"""Market Overview Panel - Displays market summary and key metrics."""

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class MarketMetrics:
    """Market metrics and summary data."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_volume: float = 0.0
    market_breadth_advance: int = 0  # Advancing issues
    market_breadth_decline: int = 0  # Declining issues
    market_breadth_unchanged: int = 0  # Unchanged issues
    sector_data: Dict[str, Dict[str, float]] = field(default_factory=dict)  # Sector -> {change%, volume}
    top_gainers: List[Dict] = field(default_factory=list)  # [{symbol, price, change%, volume}, ...]
    top_losers: List[Dict] = field(default_factory=list)
    top_volume: List[Dict] = field(default_factory=list)
    market_index: Optional[float] = None  # e.g., SPX, Crypto Index
    market_index_change: Optional[float] = None


class MarketOverviewPanel(ttk.Frame):
    """Panel displaying market overview with key metrics."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.callbacks: Dict[str, List[Callable]] = {
            'symbol_selected': [],
            'symbol_chart': []
        }
        self.market_data = MarketMetrics()
        
        self._create_ui()
    
    def _create_ui(self):
        """Create UI elements."""
        # Main layout with tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: Market Summary
        self._create_summary_tab()
        
        # Tab 2: Sector Performance
        self._create_sector_tab()
        
        # Tab 3: Top Performers
        self._create_performers_tab()
        
        # Tab 4: Heatmap
        self._create_heatmap_tab()
    
    def _create_summary_tab(self):
        """Create market summary tab."""
        summary_frame = ttk.Frame(self.notebook)
        self.notebook.add(summary_frame, text="Summary")
        
        # Market Index Card
        index_frame = ttk.LabelFrame(summary_frame, text="Market Index", padding=10)
        index_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.index_label = ttk.Label(index_frame, text="SPX: 4,850.00", font=('Arial', 14, 'bold'))
        self.index_label.pack(anchor=tk.W)
        
        self.index_change_label = ttk.Label(index_frame, text="+1.25% (+50.00)", foreground='green')
        self.index_change_label.pack(anchor=tk.W)
        
        # Breadth Card
        breadth_frame = ttk.LabelFrame(summary_frame, text="Market Breadth", padding=10)
        breadth_frame.pack(fill=tk.X, padx=10, pady=10)
        
        breadth_content = ttk.Frame(breadth_frame)
        breadth_content.pack(fill=tk.X)
        
        ttk.Label(breadth_content, text="Advancing:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.advance_label = ttk.Label(breadth_content, text="2,850", foreground='green', font=('Arial', 10, 'bold'))
        self.advance_label.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(breadth_content, text="Declining:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.decline_label = ttk.Label(breadth_content, text="1,240", foreground='red', font=('Arial', 10, 'bold'))
        self.decline_label.grid(row=0, column=3, sticky=tk.W, padx=5)
        
        ttk.Label(breadth_content, text="Unchanged:").grid(row=0, column=4, sticky=tk.W, padx=5)
        self.unchanged_label = ttk.Label(breadth_content, text="310", font=('Arial', 10, 'bold'))
        self.unchanged_label.grid(row=0, column=5, sticky=tk.W, padx=5)
        
        # Volume Card
        volume_frame = ttk.LabelFrame(summary_frame, text="Volume", padding=10)
        volume_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.volume_label = ttk.Label(volume_frame, text="Total Volume: 2.1B", font=('Arial', 10))
        self.volume_label.pack(anchor=tk.W)
    
    def _create_sector_tab(self):
        """Create sector performance tab."""
        sector_frame = ttk.Frame(self.notebook)
        self.notebook.add(sector_frame, text="Sectors")
        
        columns = ('Sector', 'Change %', 'Volume', 'Status')
        self.sector_tree = ttk.Treeview(sector_frame, columns=columns, height=12)
        self.sector_tree.column('#0', width=0, stretch=tk.NO)
        self.sector_tree.column('Sector', anchor=tk.W, width=120)
        self.sector_tree.column('Change %', anchor=tk.CENTER, width=100)
        self.sector_tree.column('Volume', anchor=tk.CENTER, width=100)
        self.sector_tree.column('Status', anchor=tk.CENTER, width=80)
        
        self.sector_tree.heading('#0', text='', anchor=tk.W)
        self.sector_tree.heading('Sector', text='Sector', anchor=tk.W)
        self.sector_tree.heading('Change %', text='Change %', anchor=tk.CENTER)
        self.sector_tree.heading('Volume', text='Volume', anchor=tk.CENTER)
        self.sector_tree.heading('Status', text='Status', anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(sector_frame, orient=tk.VERTICAL, command=self.sector_tree.yview)
        self.sector_tree.configure(yscroll=scrollbar.set)
        
        self.sector_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Sample data
        self._populate_sectors()
    
    def _create_performers_tab(self):
        """Create top performers tab."""
        performers_frame = ttk.Frame(self.notebook)
        self.notebook.add(performers_frame, text="Top Performers")
        
        # Gainers
        gainers_frame = ttk.LabelFrame(performers_frame, text="Top Gainers", padding=5)
        gainers_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        columns = ('Symbol', 'Price', 'Change %', 'Volume')
        self.gainers_tree = ttk.Treeview(gainers_frame, columns=columns, height=8)
        self.gainers_tree.column('#0', width=0)
        self.gainers_tree.column('Symbol', anchor=tk.W, width=80)
        self.gainers_tree.column('Price', anchor=tk.CENTER, width=100)
        self.gainers_tree.column('Change %', anchor=tk.CENTER, width=100)
        self.gainers_tree.column('Volume', anchor=tk.CENTER, width=120)
        
        self.gainers_tree.heading('Symbol', text='Symbol', anchor=tk.W)
        self.gainers_tree.heading('Price', text='Price', anchor=tk.CENTER)
        self.gainers_tree.heading('Change %', text='Change %', anchor=tk.CENTER)
        self.gainers_tree.heading('Volume', text='Volume', anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(gainers_frame, orient=tk.VERTICAL, command=self.gainers_tree.yview)
        self.gainers_tree.configure(yscroll=scrollbar.set)
        
        self.gainers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.gainers_tree.bind('<Button-3>', lambda e: self._show_symbol_menu(e, 'gainers'))
        
        # Losers
        losers_frame = ttk.LabelFrame(performers_frame, text="Top Losers", padding=5)
        losers_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.losers_tree = ttk.Treeview(losers_frame, columns=columns, height=8)
        self.losers_tree.column('#0', width=0)
        self.losers_tree.column('Symbol', anchor=tk.W, width=80)
        self.losers_tree.column('Price', anchor=tk.CENTER, width=100)
        self.losers_tree.column('Change %', anchor=tk.CENTER, width=100)
        self.losers_tree.column('Volume', anchor=tk.CENTER, width=120)
        
        self.losers_tree.heading('Symbol', text='Symbol', anchor=tk.W)
        self.losers_tree.heading('Price', text='Price', anchor=tk.CENTER)
        self.losers_tree.heading('Change %', text='Change %', anchor=tk.CENTER)
        self.losers_tree.heading('Volume', text='Volume', anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(losers_frame, orient=tk.VERTICAL, command=self.losers_tree.yview)
        self.losers_tree.configure(yscroll=scrollbar.set)
        
        self.losers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.losers_tree.bind('<Button-3>', lambda e: self._show_symbol_menu(e, 'losers'))
        
        self._populate_performers()
    
    def _create_heatmap_tab(self):
        """Create market heatmap tab."""
        heatmap_frame = ttk.Frame(self.notebook)
        self.notebook.add(heatmap_frame, text="Heatmap")
        
        # Note: This would typically be implemented with canvas drawing or an image
        info_label = ttk.Label(
            heatmap_frame,
            text="Market Heatmap\n\nShowing performance across sectors and asset classes",
            font=('Arial', 10)
        )
        info_label.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Placeholder for actual heatmap visualization
        self.heatmap_canvas = tk.Canvas(heatmap_frame, bg='white', height=400)
        self.heatmap_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def _populate_sectors(self):
        """Populate sector data."""
        sectors = [
            ("Technology", "+2.15", "1.2B", "↑"),
            ("Healthcare", "+1.50", "856M", "↑"),
            ("Financials", "+1.25", "945M", "↑"),
            ("Consumer", "-0.50", "723M", "↓"),
            ("Industrials", "+0.85", "512M", "↑"),
            ("Energy", "-1.25", "634M", "↓"),
            ("Utilities", "+0.15", "398M", "→"),
            ("Real Estate", "-0.75", "287M", "↓"),
            ("Materials", "+1.05", "445M", "↑"),
            ("Communication", "+1.75", "567M", "↑"),
        ]
        
        for sector, change, volume, status in sectors:
            tag = 'gain' if change.startswith('+') else 'loss'
            self.sector_tree.insert('', tk.END, values=(sector, change, volume, status), tags=(tag,))
        
        self.sector_tree.tag_configure('gain', foreground='green')
        self.sector_tree.tag_configure('loss', foreground='red')
    
    def _populate_performers(self):
        """Populate top performers."""
        gainers = [
            ("NVDA", "$850.25", "+4.50%", "45.2M"),
            ("TSLA", "$245.80", "+3.75%", "52.1M"),
            ("MSFT", "$410.50", "+2.25%", "28.5M"),
            ("AMZN", "$195.30", "+1.85%", "31.2M"),
            ("META", "$520.15", "+3.10%", "19.8M"),
        ]
        
        losers = [
            ("GE", "$95.20", "-2.15%", "15.3M"),
            ("F", "$8.45", "-3.50%", "45.6M"),
            ("X", "$28.90", "-4.25%", "8.2M"),
            ("MMM", "$120.50", "-1.85%", "3.5M"),
            ("BA", "$178.25", "-2.45%", "9.8M"),
        ]
        
        for symbol, price, change, volume in gainers:
            self.gainers_tree.insert('', tk.END, values=(symbol, price, change, volume), tags=('gain',))
        
        for symbol, price, change, volume in losers:
            self.losers_tree.insert('', tk.END, values=(symbol, price, change, volume), tags=('loss',))
        
        self.gainers_tree.tag_configure('gain', foreground='green')
        self.losers_tree.tag_configure('loss', foreground='red')
    
    def _show_symbol_menu(self, event, tree_name: str):
        """Show context menu for symbol."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Add to Watchlist", command=lambda: self._add_to_watchlist(event, tree_name))
        menu.add_command(label="View Chart", command=lambda: self._view_chart(event, tree_name))
        menu.add_command(label="Create Alert", command=lambda: self._create_alert(event, tree_name))
        menu.post(event.x_root, event.y_root)
    
    def _add_to_watchlist(self, event, tree_name: str):
        """Add symbol to watchlist."""
        # TODO: Implement
        pass
    
    def _view_chart(self, event, tree_name: str):
        """View chart for symbol."""
        # TODO: Implement
        pass
    
    def _create_alert(self, event, tree_name: str):
        """Create alert for symbol."""
        # TODO: Implement
        pass
    
    def update_market_metrics(self, metrics: MarketMetrics):
        """Update market metrics display."""
        self.market_data = metrics
        
        # Update summary
        if metrics.market_index:
            self.index_label.config(text=f"SPX: {metrics.market_index:,.2f}")
        
        if metrics.market_index_change is not None:
            color = 'green' if metrics.market_index_change >= 0 else 'red'
            change_text = f"{metrics.market_index_change:+.2f}%"
            self.index_change_label.config(text=change_text, foreground=color)
        
        self.advance_label.config(text=str(metrics.market_breadth_advance))
        self.decline_label.config(text=str(metrics.market_breadth_decline))
        self.unchanged_label.config(text=str(metrics.market_breadth_unchanged))
        
        self.volume_label.config(text=f"Total Volume: {metrics.total_volume / 1e9:.1f}B")
    
    def register_callback(self, event: str, callback: Callable):
        """Register a callback."""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)
