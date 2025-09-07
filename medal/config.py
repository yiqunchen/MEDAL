import os
from pathlib import Path


def load_dotenv_if_present() -> None:
    """Load environment variables from a .env file if it exists."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    # Load local .env without overriding existing env vars
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)


def require_env(name: str) -> str:
    """Get an environment variable or raise a clear error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing environment variable {name}. Set it in your shell or in a .env file."
        )
    return value


def get_path_from_env(name: str, default: str) -> Path:
    raw = os.getenv(name, default)
    return Path(raw).expanduser().resolve()




