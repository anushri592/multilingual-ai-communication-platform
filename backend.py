
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
from sarvamai import SarvamAI
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import os
import json

load_dotenv()
app = Flask(__name__)

sarvam_key = os.getenv("SARVAM_API_KEY")
deepl_key = os.getenv("DEEPL_AUTH_KEY")

sarvam = SarvamAI(api_subscription_key=sarvam_key) if sarvam_key else None

LANGUAGES = {"en", "ta", "hi", "fr", "es"}
SARVAM_CODES = {
    "en": "en-IN",
    "ta": "ta-IN",
    "hi": "hi-IN"
}


def deepl_translate(text, source, target):
    source = source.upper()
    target = target.upper()

    if source == target:
        return text

    if not deepl_key:
        raise ValueError("DEEPL_AUTH_KEY is missing from environment settings")

    body = json.dumps({
        "text": [text],
        "source_lang": source,
        "target_lang": target
    }).encode("utf-8")

    req = Request(
        "https://api-free.deepl.com/v2/translate",
        data=body,
        headers={
            "Authorization": f"DeepL-Auth-Key {deepl_key}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        app.logger.error("DeepL HTTP %s: %s", e.code, detail)
        raise ValueError(f"DeepL API error (HTTP {e.code})") from e
    except URLError as e:
        app.logger.error("DeepL connection error: %s", e)
        raise ValueError("Could not connect to DeepL") from e

    translations = result.get("translations", [])
    if not translations:
        raise ValueError("DeepL returned no translation")

    return translations[0]["text"].strip()


def sarvam_translate(text, source, target):
    if source == target:
        return text

    if not sarvam:
        raise ValueError("SARVAM_API_KEY is missing from environment settings")

    if source not in SARVAM_CODES or target not in SARVAM_CODES:
        raise ValueError("Unsupported language for Sarvam translation")

    result = sarvam.text.translate(
        input=text,
        source_language_code=SARVAM_CODES[source],
        target_language_code=SARVAM_CODES[target],
        model="mayura:v1",
        mode="formal",
        output_script="fully-native"
    )

    translated = getattr(result, "translated_text", "")
    if not translated:
        raise ValueError("Sarvam returned no translation")

    return translated.strip()


def translate_text(text, source, target):
    if source == target:
        return text

    source_indian = source in SARVAM_CODES
    target_indian = target in SARVAM_CODES

    # English, Tamil and Hindi
    if source_indian and target_indian:
        return sarvam_translate(text, source, target)

    # French/Spanish to English, then to Tamil/Hindi
    if source in {"fr", "es"} and target_indian:
        english = deepl_translate(text, source, "en")
        if target == "en":
            return english
        return sarvam_translate(english, "en", target)

    # Tamil/Hindi to English, then to French/Spanish
    if source_indian and target in {"fr", "es"}:
        english = sarvam_translate(text, source, "en")
        return deepl_translate(english, "en", target)

    # English, French and Spanish direct translation
    return deepl_translate(text, source, target)


@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/translate", methods=["POST"])
def translate():
    data = request.get_json(silent=True) or {}

    message = str(data.get("message", "")).strip()
    source = str(data.get("source", "en")).lower()
    target = str(data.get("target", "ta")).lower()

    if not message:
        return jsonify({"error": "Please enter text."}), 400

    if source not in LANGUAGES or target not in LANGUAGES:
        return jsonify({"error": "Unsupported language."}), 400

    try:
        result = translate_text(message, source, target)
        return jsonify({"translation": result})

    except Exception:
        app.logger.exception("Translation failed")
        return jsonify({
            "error": "Translation failed. Check Render logs and API settings."
        }), 502


if __name__ == "__main__":
    app.run(debug=True)
