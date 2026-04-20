class BrokerOperationError(RuntimeError):
    """Structured broker exception that carries handling hints for callers."""

    def __init__(
        self,
        message,
        *,
        category="broker_error",
        retryable=False,
        rejection=False,
        cooldown_seconds=None,
        raw_message=None,
    ):
        super().__init__(str(message))
        self.category = str(category or "broker_error")
        self.retryable = bool(retryable)
        self.rejection = bool(rejection)
        self.cooldown_seconds = (
            float(cooldown_seconds) if cooldown_seconds not in (None, "") else None
        )
        self.raw_message = str(raw_message or message)
