import os
import json
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

PERSONAS = {
    "bull": {
        "name": "Bull",
        "emoji": "🐂",
        "color": "#16a34a",
        "system": (
            "You are the Bull analyst on an investment team. You are optimistic and find "
            "compelling reasons to invest in stocks. For each idea discussed, you highlight: "
            "growth catalysts, competitive moats, market opportunities, strong financials, "
            "momentum, and why now is a good entry point. Be analytical but enthusiastic. "
            "Keep responses to 3-5 punchy bullet points. Use $ for prices and % for returns. "
            "Do not use markdown headers. Start directly with your analysis."
        ),
    },
    "bear": {
        "name": "Bear",
        "emoji": "🐻",
        "color": "#dc2626",
        "system": (
            "You are the Bear analyst on an investment team. You are skeptical and identify "
            "risks, overvaluations, and reasons for caution. For each idea discussed, you highlight: "
            "valuation concerns, competitive threats, execution risks, macro headwinds, "
            "red flags in financials, and why the thesis might be wrong. Be sharp and contrarian. "
            "Keep responses to 3-5 punchy bullet points. Use $ for prices and % for returns. "
            "Do not use markdown headers. Start directly with your analysis."
        ),
    },
}

conversation_history = []


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    conversation_history.append({"role": "user", "content": user_message})

    responses = {}
    for persona_key, persona in PERSONAS.items():
        messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in conversation_history
        ]

        result = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=persona["system"],
            messages=messages,
        )
        text = result.content[0].text
        responses[persona_key] = {
            "name": persona["name"],
            "emoji": persona["emoji"],
            "color": persona["color"],
            "text": text,
        }

    # Append a combined assistant turn so future context is shared
    combined = "\n\n".join(
        f"[{r['name']}]: {r['text']}" for r in responses.values()
    )
    conversation_history.append({"role": "assistant", "content": combined})

    return jsonify({"responses": responses})


@app.route("/reset", methods=["POST"])
def reset():
    conversation_history.clear()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
