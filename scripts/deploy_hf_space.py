"""Deploy the Kettu API to a Hugging Face Docker Space.

Uploads only backend/src, requirements.txt and the Dockerfile (never .env files). Keys from
backend/.env.local become private Space secrets; other settings become Space variables.

    python scripts/deploy_hf_space.py --space AdithyaSNair/kettu-api --cors "https://kettu.vercel.app,http://localhost:3000"

Needs: pip install huggingface_hub, and `hf auth login` with a write token.
"""

import argparse
import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"

SECRETS = ["GNANI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "SUPABASE_SERVICE_KEY"]
VARIABLES = [
    "SPEECH_PROVIDER", "PRISMA_MODEL", "TIMBRE_MODEL", "TIMBRE_FALLBACK_MODEL", "TIMBRE_VOICE_FEMALE",
    "TIMBRE_VOICE_MALE", "GNANI_CONCURRENCY", "LLM_PROVIDER", "LLM_FALLBACK_PROVIDER", "ANTHROPIC_MODEL",
    "GEMINI_MODEL", "SUPABASE_URL", "NOTES_PER_DAY", "REPLIES_PER_DAY", "DAILY_STT_SECONDS_CAP",
    "DAILY_TTS_CHARS_CAP",
]

SPACE_CARD = """---
title: Kettu API
emoji: 👂
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 8080
pinned: false
short_description: Indian-language voice notes, understood and answered
---

Backend for **Kettu**: share a WhatsApp voice note, read it in your language, reply by voice in theirs.
Built on Gnani Prisma v3.0 (speech to text) and Timbre v3.0 (text to speech).

No audio or transcript is stored. Health check: `/healthz`.
"""


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", required=True, help="owner/name, e.g. AdithyaSNair/kettu-api")
    ap.add_argument("--cors", required=True, help="comma-separated web origins allowed to call the API")
    args = ap.parse_args()

    env = {**read_env(BACKEND / ".env"), **read_env(BACKEND / ".env.local")}
    owner, name = args.space.split("/")
    public_url = f"https://{owner.lower()}-{name.lower().replace('_', '-')}.hf.space"

    api = HfApi()
    api.create_repo(args.space, repo_type="space", space_sdk="docker", exist_ok=True, private=False)

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        shutil.copytree(BACKEND / "src", stage / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copy(BACKEND / "requirements.txt", stage / "requirements.txt")
        shutil.copy(BACKEND / "Dockerfile", stage / "Dockerfile")
        (stage / "README.md").write_text(SPACE_CARD, encoding="utf-8")
        leaked = [p.name for p in stage.rglob("*") if p.name.startswith(".env")]
        assert not leaked, f"refusing to upload env files: {leaked}"
        api.upload_folder(repo_id=args.space, repo_type="space", folder_path=stage,
                          commit_message="Deploy Kettu API", delete_patterns=["src/**"])

    for key in SECRETS:
        if env.get(key):
            api.add_space_secret(args.space, key, env[key])
            print(f"secret   {key}: set")
    variables = {k: env[k] for k in VARIABLES if env.get(k)}
    variables.update(CORS_ORIGINS=args.cors, PUBLIC_API_URL=public_url, SPEECH_PROVIDER=env.get("SPEECH_PROVIDER", "gnani"))
    for key, value in variables.items():
        api.add_space_variable(args.space, key, value)
        print(f"variable {key}: {value}")

    print(f"\nSpace: https://huggingface.co/spaces/{args.space}")
    print(f"API:   {public_url}  (first build takes a few minutes)")


if __name__ == "__main__":
    main()
