class ModelRegistry:
    def __init__(self):
        self._models = {}
        self._metadata = {}

    def register(self, name, model, metadata=None):
        key = str(name or "").strip()
        if not key:
            raise ValueError("Model name is required")
        self._models[key] = model
        self._metadata[key] = dict(metadata or {})

    def get(self, name, default=None):
        return self._models.get(str(name or "").strip(), default)

    def get_metadata(self, name, default=None):
        return self._metadata.get(str(name or "").strip(), default)

    def list(self):
        return list(self._models.keys())

    def items(self):
        for key, model in self._models.items():
            yield key, model, dict(self._metadata.get(key, {}))
