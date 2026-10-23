"""Server-side settings only. Never return this mapping to an HTTP client."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def settings(root=ROOT):
    if hasattr(root, 'config'):
        return dict(root.config)
    values = {}
    path = Path(root) / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            name, separator, value = line.partition("=")
            if not separator:
                continue
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                try:
                    value = json.loads(value)
                except ValueError:
                    raise ValueError("Netinkamas kabutėmis apgaubtas .env laukas.") from None
            elif len(value) >= 2 and value[0] == value[-1] == "'":
                value = value[1:-1]
            values[name.strip()] = value
    for name in ("OPENAI_API_KEY", "OPENAI_MODEL", "DIASPORA_BASE_URL",
                 "DIASPORA_USERNAME", "DIASPORA_PASSWORD", "SIGNALAS_DATABASE_URL"):
        if name in os.environ:
            values[name] = os.environ[name]
    return values


def set_secret(name, value, root=ROOT):
    if name not in ("OPENAI_API_KEY", "DIASPORA_PASSWORD") or not value or "\n" in value or "\r" in value:
        raise ValueError("Reikia netuščios vienos eilutės reikšmės.")
    path = Path(root) / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replacement = name + "=" + json.dumps(value, ensure_ascii=False)
    updated, found = [], False
    for line in lines:
        if line.partition("=")[0].strip() == name:
            if not found:
                updated.append(replacement)
                found = True
        else:
            updated.append(line)
    if not found:
        updated.append(replacement)
    # The directory is private project storage, outside the served dist/ tree.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        os.chmod(path, 0o600)
        stream.write("\n".join(updated) + "\n")
