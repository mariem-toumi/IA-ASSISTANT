"""
Configuration centralisée du projet.
Charge les variables d'environnement et expose les constantes globales.
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

    # Modèles
    AGENT_MODEL = "llama-3.3-70b-versatile"
    SYNTHESIS_MODEL = "llama-3.3-70b-versatile"

    # Comportement de l'agent
    MAX_TOOL_ITERATIONS = 3
    MAX_SEARCH_RESULTS = 5

    # Flask
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    PORT = int(os.getenv("PORT", 5001))

    # Production : origine autorisée pour CORS (l'URL de ton frontend déployé).
    # En développement local, laisse "*" pour ne pas te bloquer toi-même.
    ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "*")

    # Protection anti-abus : limite le nombre de requêtes par visiteur,
    # pour éviter qu'un usage public épuise ton quota Tavily/Groq gratuit.
    RATE_LIMIT_CHAT = os.getenv("RATE_LIMIT_CHAT", "15 per hour")

    @staticmethod
    def validate():
        missing = []
        if not Config.GROQ_API_KEY:
            missing.append("GROQ_API_KEY")
        if not Config.TAVILY_API_KEY:
            missing.append("TAVILY_API_KEY")
        if missing:
            raise EnvironmentError(
                f"Variables d'environnement manquantes: {', '.join(missing)}. "
                f"Vérifie ton fichier .env (en local) ou la config de ton hébergeur (en production)."
            )
