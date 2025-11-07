import json
import os
from typing import Any, Dict

class Config:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.defaults = {
            "max_retries": 3,
            "backoff_base": 2,
            "worker_count": 1
        }
        self._load()

    def _load(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                self.config = {**self.defaults, **json.load(f)}
        else:
            self.config = self.defaults
            self._save()

    def _save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def get(self, key: str) -> Any:
        return self.config.get(key, self.defaults.get(key))

    def set(self, key: str, value: Any):
        self.config[key] = value
        self._save()

    def get_all(self) -> Dict[str, Any]:
        return dict(self.config)