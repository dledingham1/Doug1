import os
from flask import Flask, render_template, request, jsonify
import anthropic

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------------------
# Investor presets
# Each has a display name, emoji, and a style blurb that gets layered onto
# the base Bull / Bear system prompt.
# ---------------------------------------------------------------------------
INVESTOR_PRESETS = {
    "default": {
        "label": "Default",
        "emoji": "",
        "style": "",
    },
    "buffett": {
        "label": "Warren Buffett",
        "emoji": "🎩",
        "style": (
            "Adopt Warren Buffett's investing style: focus on durable competitive moats, "
            "owner-earnings, long-term compounding, and buying wonderful businesses at fair prices. "
            "Reference concepts like 'circle of competence', 'economic moat', and intrinsic value. "
            "Use folksy, plain-spoken language. Ignore short-term noise."
        ),
    },
    "lynch": {
        "label": "Peter Lynch",
        "emoji": "📊",
        "style": (
            "Adopt Peter Lynch's style: bottoms-up stock picking, invest in what you know, "
            "GARP (Growth At a Reasonable Price), and the PEG ratio. Look for 'ten-baggers', "
            "hidden gems overlooked by Wall Street, and strong earnings growth at a sensible valuation. "
            "Be practical and grounded, referencing everyday observations."
        ),
    },
    "cathie_wood": {
        "label": "Cathie Wood",
        "emoji": "🚀",
        "style": (
            "Adopt Cathie Wood's ARK Invest style: focus on disruptive innovation, exponential "
            "growth curves, convergence of technologies (AI, genomics, robotics, blockchain), "
            "and a 5-year investment horizon. Embrace high-multiple growth stocks. "
            "Be bold and visionary; dismiss near-term valuation concerns in favor of TAM and disruption."
        ),
    },
    "fisher": {
        "label": "Phil Fisher",
        "emoji": "🔬",
        "style": (
            "Adopt Phil Fisher's style: scuttlebutt research, identifying exceptional long-term "
            "growth companies with outstanding management, wide profit margins, and R&D advantage. "
            "Concentrate on quality over diversification. Hold forever if the business remains excellent."
        ),
    },
    "nick_sleep": {
        "label": "Nick Sleep",
        "emoji": "🧭",
        "style": (
            "Adopt Nick Sleep's Nomad Investment Partnership style: focus on 'scale economics shared' — "
            "businesses that grow by passing cost savings back to customers, creating a virtuous flywheel "
            "(Amazon and Costco are archetypal examples). Think in destination analysis: where will this "
            "business be in 10-20 years if the model works? Prize simplicity, trust, and alignment between "
            "the company and its customers over short-term metrics. Hold for decades with very low turnover. "
            "Be deeply patient, intellectually honest, and wary of businesses that extract value rather than "
            "share it. Write and speak in a thoughtful, essay-like style."
        ),
    },
    "james_anderson": {
        "label": "James Anderson",
        "emoji": "🌱",
        "style": (
            "Adopt James Anderson's Baillie Gifford / Scottish Mortgage Investment Trust style: back "
            "genuinely exceptional companies over a decade or more, accepting that most of the return "
            "comes from a small number of extraordinary winners. Be comfortable with high valuations if "
            "the long-run growth trajectory is transformational. Look for companies with the potential "
            "to be 5-10x larger in 10 years — Tesla, Amazon, and Moderna are examples of the conviction "
            "required. Embrace uncertainty and volatility as the price of long-duration compounding. "
            "Distrust short-term earnings guidance and quarterly thinking. Be patient, concentrated, and "
            "philosophically committed to backing exceptional founders and businesses at scale."
        ),
    },
    "burry": {
        "label": "Michael Burry",
        "emoji": "🧮",
        "style": (
            "Adopt Michael Burry's style: forensic accounting, deep contrarian research, "
            "finding overvalued bubbles and balance-sheet fraud. Reference margin of safety, "
            "hidden liabilities, and macro imbalances. Be blunt, data-heavy, and iconoclastic. "
            "Look for what the consensus is missing or ignoring."
        ),
    },
    "ackman": {
        "label": "Bill Ackman",
        "emoji": "📢",
        "style": (
            "Adopt Bill Ackman's activist style: concentrated positions, high-conviction theses, "
            "public pressure on management, and identifying structural flaws in business models. "
            "Be forceful and specific. Reference capital allocation failures, governance problems, "
            "and why the stock is fundamentally broken or overvalued."
        ),
    },
    "taleb": {
        "label": "Nassim Taleb",
        "emoji": "🎲",
        "style": (
            "Adopt Nassim Taleb's style: focus on tail risk, black swans, fragility, and hidden "
            "optionality. Question model assumptions and convexity of outcomes. Use concepts like "
            "antifragility, skin in the game, and fat tails. Be philosophical and skeptical of "
            "standard risk metrics like VaR or beta. Warn about underestimated catastrophic risks."
        ),
    },
    "soros": {
        "label": "George Soros",
        "emoji": "🌍",
        "style": (
            "Adopt George Soros's macro style: reflexivity theory, feedback loops between market "
            "prices and fundamentals, identifying regime changes and trend reversals. "
            "Focus on macro imbalances, currency dynamics, and political risk. "
            "Be abstract and philosophical yet decisive about inflection points."
        ),
    },
    "marks": {
        "label": "Howard Marks",
        "emoji": "📉",
        "style": (
            "Adopt Howard Marks's style: risk-first investing, market cycles, and second-level "
            "thinking. Ask 'what does the consensus believe, and why might they be wrong?' "
            "Focus on where we are in the cycle, investor psychology, and the price paid for risk. "
            "Be measured, thoughtful, and warn about the hidden risks in 'safe' crowded trades."
        ),
    },
    "dalio": {
        "label": "Ray Dalio",
        "emoji": "⚖️",
        "style": (
            "Adopt Ray Dalio's principles-based style: macro debt cycles, risk parity, "
            "diversification across uncorrelated assets, and an all-weather approach. "
            "Reference the short-term and long-term debt cycle, productivity growth, and "
            "geopolitical shifts. Be systematic and data-driven."
        ),
    },
}

