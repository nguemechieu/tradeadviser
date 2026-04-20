"""Alerts Panel UI Component - Displays and manages alerts."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Dict, List, Optional, Callable

from src.alerts import AlertRule, AlertEvent, AlertType


class AlertsPanel(ttk.Frame):
    """Panel displaying active alerts and triggered alerts."""
    
    def __init__(self, parent, alert_engine, **kwargs):
        super().__init__(parent, **kwargs)
        self.alert_engine = alert_engine
        self.callbacks: Dict[str, List[Callable]] = {
            'create_alert': [],
            'delete_alert': [],
            'toggle_alert': []
        }
        
        # Subscribe to alert events
        self.alert_engine.subscribe(self._on_alert_triggered)
        
        self._create_ui()
        self._populate_alerts()
    
    def _create_ui(self):
        """Create UI elements."""
        # Top toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="New Alert", command=self._on_new_alert).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Refresh", command=self._populate_alerts).pack(side=tk.LEFT, padx=2)
        
        # Tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Active Alerts Tab
        self.active_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.active_frame, text="Active Alerts")
        self._create_active_alerts_tab()
        
        # Triggered Alerts Tab
        self.triggered_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.triggered_frame, text="Triggered Alerts")
        self._create_triggered_alerts_tab()
    
    def _create_active_alerts_tab(self):
        """Create active alerts list view."""
        # Treeview for alerts
        columns = ('Name', 'Type', 'Symbol', 'Condition', 'Status', 'Actions')
        self.active_tree = ttk.Treeview(self.active_frame, columns=columns, height=10)
        self.active_tree.column('#0', width=0, stretch=tk.NO)
        self.active_tree.column('Name', anchor=tk.W, width=120)
        self.active_tree.column('Type', anchor=tk.W, width=100)
        self.active_tree.column('Symbol', anchor=tk.W, width=80)
        self.active_tree.column('Condition', anchor=tk.W, width=120)
        self.active_tree.column('Status', anchor=tk.CENTER, width=70)
        self.active_tree.column('Actions', anchor=tk.CENTER, width=80)
        
        self.active_tree.heading('#0', text='', anchor=tk.W)
        self.active_tree.heading('Name', text='Alert Name', anchor=tk.W)
        self.active_tree.heading('Type', text='Type', anchor=tk.W)
        self.active_tree.heading('Symbol', text='Symbol', anchor=tk.W)
        self.active_tree.heading('Condition', text='Condition', anchor=tk.W)
        self.active_tree.heading('Status', text='Status', anchor=tk.CENTER)
        self.active_tree.heading('Actions', text='Actions', anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(self.active_frame, orient=tk.VERTICAL, command=self.active_tree.yview)
        self.active_tree.configure(yscroll=scrollbar.set)
        
        self.active_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind double-click to edit
        self.active_tree.bind('<Double-1>', self._on_alert_double_click)
    
    def _create_triggered_alerts_tab(self):
        """Create triggered alerts history."""
        columns = ('Alert', 'Triggered', 'Message', 'Count')
        self.triggered_tree = ttk.Treeview(self.triggered_frame, columns=columns, height=10)
        self.triggered_tree.column('#0', width=0, stretch=tk.NO)
        self.triggered_tree.column('Alert', anchor=tk.W, width=150)
        self.triggered_tree.column('Triggered', anchor=tk.CENTER, width=150)
        self.triggered_tree.column('Message', anchor=tk.W, width=250)
        self.triggered_tree.column('Count', anchor=tk.CENTER, width=70)
        
        self.triggered_tree.heading('#0', text='', anchor=tk.W)
        self.triggered_tree.heading('Alert', text='Alert', anchor=tk.W)
        self.triggered_tree.heading('Triggered', text='Triggered At', anchor=tk.CENTER)
        self.triggered_tree.heading('Message', text='Message', anchor=tk.W)
        self.triggered_tree.heading('Count', text='Count', anchor=tk.CENTER)
        
        scrollbar = ttk.Scrollbar(self.triggered_frame, orient=tk.VERTICAL, command=self.triggered_tree.yview)
        self.triggered_tree.configure(yscroll=scrollbar.set)
        
        self.triggered_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _populate_alerts(self):
        """Populate alert list."""
        # Clear existing items
        for item in self.active_tree.get_children():
            self.active_tree.delete(item)
        
        # Add alerts
        for alert in self.alert_engine.get_all_alerts():
            status = "Enabled" if alert.enabled else "Disabled"
            condition = self._format_condition(alert)
            
            self.active_tree.insert('', tk.END, iid=alert.id, values=(
                alert.name,
                alert.alert_type.value.replace('_', ' ').title(),
                alert.symbol or 'N/A',
                condition,
                status,
                'Edit | Del'
            ))
    
    def _format_condition(self, alert: AlertRule) -> str:
        """Format alert condition for display."""
        if alert.price_level:
            return f"${alert.price_level:.2f}"
        if alert.percentage:
            return f"{alert.percentage:+.1f}%"
        if alert.volume_threshold:
            return f"Vol: {alert.volume_threshold:.0f}"
        return "Custom"
    
    def _on_new_alert(self):
        """Handle new alert creation."""
        for callback in self.callbacks.get('create_alert', []):
            callback()
    
    def _on_alert_double_click(self, event):
        """Handle double-click on alert."""
        item = self.active_tree.selection()
        if item:
            alert_id = item[0]
            self._on_edit_alert(alert_id)
    
    def _on_edit_alert(self, alert_id: str):
        """Edit an alert."""
        alert = self.alert_engine.get_alert(alert_id)
        if alert:
            # TODO: Open edit dialog
            pass
    
    def _on_alert_triggered(self, event: AlertEvent):
        """Handle alert trigger event."""
        # Add to triggered alerts tab
        timestamp = event.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        self.triggered_tree.insert('', 0, values=(
            event.alert_name,
            timestamp,
            event.message,
            str(self.alert_engine.get_alert(event.alert_id).triggered_count)
        ))
    
    def register_callback(self, event: str, callback: Callable):
        """Register a callback for events."""
        if event not in self.callbacks:
            self.callbacks[event] = []
        self.callbacks[event].append(callback)


class CreateAlertDialog(tk.Toplevel):
    """Dialog for creating a new alert."""
    
    def __init__(self, parent, alert_engine, on_create: Optional[Callable] = None):
        super().__init__(parent)
        self.title("Create Alert")
        self.geometry("500x600")
        self.alert_engine = alert_engine
        self.on_create = on_create
        
        self._create_ui()
    
    def _create_ui(self):
        """Create dialog UI."""
        # Main frame with padding
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Alert name
        ttk.Label(main_frame, text="Alert Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var, width=40).grid(row=0, column=1, sticky=tk.EW, pady=5)
        
        # Alert type
        ttk.Label(main_frame, text="Alert Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar()
        type_combo = ttk.Combobox(main_frame, textvariable=self.type_var, state='readonly', width=37)
        type_combo['values'] = [at.value for at in AlertType]
        type_combo.grid(row=1, column=1, sticky=tk.EW, pady=5)
        type_combo.bind('<<ComboboxSelected>>', self._on_type_changed)
        
        # Symbol
        ttk.Label(main_frame, text="Symbol:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.symbol_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.symbol_var, width=40).grid(row=2, column=1, sticky=tk.EW, pady=5)
        
        # Condition frame (will be populated based on alert type)
        ttk.Label(main_frame, text="Condition:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.condition_frame = ttk.Frame(main_frame)
        self.condition_frame.grid(row=3, column=1, sticky=tk.EW, pady=5)
        
        # Channels
        ttk.Label(main_frame, text="Notifications:").grid(row=4, column=0, sticky=tk.W, pady=5)
        channels_frame = ttk.Frame(main_frame)
        channels_frame.grid(row=4, column=1, sticky=tk.EW, pady=5)
        
        self.in_app_var = tk.BooleanVar(value=True)
        self.sound_var = tk.BooleanVar(value=True)
        self.email_var = tk.BooleanVar(value=False)
        
        ttk.Checkbutton(channels_frame, text="In-App", variable=self.in_app_var).pack(anchor=tk.W)
        ttk.Checkbutton(channels_frame, text="Sound", variable=self.sound_var).pack(anchor=tk.W)
        ttk.Checkbutton(channels_frame, text="Email", variable=self.email_var).pack(anchor=tk.W)
        
        # Email address (if email enabled)
        ttk.Label(main_frame, text="Email:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.email_var_input = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.email_var_input, width=40).grid(row=5, column=1, sticky=tk.EW, pady=5)
        
        # One-time alert
        self.one_time_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="One-time alert (disable after trigger)", 
                       variable=self.one_time_var).grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=10)
        
        ttk.Button(button_frame, text="Create", command=self._on_create).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        main_frame.columnconfigure(1, weight=1)
    
    def _on_type_changed(self, event=None):
        """Handle alert type change."""
        # Clear condition frame
        for widget in self.condition_frame.winfo_children():
            widget.destroy()
        
        alert_type = self.type_var.get()
        
        if alert_type in ['price_above', 'price_below']:
            ttk.Label(self.condition_frame, text="Price Level:").pack(anchor=tk.W)
            self.price_var = tk.StringVar()
            ttk.Entry(self.condition_frame, textvariable=self.price_var, width=20).pack(anchor=tk.W)
        
        elif alert_type in ['percentage_up', 'percentage_down']:
            ttk.Label(self.condition_frame, text="Percentage (%):").pack(anchor=tk.W)
            self.percentage_var = tk.StringVar()
            ttk.Entry(self.condition_frame, textvariable=self.percentage_var, width=20).pack(anchor=tk.W)
        
        elif alert_type == 'volume_spike':
            ttk.Label(self.condition_frame, text="Volume Threshold:").pack(anchor=tk.W)
            self.volume_var = tk.StringVar()
            ttk.Entry(self.condition_frame, textvariable=self.volume_var, width=20).pack(anchor=tk.W)
    
    def _on_create(self):
        """Create the alert."""
        if not self.name_var.get():
            messagebox.showwarning("Error", "Please enter an alert name")
            return
        
        if not self.type_var.get():
            messagebox.showwarning("Error", "Please select an alert type")
            return
        
        # TODO: Validate and create alert
        if self.on_create:
            self.on_create()
        
        self.destroy()
