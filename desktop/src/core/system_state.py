
class SystemState:

    def __init__(self):
        self.running = False

        self.connected = False

        self.exchange = None

        self.symbols = []

        self.start_time = None

    # =========================
    # START SYSTEM
    # =========================

    def start(self):
        self.running = True

    # =========================
    # STOP SYSTEM
    # =========================

    def stop(self):
        self.running = False
