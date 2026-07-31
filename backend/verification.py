"""
Couche de vérification des réponses.
Construit le prompt système qui force le LLM à citer ses sources
et à signaler les incertitudes ou contradictions.
"""

VERIFICATION_SYSTEM_PROMPT = """Tu es un assistant IA rigoureux qui répond en te basant sur des informations vérifiées.

RÈGLES STRICTES :
1. Si tu utilises l'outil search_web, base ta réponse UNIQUEMENT sur les résultats retournés.
2. Chaque affirmation factuelle importante doit être suivie de sa source entre crochets, format : [Source: nom_du_site]
3. Si plusieurs sources se contredisent, signale-le explicitement à l'utilisateur.
4. Si les résultats de recherche ne permettent pas de répondre avec certitude, dis-le clairement plutôt que d'inventer une réponse.
5. Pour les questions de connaissance générale (non temporelles), tu peux répondre directement sans recherche.
6. Si la recherche web est indisponible (problème réseau), explique brièvement et simplement que tu ne peux pas vérifier l'information pour le moment, sans détailler la cause technique, et propose à l'utilisateur de réessayer.
7. Termine ta réponse par un niveau de confiance : [Confiance: Haute/Moyenne/Faible] uniquement si tu as utilisé une recherche web.

Sois concis, précis, et toujours honnête sur les limites de ce que tu sais."""


def build_verification_context(search_results: dict) -> str:
    """
    Transforme les résultats de recherche en un contexte textuel structuré
    et lisible pour le LLM, avec les sources clairement identifiées.
    """
    if search_results.get("error") == "network_unavailable":
        return (
            "La recherche web n'a pas pu aboutir en raison d'un problème réseau temporaire. "
            "Aucune source n'est disponible pour cette question. "
            "Informe l'utilisateur simplement que la vérification en direct n'a pas pu se faire "
            "et propose de réessayer dans un instant, sans mentionner de détails techniques."
        )

    if search_results.get("error"):
        return f"Erreur lors de la recherche: {search_results['error']}"

    if not search_results.get("sources"):
        return "Aucun résultat trouvé pour cette recherche."

    context_parts = [f"Résumé rapide: {search_results.get('answer_summary', 'N/A')}\n"]

    for i, source in enumerate(search_results["sources"], 1):
        context_parts.append(
            f"[Source {i}: {source['title']}]\n"
            f"URL: {source['url']}\n"
            f"Contenu: {source['content'][:500]}...\n"
        )

    return "\n".join(context_parts)


def check_source_agreement(search_results: dict) -> str:
    """
    Heuristique simple de cohérence : vérifie si plusieurs sources existent.
    (Peut être enrichi plus tard avec une vraie comparaison sémantique.)
    """
    sources = search_results.get("sources", [])
    if len(sources) == 0:
        return "no_sources"
    elif len(sources) == 1:
        return "single_source"
    else:
        return "multiple_sources"
