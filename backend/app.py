"""
Point d'entrée Flask de l'API Live AI Assistant.
"""
import logging
import uuid
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import json

from config import Config
from agent import run_agent, run_agent_stream
from memory import get_history, append_message, clear_session

# --- Setup logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# --- Validation config au démarrage ---
Config.validate()

# --- App Flask ---
app = Flask(__name__)
CORS(app)  # à restreindre en prod (origins spécifiques)

@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """
    Version streaming (SSE) de l'endpoint chat.
    Le frontend doit lire ce flux avec EventSource ou fetch + ReadableStream.
    """
    data = request.get_json(silent=True)

    if not data or "message" not in data or not data["message"].strip():
        return jsonify({"error": "Le champ 'message' est requis et ne peut pas être vide."}), 400

    user_message = data["message"].strip()
    session_id = data.get("session_id") or str(uuid.uuid4())

    logger.info(f"[session={session_id}] [STREAM] Question reçue: {user_message}")

    history = get_history(session_id)

    def generate():
        # Envoie le session_id en premier, pour que le frontend le récupère immédiatement
        yield f"data: {json.dumps({'type': 'session', 'data': session_id})}\n\n"

        final_response_text = ""

        for event in run_agent_stream(user_message, history):
            if event["type"] == "done":
                final_response_text = event["data"]["response"]

            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # Une fois le stream terminé, on sauvegarde dans la mémoire de session
        if final_response_text:
            append_message(session_id, "user", user_message)
            append_message(session_id, "assistant", final_response_text)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # évite le buffering côté proxy/nginx
        }
    )

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "Live AI Assistant API",
        "status": "running",
        "endpoints": ["/api/health", "/api/chat", "/api/session/<id>"]
    }), 200


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "service": "live-ai-assistant"}), 200


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Endpoint principal du chat.
    Body attendu (JSON) :
    {
        "message": "Quelle est l'actualité sur X ?",
        "session_id": "optionnel-uuid"
    }
    """
    data = request.get_json(silent=True)

    if not data or "message" not in data or not data["message"].strip():
        return jsonify({"error": "Le champ 'message' est requis et ne peut pas être vide."}), 400

    user_message = data["message"].strip()
    session_id = data.get("session_id") or str(uuid.uuid4())

    logger.info(f"[session={session_id}] Question reçue: {user_message}")

    history = get_history(session_id)

    result = run_agent(user_message, history)

    # Mise à jour de la mémoire de session
    append_message(session_id, "user", user_message)
    append_message(session_id, "assistant", result["response"])

    return jsonify({
        "session_id": session_id,
        "response": result["response"],
        "sources": result.get("sources", []),
        "confidence": result.get("confidence", "n/a"),
        "tool_used": result.get("tool_used", False)
    }), 200


@app.route("/api/session/<session_id>", methods=["DELETE"])
def reset_session(session_id):
    clear_session(session_id)
    return jsonify({"status": "session effacée", "session_id": session_id}), 200


if __name__ == "__main__":
    app.run(debug=Config.DEBUG, port=Config.PORT, use_reloader=False)