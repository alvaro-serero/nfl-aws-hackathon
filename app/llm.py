"""Rephrase the Chip Advisor recommendation as two coach sentences via Amazon Bedrock (boto3 converse API).

Model: env var BEDROCK_MODEL_ID (region: AWS_REGION / AWS_DEFAULT_REGION, default us-east-1).
Without the model id, AWS credentials or on any error, returns the fallback text unchanged: the app never breaks.
"""
import os

SYSTEM = ("Tu es l'assistant d'un coordinateur offensif NFL. On te donne des taux observés sur les données NGS/PFF "
          "2021. Reformule-les en exactement deux phrases de coach, en français, directes et concrètes. "
          "N'invente aucun chiffre : reprends uniquement ceux fournis.")


def coach_phrase(facts, fallback):
    """Returns (text, source) where source says whether Bedrock answered or the fallback was used."""
    model_id = os.environ.get("BEDROCK_MODEL_ID")
    if not model_id:
        return fallback, "texte de secours (BEDROCK_MODEL_ID non défini)"
    try:
        import boto3

        session = boto3.Session(region_name=os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")))
        if session.get_credentials() is None:
            return fallback, "texte de secours (pas d'identifiants AWS)"
        resp = session.client("bedrock-runtime").converse(
            modelId=model_id,
            system=[{"text": SYSTEM}],
            messages=[{"role": "user", "content": [{"text": facts}]}],
            inferenceConfig={"maxTokens": 400},
        )
        text = " ".join(b["text"] for b in resp["output"]["message"]["content"] if "text" in b).strip()
        return (text, f"Amazon Bedrock ({model_id})") if text else (fallback, "texte de secours (réponse vide)")
    except Exception as exc:  # demo must survive any AWS failure
        return fallback, f"texte de secours (erreur Bedrock : {type(exc).__name__})"
