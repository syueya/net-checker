import os
from dataclasses import dataclass
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    app_dir: Path
    static_dir: Path
    config_path: Path
    host: str
    port: int


def load_dotenv(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def load_settings():
    load_dotenv(APP_DIR / ".env")
    return Settings(
        app_dir=APP_DIR,
        static_dir=APP_DIR / "static",
        config_path=Path(os.environ.get("CONFIG_PATH", "./data/config.json")),
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8080")),
    )