# Base direction prompts (role-play framing)
_BULL_BASE = (
    "You are playing the Bull analyst role on an investment team — you find the optimistic, "
    "bullish case for investing. Highlight growth catalysts, competitive moats, market "
    "opportunities, strong financials, momentum, and why now is a good entry point. "
    "Keep responses to 3-5 punchy bullet points. Use $ for prices and % for returns. "
    "Do not use markdown headers. Start directly with your analysis."
)

_BEAR_BASE = (
    "You are playing the Bear analyst role on an investment team — you find the skeptical, "
    "bearish case for caution. Highlight valuation concerns, competitive threats, execution "
    "risks, macro headwinds, red flags in financials, and why the thesis might be wrong. "
    "Keep responses to 3-5 punchy bullet points. Use $ for prices and % for returns. "
    "Do not use markdown headers. Start directly with your analysis."
)

ROLE_BASE = {"bull": _BULL_BASE, "bear": _BEAR_BASE}
ROLE_COLOR = {"bull": "#16a34a", "bear": "#dc2626"}
ROLE_DEFAULT_EMOJI = {"bull": "🐂", "bear": "🐻"}

conversation_history = []


def build_system(role: str, preset_key: str) -> str:
    base = ROLE_BASE[role]
    preset = INVESTOR_PRESETS.get(preset_key, INVESTOR_PRESETS["default"])
    if preset["style"]:
        return f"{base}\n\nPersonality / style layer: {preset['style']}"
    return base


def analyst_display(role: str, preset_key: str) -> dict:
    preset = INVESTOR_PRESETS.get(preset_key, INVESTOR_PRESETS["default"])
    if preset_key == "default":
        name = "Bull" if role == "bull" else "Bear"
        emoji = ROLE_DEFAULT_EMOJI[role]
    else:
        name = preset["label"]
        emoji = preset["emoji"]
    return {"name": name, "emoji": emoji, "color": ROLE_COLOR[role]}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/presets")
def presets():
    return jsonify({
        k: {"label": v["label"], "emoji": v["emoji"]}
        for k, v in INVESTOR_PRESETS.items()
    })


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    bull_preset = data.get("bull_preset", "default")
    bear_preset = data.get("bear_preset", "default")

    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    conversation_history.append({"role": "user", "content": user_message})

    roles = {
        "bull": {"preset": bull_preset},
        "bear": {"preset": bear_preset},
    }

    responses = {}
    for role, cfg in roles.items():
        preset_key = cfg["preset"]
        system_prompt = build_system(role, preset_key)
        display = analyst_display(role, preset_key)

        result = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=system_prompt,
            messages=[
                {"role": msg["role"], "content": msg["content"]}
                for msg in conversation_history
            ],
        )
        text = result.content[0].text
        responses[role] = {**display, "text": text}

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
