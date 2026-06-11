import json
from django.conf import settings
from groq import Groq

try:
    client = Groq(api_key=settings.GROQ_API_KEY)
except Exception as e:
    client = None
    print(f"Erreur d'initialisation de Groq: {e}")

MODEL_NAME = "llama-3.1-8b-instant"

def generate_subtasks(task_title, task_description):
    if not client: return []
    
    prompt = f"""Tu es un assistant chef de projet expert.
Tâche : "{task_title}"
Description : "{task_description}"

Découpe cette tâche en 3 à 5 sous-tâches réalisables.
Retourne UNIQUEMENT un objet JSON avec la clé "subtasks" contenant un tableau de chaînes de caractères.
Exemple: {{"subtasks": ["Sous-tâche 1", "Sous-tâche 2"]}}
"""
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": "Tu es un assistant JSON strict."}, {"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        content = json.loads(completion.choices[0].message.content)
        return content.get("subtasks", [])
    except Exception as e:
        print(f"Erreur generate_subtasks: {e}")
        return []

def generate_project_summary(project, tasks_data, comments_data):
    if not client: return "L'IA est indisponible."

    prompt = f"""Tu es un chef de projet analysant l'avancement d'un projet.
Projet : {project.title} (Statut: {project.get_status_display()})
Du {project.start_date} au {project.end_date}

Voici les données récentes :
Tâches: {json.dumps(tasks_data, ensure_ascii=False)}
Commentaires récents: {json.dumps(comments_data, ensure_ascii=False)}

Rédige une synthèse professionnelle en français (max 200 mots) qui résume l'avancement, les points de blocage éventuels et la suite. Sois clair et concis. N'utilise pas le format Markdown gras partout, fais des paragraphes simples.
"""
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"Erreur generate_project_summary: {e}")
        return "Impossible de générer le résumé."

def suggest_assignment(task_title, task_description, users_data):
    if not client: return None

    prompt = f"""Tu dois assigner la tâche suivante à un utilisateur de l'équipe :
Tâche : {task_title}
Description : {task_description}

Voici l'équipe et leur charge de travail :
{json.dumps(users_data, ensure_ascii=False)}

Choisis le meilleur utilisateur pour cette tâche en fonction de sa charge de travail.
Retourne UNIQUEMENT un objet JSON avec les clés "user_id" (l'ID de l'utilisateur choisi) et "reason" (une courte explication en français).
Exemple: {{"user_id": 2, "reason": "Alban a moins de tâches en cours."}}
"""
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": "Tu es un assistant JSON strict."}, {"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        content = json.loads(completion.choices[0].message.content)
        return content
    except Exception as e:
        print(f"Erreur suggest_assignment: {e}")
        return None

def get_chat_stream(messages_history, context_data):
    """
    Retourne un générateur pour streamer la réponse du chat.
    """
    if not client:
        yield "L'IA est indisponible."
        return

    system_prompt = f"""Tu es l'assistant IA intégré au logiciel de gestion de projet de l'entreprise.
Tu as accès à la base de données complète des projets, tâches, sous-tâches, ressources, commentaires et membres de l'équipe.

Voici les données actuelles du système :
{json.dumps(context_data, ensure_ascii=False, indent=2)}

Instructions :
- Réponds TOUJOURS en français.
- Base-toi UNIQUEMENT sur les données ci-dessus pour répondre. Si une information n'existe pas dans les données, dis-le clairement.
- Sois précis : cite les noms des projets, des tâches et des personnes.
- Tu peux calculer des pourcentages d'avancement, identifier les tâches en retard, résumer l'état d'un projet, etc.
- Sois concis, professionnel et utile.
- Ne propose pas de commandes ou d'actions techniques (comme "créer projet"), suggère plutôt d'utiliser l'interface.
"""
    messages = [{"role": "system", "content": system_prompt}] + messages_history

    try:
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.5,
            stream=True
        )
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content
    except Exception as e:
        print(f"Erreur chat stream: {e}")
        yield "Une erreur s'est produite lors de la génération de la réponse."
