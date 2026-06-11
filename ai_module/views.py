from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.http import StreamingHttpResponse
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse, inline_serializer
from rest_framework import serializers as drf_serializers
from projects.models import Project, Task
from .services import generate_subtasks, generate_project_summary, suggest_assignment, get_chat_stream

User = get_user_model()


@extend_schema(
    tags=['AI'],
    summary="Générer des sous-tâches",
    description="Envoie le titre et la description d'une tâche à l'IA (Groq) et retourne une liste de 3 à 5 sous-tâches logiques.",
    request=inline_serializer(
        name='SubtasksInput',
        fields={
            'title': drf_serializers.CharField(help_text="Titre de la tâche principale"),
            'description': drf_serializers.CharField(required=False, help_text="Description optionnelle"),
        }
    ),
    responses={
        200: inline_serializer(
            name='SubtasksOutput',
            fields={'subtasks': drf_serializers.ListField(child=drf_serializers.CharField())}
        ),
        400: OpenApiResponse(description="Titre manquant"),
    },
)

class GenerateSubtasksView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        title = request.data.get('title')
        description = request.data.get('description', '')
        
        if not title:
            return Response({"error": "Le titre de la tâche est requis."}, status=status.HTTP_400_BAD_REQUEST)
            
        subtasks = generate_subtasks(title, description)
        return Response({"subtasks": subtasks})


@extend_schema(
    tags=['AI'],
    summary="Synthèse intelligente d'un projet",
    description="Génère un résumé professionnel en français de l'avancement du projet (tâches, commentaires, retards).",
    responses={
        200: inline_serializer(
            name='ProjectSummaryOutput',
            fields={'summary': drf_serializers.CharField(help_text="Texte de synthèse généré par l'IA")}
        ),
        404: OpenApiResponse(description="Projet introuvable"),
    },
)
class GenerateProjectSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"error": "Projet introuvable."}, status=status.HTTP_404_NOT_FOUND)
            
        # Collecter les données
        tasks = project.tasks.all()
        tasks_data = [
            {"titre": t.title, "status": t.get_status_display(), "assigné_à": t.user.email} 
            for t in tasks
        ]
        
        comments_data = []
        for t in tasks:
            for c in t.comments.all()[:3]: # Prendre les derniers commentaires
                comments_data.append(f"{c.author.email}: {c.content}")
                
        summary = generate_project_summary(project, tasks_data, comments_data)
        return Response({"summary": summary})


