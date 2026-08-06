"""
Point d'entrée Flask de l'API Live AI Assistant.
"""
import json
import logging
import uuid
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import Config
from agent import run_agent, run_agent_stream
from memory import (
    get_history,
    append_message,
    clear_session,
    list_conversations,
    get_conversation_messages,
    search_conversations,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

Config.validate()

app = Flask(__name__)
CORS(app, origins=Config.ALLOWED_ORIGIN)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "Live AI Assistant API",
        "status": "running",
        "endpoints": [
            "/api/health",
            "/api/chat",
            "/api/chat/stream",
            "/api/session/<id>",
            "/api/conversations",
            "/api/conversations/<id>",
            "/api/conversations/search"
        ]
    }), 200


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "service": "live-ai-assistant"}), 200


@app.route("/api/chat", methods=["POST"])
@limiter.limit(Config.RATE_LIMIT_CHAT)
def chat():
    data = request.get_json(silent=True)

    if not data or "message" not in data or not data["message"].strip():
        return jsonify({"error": "Le champ 'message' est requis et ne peut pas être vide."}), 400

    user_message = data["message"].strip()
    session_id = data.get("session_id") or str(uuid.uuid4())
    visitor_id = data.get("visitor_id")

    logger.info(f"[session={session_id}] Question reçue: {user_message}")

    history = get_history(session_id)
    result = run_agent(user_message, history)

    append_message(session_id, "user", user_message, visitor_id)
    append_message(session_id, "assistant", result["response"], visitor_id)

    return jsonify({
        "session_id": session_id,
        "response": result["response"],
        "sources": result.get("sources", []),
        "confidence": result.get("confidence", "n/a"),
        "tool_used": result.get("tool_used", False)
    }), 200


@app.route("/api/chat/stream", methods=["POST"])
@limiter.limit(Config.RATE_LIMIT_CHAT)
def chat_stream():
    data = request.get_json(silent=True)

    if not data or "message" not in data or not data["message"].strip():
        return jsonify({"error": "Le champ 'message' est requis et ne peut pas être vide."}), 400

    user_message = data["message"].strip()
    session_id = data.get("session_id") or str(uuid.uuid4())
    visitor_id = data.get("visitor_id")

    logger.info(f"[session={session_id}] [STREAM] Question reçue: {user_message}")

    history = get_history(session_id)

    def generate():
        yield f"data: {json.dumps({'type': 'session', 'data': session_id})}\n\n"

        final_response_text = ""

        for event in run_agent_stream(user_message, history):
            if event["type"] == "done":
                final_response_text = event["data"]["response"]

            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        if final_response_text:
            append_message(session_id, "user", user_message, visitor_id)
            append_message(session_id, "assistant", final_response_text, visitor_id)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


@app.route("/api/session/<session_id>", methods=["DELETE"])
def reset_session(session_id):
    visitor_id = request.args.get("visitor_id")
    clear_session(session_id, visitor_id)
    return jsonify({"status": "session effacée", "session_id": session_id}), 200


# --- Historique des conversations (scoped par visitor_id) ---

@app.route("/api/conversations", methods=["GET"])
def get_conversations():
    visitor_id = request.args.get("visitor_id", "")
    conversations = list_conversations(visitor_id)
    return jsonify({"conversations": conversations}), 200


@app.route("/api/conversations/search", methods=["GET"])
def search_conversations_route():
    query = request.args.get("q", "").strip()
    visitor_id = request.args.get("visitor_id", "")
    if not query:
        return jsonify({"results": []}), 200

    results = search_conversations(query, visitor_id)
    return jsonify({"results": results}), 200


@app.route("/api/conversations/<session_id>", methods=["GET"])
def get_conversation(session_id):
    visitor_id = request.args.get("visitor_id", "")
    messages = get_conversation_messages(session_id, visitor_id)
    if not messages:
        return jsonify({"error": "Conversation introuvable."}), 404

    return jsonify({"session_id": session_id, "messages": messages}), 200


@app.route("/api/conversations/<session_id>", methods=["DELETE"])
def delete_conversation(session_id):
    visitor_id = request.args.get("visitor_id", "")
    deleted = clear_session(session_id, visitor_id)
    if not deleted:
        return jsonify({"error": "Conversation introuvable ou accès refusé."}), 404
    return jsonify({"status": "conversation supprimée", "session_id": session_id}), 200


@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({
        "error": "Trop de requêtes envoyées. Merci de patienter un peu avant de réessayer."
    }), 429


if __name__ == "__main__":
    app.run(debug=Config.DEBUG, port=Config.PORT, use_reloader=False)
