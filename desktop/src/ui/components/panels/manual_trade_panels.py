from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def ensure_manual_trade_ticket_window(terminal, window):
    if getattr(window, "_manual_trade_container", None) is not None:
        return

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(10)

    hint = QLabel(
        "Set symbol, side, and size. Limit and stop-limit orders need prices. "
        "Stop loss and take profit are optional."
    )
    hint.setWordWrap(True)
    hint.setStyleSheet(
        "color: #d9e6f7; background-color: #101a2d; border: 1px solid #20324d; "
        "border-radius: 12px; padding: 12px; font-size: 13px; font-weight: 600;"
    )
    layout.addWidget(hint)

    form = QFormLayout()
    form.setSpacing(10)

    symbol_picker = QComboBox()
    symbol_picker.setEditable(True)
    side_picker = QComboBox()
    side_picker.addItems(["buy", "sell"])
    type_picker = QComboBox()
    type_picker.addItems(["market", "limit", "stop_limit"])
    quantity_picker = QComboBox()
    quantity_picker.addItems(["Units", "Lots"])
    amount_input = QDoubleSpinBox()
    amount_input.setRange(0.0, 1_000_000_000.0)
    amount_input.setDecimals(8)
    amount_input.setValue(1.0)
    price_input = QLineEdit()
    stop_price_input = QLineEdit()
    stop_loss_input = QLineEdit()
    take_profit_input = QLineEdit()

    form.addRow("Symbol", symbol_picker)
    form.addRow("Side", side_picker)
    form.addRow("Order Type", type_picker)
    form.addRow("Size In", quantity_picker)
    form.addRow("Amount", amount_input)
    price_label = QLabel("Entry Price")
    form.addRow(price_label, price_input)
    stop_price_label = QLabel("Stop Trigger")
    form.addRow(stop_price_label, stop_price_input)
    form.addRow("Stop Loss", stop_loss_input)
    form.addRow("Take Profit", take_profit_input)
    layout.addLayout(form)

    status = QLabel("")
    status.setWordWrap(True)
    status.setStyleSheet("color: #9fb0c7; padding: 4px 0;")
    layout.addWidget(status)

    controls = QHBoxLayout()
    buy_limit_btn = QPushButton("Buy Market")
    sell_limit_btn = QPushButton("Sell Market")
    submit_btn = QPushButton("Submit Order")
    reset_btn = QPushButton("Reset Ticket")
    buy_limit_btn.setStyleSheet(
        "QPushButton { background-color:#163726; color:#dcfff0; border:1px solid #2e8a5b; border-radius:10px; padding:8px 12px; font-weight:700; }"
        "QPushButton:hover { background-color:#1c4a32; }"
    )
    sell_limit_btn.setStyleSheet(
        "QPushButton { background-color:#46181c; color:#ffe0e3; border:1px solid #b45b68; border-radius:10px; padding:8px 12px; font-weight:700; }"
        "QPushButton:hover { background-color:#5b2127; }"
    )
    controls.addStretch()
    controls.addWidget(buy_limit_btn)
    controls.addWidget(sell_limit_btn)
    controls.addWidget(reset_btn)
    controls.addWidget(submit_btn)
    layout.addLayout(controls)

    symbol_picker.currentTextChanged.connect(lambda *_: terminal._refresh_manual_trade_ticket(window))
    side_picker.currentTextChanged.connect(lambda *_: terminal._refresh_manual_trade_ticket(window))
    type_picker.currentTextChanged.connect(lambda *_: terminal._refresh_manual_trade_ticket(window))
    quantity_picker.currentTextChanged.connect(lambda *_: terminal._refresh_manual_trade_ticket(window))
    amount_input.valueChanged.connect(lambda *_: terminal._refresh_manual_trade_ticket(window))
    price_input.textChanged.connect(lambda *_: terminal._refresh_manual_trade_ticket(window))
    stop_price_input.textChanged.connect(lambda *_: terminal._refresh_manual_trade_ticket(window))
    stop_loss_input.textChanged.connect(lambda *_: terminal._refresh_manual_trade_ticket(window))
    take_profit_input.textChanged.connect(lambda *_: terminal._refresh_manual_trade_ticket(window))
    price_input.editingFinished.connect(
        lambda: terminal._apply_manual_trade_price_field_format(window, "_manual_trade_price_input")
    )
    stop_price_input.editingFinished.connect(
        lambda: terminal._apply_manual_trade_price_field_format(window, "_manual_trade_stop_price_input")
    )
    stop_loss_input.editingFinished.connect(
        lambda: terminal._apply_manual_trade_price_field_format(window, "_manual_trade_stop_loss_input")
    )
    take_profit_input.editingFinished.connect(
        lambda: terminal._apply_manual_trade_price_field_format(window, "_manual_trade_take_profit_input")
    )
    reset_btn.clicked.connect(lambda: terminal._populate_manual_trade_ticket(window, None))
    submit_btn.clicked.connect(lambda: terminal._submit_manual_trade_from_ticket(window))
    buy_limit_btn.clicked.connect(lambda: terminal._submit_manual_trade_side(window, "buy"))
    sell_limit_btn.clicked.connect(lambda: terminal._submit_manual_trade_side(window, "sell"))

    window.setCentralWidget(container)
    window._manual_trade_container = container
    window._manual_trade_hint = hint
    window._manual_trade_symbol_picker = symbol_picker
    window._manual_trade_side_picker = side_picker
    window._manual_trade_type_picker = type_picker
    window._manual_trade_quantity_picker = quantity_picker
    window._manual_trade_amount_input = amount_input
    window._manual_trade_price_label = price_label
    window._manual_trade_price_input = price_input
    window._manual_trade_stop_price_label = stop_price_label
    window._manual_trade_stop_price_input = stop_price_input
    window._manual_trade_stop_loss_input = stop_loss_input
    window._manual_trade_take_profit_input = take_profit_input
    window._manual_trade_status = status
    window._manual_trade_submit_btn = submit_btn
    window._manual_trade_reset_btn = reset_btn
    window._manual_trade_buy_limit_btn = buy_limit_btn
    window._manual_trade_sell_limit_btn = sell_limit_btn
    window._manual_trade_source = "manual"
    window.destroyed.connect(lambda *_: terminal._clear_trade_overlays())
