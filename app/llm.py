"""Coach briefing in two sentences via the Mistral API (chat completions).

Key: MISTRAL_API_KEY, from the environment or the repo's .env file (git-ignored, never committed).
Model: MISTRAL_MODEL (default mistral-large-latest). Without a key or on any error, returns the fallback text.
"""
import json
import os
import urllib.request
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"
URL = "https://api.mistral.ai/v1/chat/completions"
SYSTEM = ("Tu es l'assistant d'un coordinateur offensif NFL. On te donne une recommandation de chip et des taux "
          "observés (NGS/PFF 2021). Reformule-la en exactement deux phrases courtes, en français, à l'impératif, "
          "comme un coach parle à ses joueurs, avec des mots simples de football. Cite les deux taux de pression "
          "(sans chip, avec chip) et le plan B s'il est fourni. N'invente aucun chiffre. Pas de guillemets.")


def _key():
    if os.environ.get("MISTRAL_API_KEY"):
        return os.environ["MISTRAL_API_KEY"]
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "MISTRAL_API_KEY":
                return value.strip().strip("'\"")
    return None


def coach_brief(facts, fallback):
    """Returns (text, source); source says whether Mistral answered or the fallback was used."""
    key = _key()
    if not key:
        return fallback, "texte de secours (pas de clé Mistral)"
    model = os.environ.get("MISTRAL_MODEL", "mistral-large-latest")
    body = {"model": model, "max_tokens": 200,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": facts}]}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            text = json.load(resp)["choices"][0]["message"]["content"].strip().strip("\"«» ")
        return (text, f"Mistral ({model})") if text else (fallback, "texte de secours (réponse vide)")
    except Exception as exc:  # the demo must survive any network or API failure
        return fallback, f"texte de secours (erreur Mistral : {type(exc).__name__})"
