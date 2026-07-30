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
    AGENT_MODEL = "llama-3.3-70b-versatile"   # raisonnement + tool calling
    SYNTHESIS_MODEL = "llama-3.3-70b-versatile"

    # Comportement de l'agent
    MAX_TOOL_ITERATIONS = 3       # évite les boucles infinies d'appels d'outils
    MAX_SEARCH_RESULTS = 5

    # Flask
    DEBUG = True
    PORT = 5001

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
                f"Vérifie ton fichier .env"
            )