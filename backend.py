from flask import Flask, request, jsonify, send_from_directory
import os
from dotenv import load_dotenv
from sarvamai import SarvamAI
load_dotenv()
api_key = os.getenv("SARVAM_API_KEY")
client = SarvamAI(api_subscription_key=api_key) if api_key else None
from urllib.request import urlopen
from urllib.parse import urlencode
import json
import html

app = Flask(__name__)

@app.route("/")
def home():
    return send_from_directory(".", "index.html")

@app.route("/translate", methods=["POST"])
def translate():
    data = request.get_json()
    message = data.get("message", "").strip()
    source = data.get("source", "en")
    target = data.get("target", "ta")

    if not message:
        return jsonify({"error": "Please enter a message."}), 400

    language_codes = {
        "en": "en-IN",
        "ta": "ta-IN",
        "hi": "hi-IN"
    }

    if client is None:
        return jsonify({
            "error": "API key not found. Check your .env file."
        }), 500

    try:
        if source in language_codes and target in language_codes:
            response = client.text.translate(
                input=message,
                source_language_code=language_codes[source],
                target_language_code=language_codes[target],
                model="mayura:v1",
                mode="modern-colloquial",
                output_script="fully-native"
            )
            translated = response.translated_text

        else:
            params = urlencode({
                "q": message,
                "langpair": f"{source}|{target}"
            })
            url = "https://api.mymemory.translated.net/get?" + params

            with urlopen(url, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))

            translated = result.get("responseData", {}).get(
                "translatedText", ""
            )

        return jsonify({"translation": translated})

    except Exception as e:
        print("Translation error:", e)
        return jsonify({
            "error": "Translation failed. Please try again."
        }), 502

if __name__ == "__main__":
    app.run(debug=True)