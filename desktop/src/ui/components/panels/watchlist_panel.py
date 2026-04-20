"""Watchlist Panel UI Component - Displays and manages watchlists."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Callable

from src.watchlists import WatchlistManager, Watchlist, WatchlistType


class WatchlistPanel(ttk.Frame):
    """Panel displaying watchlists and their symbols."""
    
    def __init__(self, parent, watchlist_manager: WatchlistManager, **kwargs):
        super().__init__(parent, **kwargs)
        self.watchlist_manager = watchlist_manager
        self.current_watchlist_id: Optional[str] = None
        self.callbacks: Dict[str, List[Callable]] = {
            'symbol_selected': [],
            'symbol_removed': [],
            'add_symbol': []
        }
        
        # Subscribe to watchlist changes
        self.watchlist_manager.subscribe(self._on_watchlist_changed)
        
        self._create_ui()
        self._refresh_watchlists()
    
    def _create_ui(self):
        """Create UI elements."""
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="New Watchlist", command=self._on_new_watchlist).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Add Symbol", command=self._on_add_symbol).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_watchlists).pack(side=tk.LEFT, padx=2)
        
        # Main content
        content = ttk.Frame(self)
        content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left side - Watchlist list
        left_frame = ttk.Frame(content)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5)
        
        ttk.Label(left_frame, text="Watchlists", font=('Arial', 10, 'bold')).pack(anchor=tk.W)
        
        self.watchlist_tree = ttk.Treeview(left_frame, height=15, width=25)
        self.watchlist_tree.column('#0', width=200)
        self.watchlist_tree.heading('#0', text='Watchlist', anchor=tk.W)
        
        scrollbar = ttk.Scrollbar(left_frame, orient=tk.VERTICAL, command=self.watchlist_tree.yview)
        self.watchlist_tree.configure(yscroll=scrollbar.set)
        
        self.watchlist_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.watchlist_tree.bind('<<TreeviewSelect>>', self._on_watchlist_selected)
        self.watchlist_tree.bind('<Button-3>', self._on_watchlist_right_click)
        
        # Right side - Symbol list
        right_frame = ttk.Frame(content)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        
        self.symbol_label = ttk.Label(right_frame, text="Symbols", font=('Arial', 10, 'bold'))
        self.symbol_label.pack(anchor=tk.W)
        
        columns = ('Symbol', 'Added', 'Target', 'Actions')
        self.symbol_tree = ttk.Treeview(right_frame, columns=columns, height=15)
        self.symbol_tree.column('#0', width=0, stretch=tk.NO)
        self.symbol_tree.column('Symbol', anchor=tk.W, width=80)
        self.symbol_tree.column('Added', anchor=tk.CENTER, width=100)
        self.symbol_tree.column('Target', anchor=tk.CENTER, width=80)
        self.symbol_tree.column('Actions', anchor=tk.CENTER, width=60)
        
        self.symbol_tree.heading('#0', text='', anchor=tk.W)
        self.symbol_tree.heading('Symbol', text='Symbol', anchor=tk.W)
        self.symbol_tree.heading('Added', text='Added Date', anchor=tk.CENTER)
        self.symbol_tree.heading('Target', text='Target Price', anchor=tk.CENTER)
        self.symbol_tree.heading('Actions', text='Actions', anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.symbol_tree.yview)
        self.symbol_tree.configure(yscroll=scrollbar.set)
        
        self.symbol_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.symbol_tree.bind('<Button-3>', self._on_symbol_right_click)
        self.symbol_tree.bind('<Double-1>', self._on_symbol_double_click)
    
    def _refresh_watchlists(self):
        """Refresh watchlist display."""
        # Clear existing
        for item in self.watchlist_tree.get_children():
            self.watchlist_tree.delete(item)
        
        # Add watchlists
        for watchlist in self.watchlist_manager.get_all_watchlists():
            count = len(watchlist.symbols)
            display_text = f"{watchlist.name} ({count})"
            self.watchlist_tree.insert('', tk.END, iid=watchlist.id, text=display_text)
    
    def _on_watchlist_selected(self, event):
        """Handle watchlist selection."""
        selection = self.watchlist_tree.selection()
        if selection:
            self.current_watchlist_id = selection[0]
            self._refresh_symbols()
    
    def _refresh_symbols(self):
        """Refresh symbols for current watchlist."""
        # Clear existing
        for item in self.symbol_tree.get_children():
            self.symbol_tree.delete(item)
        
        if not self.current_watchlist_id:
            return
        
        watchlist = self.watchlist_manager.get_watchlist(self.current_watchlist_id)
        if not watchlist:
            return
        
        self.symbol_label.config(text=f"Symbols - {watchlist.name}")
        
        # Add symbols
        for symbol, ws in watchlist.symbols.items():
            added_date = ws.added_at.strftime('%Y-%m-%d')
            target_str = f"${ws.target_price:.2f}" if ws.target_price else "-"
            
            self.symbol_tree.insert('', tk.END, iid=f"{self.current_watchlist_id}:{symbol}", values=(
                symbol,
                added_date,
                target_str,
                'Remove'
            ))
    
    def _on_new_watchlist(self):
        """Create new watchlist."""
        dialog = CreateWatchlistDialog(self)
        self.wait_window(dialog)
        
        if hasattr(dialog, 'result') and dialog.result:
            name, wl_type, description = dialog.result
            watchlist_id = f"wl_{len(self.watchlist_manager.get_all_watchlists())}"
            self.watchlist_manager.create_watchlist(
                watchlist_id, name, WatchlistType(wl_type), description
            )
            self._refresh_watchlists()
    
    def _on_add_symbol(self):
        """Add symbol to current watchlist."""
        if not self.current_watchlist_id:
            messagebox.showwarning("Error", "Please select a watchlist first")
            return
        
        dialog = AddSymbolDialog(self)
        self.wait_window(dialog)
        
        if hasattr(dialog, 'result') and dialog.result:
            symbol, notes, target = dialog.result
            self.watchlist_manager.add_symbol(
                self.current_watchlist_id, symbol, notes, target
            )
            self._refresh_symbols()
            
            for callback in self.callbacks.get('add_symbol', []):
                callback(symbol)
    
    def _on_watchlist_right_click(self, event):
        """Handle right-click on watchlist."""
        item = self.watchlist_tree.identify('item', event.x, event.y)
        if not item:
            return
        
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Rename", command=lambda: self._rename_watchlist(item))
        menu.add_command(label="Delete", command=lambda: self._delete_watchlist(item))
        menu.post(event.x_root, event.y_root)
    
    def _on_symbol_right_click(self, event):
        """Handle right-click on symbol."""
        item = self.symbol_tree.identify('item', event.x, event.y)
        if not item:
            return
        
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Edit Notes", command=lambda: self._edit_symbol_notes(item))
        menu.add_command(label="Remove", command=lambda: self._remove_symbol(item))
        menu.post(event.x_root, event.y_root)
    
    def _on_symbol_double_click(self, event):
        """Handle double-click on symbol."""
        item = self.symbol_tree.identify('item', event.x, event.y)
        if item:
            # Extract symbol from item ID
            parts = item.split(':')
            if len(parts) == 2:
                symbol = parts[1]
                for callback in self.callbacks.get('symbol_selected', []):
                    callback(symbol)
    
    def _rename_watchlist(self, watchlist_id: str):
        """Rename watchlist."""
        watchlist = self.watchlist_manager.get_watchlist(watchlist_id)
        if not watchlist:
            return
        
        dialog = RenameDialog(self, watchlist.name)
        self.wait_window(dialog)
        
        if hasattr(dialog, 'result') and dialog.result:
            self.watchlist_manager.rename_watchlist(watchlist_id, dialog.result)
            self._refresh_watchlists()
    
    def _delete_watchlist(self, watchlist_id: str):
        """Delete watchlist."""
        if messagebox.askyesno("Confirm", "Delete this watchlist?"):
            self.watchlist_manager.delete_watchlist(watchlist_id)
            self._refresh_watchlists()
            self.current_watchlist_id = None
            self._refresh_symbols()
    
    def _remove_symbol(self, symbol_id: str):
        """Remove symbol from watchlist."""
        if not self.current_watchlist_id:
            return
        
        parts = symbol_id.split(':')
        if len(parts) != 2:
            return
        
        symbol = parts[1]
        if messagebox.askyesno("Confirm", f"Remove {symbol} from watchlist?"):
            self.watchlist_manager.remove_symbol(self.current_watchlist_id, symbol)
            self._refresh_symbols()
    
    def _edit_symbol_notes(self, symbol_id: str):
        """Edit symbol notes."""
        if not self.current_watchlist_id:
            return
        
        parts = symbol_id.split(':')
        if len(parts) != 2:
            return
        
        symbol = parts[1]
        watchlist = self.watchlist_manager.get_watchlist(self.current_watchlist_id)
        if not watchlist:
            return
        
        ws = watchlist.get_symbol(symbol)
        if not ws:
            return
        
        dialog = EditSymbolDialog(self, symbol, ws.notes or "", ws.target_price)
        self.wait_window(dialog)
        
        if hasattr(dialog, 'result') and dialog.result:
            notes, target = dialog.result
            watchlist.update_symbol_notes(symbol, notes)
            if target is not None:
                watchlist.update_symbol_target(symbol, target)
            self._refresh_symbols()
    
    def _on_watchlist_changed(self, event: str, data):
        """Handle watchlist changes."""
        self._refresh_watchlists()


class CreateWatchlistDialog(tk.Toplevel):
    """Dialog to create new watchlist."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Create Watchlist")
        self.geometry("400x200")
        self.result = None
        
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=30).grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(main_frame, text="Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar(value="custom")
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, state='readonly', width=27)
        type_combo['values'] = [wt.value for wt in WatchlistType]
        type_combo.grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(main_frame, text="Description:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.desc_text = tk.Text(main_frame, height=4, width=30)
        self.desc_text.grid(row=2, column=1, sticky=tk.EW, pady=5)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        ttk.Button(button_frame, text="Create", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
    
    def _on_ok(self):
        """OK button clicked."""
        name = self.name_var.get()
        if not name:
            messagebox.showwarning("Error", "Please enter a name")
            return
        
        description = self.desc_text.get("1.0", tk.END).strip()
        self.result = (name, self.type_var.get(), description)
        self.destroy()


class AddSymbolDialog(tk.Toplevel):
    """Dialog to add symbol to watchlist."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add Symbol")
        self.geometry("400x200")
        self.result = None
        
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Symbol:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.symbol_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.symbol_var, width=30).grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(main_frame, text="Target Price:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.target_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.target_var, width=30).grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(main_frame, text="Notes:").grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.notes_text = tk.Text(main_frame, height=3, width=30)
        self.notes_text.grid(row=2, column=1, sticky=tk.EW, pady=5)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        ttk.Button(button_frame, text="Add", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
    
    def _on_ok(self):
        """OK button clicked."""
        symbol = self.symbol_var.get().upper()
        if not symbol:
            messagebox.showwarning("Error", "Please enter a symbol")
            return
        
        try:
            target = float(self.target_var.get()) if self.target_var.get() else None
        except ValueError:
            messagebox.showwarning("Error", "Invalid target price")
            return
        
        notes = self.notes_text.get("1.0", tk.END).strip()
        self.result = (symbol, notes, target)
        self.destroy()


class RenameDialog(tk.Toplevel):
    """Dialog to rename watchlist."""
    
    def __init__(self, parent, current_name: str):
        super().__init__(parent)
        self.title("Rename Watchlist")
        self.geometry("300x100")
        self.result = None
        
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="New Name:").pack(anchor=tk.W)
        self.name_var = tk.StringVar(value=current_name)
        ttk.Entry(main_frame, textvariable=self.name_var, width=30).pack(anchor=tk.W, pady=5)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(anchor=tk.E, pady=10)
        
        ttk.Button(button_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
    
    def _on_ok(self):
        """OK button clicked."""
        name = self.name_var.get()
        if name:
            self.result = name
            self.destroy()


class EditSymbolDialog(tk.Toplevel):
    """Dialog to edit symbol in watchlist."""
    
    def __init__(self, parent, symbol: str, notes: str = "", target_price: Optional[float] = None):
        super().__init__(parent)
        self.title(f"Edit {symbol}")
        self.geometry("400x200")
        self.result = None
        
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Target Price:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.target_var = tk.StringVar(value=str(target_price) if target_price else "")
        ttk.Entry(main_frame, textvariable=self.target_var, width=30).grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        ttk.Label(main_frame, text="Notes:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.notes_text = tk.Text(main_frame, height=4, width=30)
        self.notes_text.insert('1.0', notes)
        self.notes_text.grid(row=1, column=1, sticky=tk.EW, pady=5)
        
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        ttk.Button(button_frame, text="Save", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
    
    def _on_ok(self):
        """OK button clicked."""
        try:
            target = float(self.target_var.get()) if self.target_var.get() else None
        except ValueError:
            messagebox.showwarning("Error", "Invalid target price")
            return
        
        notes = self.notes_text.get("1.0", tk.END).strip()
        self.result = (notes, target)
        self.destroy()