@extend_schema(
    tags=['AI'],
    summary="Suggérer l'assignation d'une tâche",
    description="Analyse la charge de travail de chaque utilisateur et recommande la personne la plus disponible pour réaliser la tâche.",
    request=inline_serializer(
        name='AssignmentInput',
        fields={
            'title': drf_serializers.CharField(help_text="Titre de la tâche"),
            'description': drf_serializers.CharField(required=False, help_text="Description optionnelle"),
        }
    ),
    responses={
        200: inline_serializer(
            name='AssignmentOutput',
            fields={
                'user_id': drf_serializers.IntegerField(help_text="ID de l'utilisateur suggéré"),
                'reason': drf_serializers.CharField(help_text="Explication de la suggestion"),
            }
        ),
        400: OpenApiResponse(description="Titre manquant"),
        500: OpenApiResponse(description="Erreur IA"),
    },
)
class SuggestAssignmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        title = request.data.get('title')
        description = request.data.get('description', '')
        
        if not title:
            return Response({"error": "Le titre de la tâche est requis."}, status=status.HTTP_400_BAD_REQUEST)
            
        # Récupérer tous les utilisateurs avec le compte de leurs tâches en cours
        users = User.objects.all()
        users_data = []
        for u in users:
            active_tasks = u.tasks.exclude(status='done').count()
            users_data.append({"id": u.id, "email": u.email, "taches_actives": active_tasks})
            
        suggestion = suggest_assignment(title, description, users_data)
        if suggestion:
            return Response(suggestion)
        return Response({"error": "Impossible de générer une suggestion."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    tags=['AI'],
    summary="Chat assistant projet (streaming)",
    description=(
        "Envoie un historique de messages à l'IA qui a accès au contexte des projets de l'utilisateur. "
        "La réponse est retournée en **streaming** (text/plain chunks)."
    ),
    request=inline_serializer(
        name='ChatInput',
        fields={
            'messages': drf_serializers.ListField(
                child=inline_serializer(
                    name='ChatMessage',
                    fields={
                        'role': drf_serializers.ChoiceField(choices=['user', 'assistant']),
                        'content': drf_serializers.CharField(),
                    }
                ),
                help_text="Historique des messages (role: 'user' ou 'assistant')"
            )
        }
    ),
    responses={200: OpenApiResponse(description="Réponse en streaming (text/plain)")},
)
class ChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        messages = request.data.get('messages', [])
        
        # ── Construire un contexte COMPLET de tous les projets ──
        projects = Project.objects.prefetch_related(
            'tasks__user',
            'tasks__subtasks',
            'tasks__resources',
            'tasks__comments__author',
            'client',
        ).all()

        projects_data = []
        for p in projects:
            tasks_list = []
            for t in p.tasks.all():
                task_info = {
                    "titre": t.title,
                    "description": t.description or "",
                    "statut": t.get_status_display(),
                    "priorité": t.get_priority_display(),
                    "assigné_à": f"{t.user.first_name} {t.user.last_name} ({t.user.email})" if t.user else "Non assigné",
                    "date_début": str(t.start_date.date()) if t.start_date else "Non définie",
                    "échéance": str(t.due_date.date()) if t.due_date else "Non définie",
                    "terminée": t.is_completed,
                }
                # Sous-tâches
                subtasks = list(t.subtasks.all())
                if subtasks:
                    task_info["sous_tâches"] = [
                        {"titre": st.title, "fait": st.is_done} for st in subtasks
                    ]
                # Ressources
                resources = list(t.resources.all())
                if resources:
                    task_info["ressources"] = [
                        {"nom": r.name, "type": r.get_resource_type_display()} for r in resources
                    ]
                # Commentaires récents (les 5 derniers)
                comments = list(t.comments.order_by('-created_at')[:5])
                if comments:
                    task_info["commentaires_récents"] = [
                        {"auteur": c.author.email, "contenu": c.content[:200], "date": str(c.created_at.date())}
                        for c in comments
                    ]
                tasks_list.append(task_info)

            project_info = {
                "nom": p.title,
                "description": p.description or "",
                "statut": p.get_status_display(),
                "date_début": str(p.start_date.date()) if p.start_date else "Non définie",
                "date_fin": str(p.end_date.date()) if p.end_date else "Non définie",
                "client": str(p.client) if p.client else "Aucun",
                "nombre_tâches": len(tasks_list),
                "tâches_terminées": sum(1 for t in tasks_list if t["terminée"]),
                "tâches": tasks_list,
            }
            # Membres de l'équipe (utilisateurs distincts ayant des tâches)
            team_members = set()
            for t in p.tasks.all():
                if t.user:
                    team_members.add(f"{t.user.first_name} {t.user.last_name} ({t.user.email})")
            if team_members:
                project_info["équipe"] = list(team_members)

            projects_data.append(project_info)

        # Statistiques globales
        all_tasks = Task.objects.all()
        stats = {
            "total_projets": len(projects_data),
            "total_tâches": all_tasks.count(),
            "tâches_à_faire": all_tasks.filter(status='todo').count(),
            "tâches_en_cours": all_tasks.filter(status='in_progress').count(),
            "tâches_terminées": all_tasks.filter(status='done').count(),
        }

        context_data = {
            "statistiques_globales": stats,
            "projets": projects_data,
        }

        # Créer le générateur de réponse en streaming
        def stream():
            for chunk in get_chat_stream(messages, context_data):
                yield chunk
                
        response = StreamingHttpResponse(stream(), content_type='text/plain; charset=utf-8')
        response['Cache-Control'] = 'no-cache'
        return response

