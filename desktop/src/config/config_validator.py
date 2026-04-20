from config.config import AppConfig


class ConfigValidator:

    REQUIRED_KEYS = ["broker", "risk", "system"]

    @staticmethod
    def validate(config):

        # If using AppConfig object
        if isinstance(config, AppConfig):

            if config.broker is None:
                raise ValueError("Missing config section: broker")

            if config.risk is None:
                raise ValueError("Missing config section: risk")

            if config.system is None:
                raise ValueError("Missing config section: system")

            return True

        # Fallback for dictionary configs
        for key in ConfigValidator.REQUIRED_KEYS:

            if key not in config:
                raise ValueError(f"Missing config section: {key}")

        return True