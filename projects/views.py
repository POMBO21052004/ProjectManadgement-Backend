import logging

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count, Q
from .models import Task, Project, Resource, Client
from .serializers import (
    TaskSerializer, TaskCreateSerializer, TaskUpdateSerializer, TaskWithProjectSerializer,
    ProjectSerializer, ProjectCreateSerializer, ProjectUpdateSerializer, ProjectWithTasksSerializer,
    UserSimpleSerializer, ResourceSerializer, ClientSerializer
)
from .permissions import IsOwnerOrAdmin, IsAdminUser

logger = logging.getLogger(__name__)


def send_task_assignment_email(task):
    if not task or not task.user or not task.user.email:
        return
    
    due_display = "Non dÃ©finie"
    if task.due_date:
        due_display = timezone.localtime(task.due_date).strftime("%d/%m/%Y %H:%M")
    
    project_info = task.project.title if task.project else "Sans projet"
    message = (
        f"Bonjour {task.user.get_full_name() or task.user.username},\n\n"
        f"Une nouvelle tÃ¢che vous a Ã©tÃ© assignÃ©e.\n"
        f"Titre : {task.title}\n"
        f"Projet : {project_info}\n"
        f"Date d'Ã©chÃ©ance : {due_display}\n\n"
        "Merci de vous connecter Ã  la plateforme pour plus de dÃ©tails."
    )
    
    try:
        send_mail(
            subject=f"Nouvelle tÃ¢che : {task.title}",
            message=message,
            from_email=getattr(settings, 'EMAIL_HOST_USER', None),
            recipient_list=[task.user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.warning("Impossible d'envoyer l'email d'assignation pour la tÃ¢che %s", task.id, exc_info=exc)


@extend_schema(tags=['Projects'])
class ProjectViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gÃ©rer les projets (GLOBAL - pas assignÃ© aux utilisateurs)
    Tout le monde peut voir les projets
    Seuls les admins peuvent crÃ©er/modifier/supprimer
    """
    serializer_class = ProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'title']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Les admins voient tout, les utilisateurs voient seulement leurs projets"""
        user = self.request.user
        if user.is_staff or getattr(user, 'is_admin', False):
            return Project.objects.all()
        return Project.objects.filter(users=user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ProjectCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ProjectUpdateSerializer
        elif self.action == 'with_tasks':
            return ProjectWithTasksSerializer
        return ProjectSerializer
    
    def get_permissions(self):
        """Seuls les admins peuvent crÃ©er/modifier/supprimer des projets"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def mark_completed(self, request, pk=None):
        """
        Marquer un projet comme terminÃ© (Admin uniquement)
        """
        project = self.get_object()
        project.mark_as_completed()
        serializer = self.get_serializer(project)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def tasks(self, request, pk=None):
        """
        Obtenir toutes les tÃ¢ches d'un projet
        """
        project = self.get_object()
        tasks = project.tasks.select_related('user').all()
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def my_tasks(self, request, pk=None):
        """
        Obtenir MES tÃ¢ches dans ce projet
        """
        project = self.get_object()
        tasks = project.tasks.filter(user=request.user)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def with_tasks(self, request, pk=None):
        """
        Obtenir le projet avec toutes ses tÃ¢ches
        """
        project = self.get_object()
        serializer = ProjectWithTasksSerializer(project)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """
        Statistiques d'un projet
        """
        project = self.get_object()
        tasks = project.tasks.all()
        
        # Statistiques par utilisateur
        users_stats = []
        for user in project.get_assigned_users():
            user_tasks = tasks.filter(user=user)
            users_stats.append({
                'user': UserSimpleSerializer(user).data,
                'total_tasks': user_tasks.count(),
                'completed_tasks': user_tasks.filter(is_completed=True).count(),
                'pending_tasks': user_tasks.filter(is_completed=False).count(),
            })
        
        stats = {
            'project_title': project.title,
            'total_tasks': tasks.count(),
            'completed_tasks': tasks.filter(is_completed=True).count(),
            'pending_tasks': tasks.filter(is_completed=False).count(),
            'by_priority': {
                'high': tasks.filter(priority='high').count(),
                'medium': tasks.filter(priority='medium').count(),
                'low': tasks.filter(priority='low').count(),
            },
            'by_status': {
                'todo': tasks.filter(status='todo').count(),
                'in_progress': tasks.filter(status='in_progress').count(),
                'done': tasks.filter(status='done').count(),
            },
            'users_stats': users_stats
        }
        
        return Response(stats)


@extend_schema(tags=['Tasks'])
class TaskViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gÃ©rer les tÃ¢ches
    - Utilisateur normal : voit seulement SES tÃ¢ches
    - Admin : voit TOUTES les tÃ¢ches et peut les assigner Ã  n'importe qui
    """
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['priority', 'status', 'is_completed', 'project', 'user']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'due_date', 'priority']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Les utilisateurs normaux voient seulement leurs tÃ¢ches
        Les admins voient toutes les tÃ¢ches
        """
        user = self.request.user
        if user.is_admin or user.is_superuser:
            return Task.objects.select_related('user', 'project').all()
        return Task.objects.filter(user=user).select_related('project')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TaskCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TaskUpdateSerializer
        elif self.action == 'with_project_details':
            return TaskWithProjectSerializer
        return TaskSerializer
    
    def get_serializer_context(self):
        """Ajouter le request au context pour validation"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        """
        Associer automatiquement l'utilisateur connectÃ© Ã  la tÃ¢che
        SAUF si un admin spÃ©cifie un autre utilisateur
        """
        user = self.request.user
        
        # Si l'admin spÃ©cifie un user dans la requÃªte
        if user.is_admin or user.is_superuser:
            if 'user' in serializer.validated_data:
                task = serializer.save()  # Utilise le user spÃ©cifiÃ©
            else:
                task = serializer.save(user=user)  # Utilise l'admin lui-mÃªme
        else:
            # Utilisateur normal : toujours assignÃ© Ã  lui-mÃªme
            task = serializer.save(user=user)
        
        self._notify_assignment(task)
    
    def get_permissions(self):
        """
        Pour modifier/supprimer : soit propriÃ©taire, soit admin
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsOwnerOrAdmin()]
        return [IsAuthenticated()]
    
    def _notify_assignment(self, task):
        send_task_assignment_email(task)
    
    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        """
        Marquer une tÃ¢che comme terminÃ©e
        """
        task = self.get_object()
        task.mark_as_completed()
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_incomplete(self, request, pk=None):
        """
        Marquer une tÃ¢che comme non terminÃ©e
        """
        task = self.get_object()
        task.is_completed = False
        task.status = 'todo'
        task.completed_at = None
        task.save()
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def reassign(self, request, pk=None):
        """
        RÃ©assigner une tÃ¢che Ã  un autre utilisateur (Admin uniquement)
        """
        task = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({
                'error': 'user_id est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            new_user = User.objects.get(id=user_id)
            task.user = new_user
            task.save()
            return Response({
                'message': f'TÃ¢che rÃ©assignÃ©e Ã  {new_user.email}',
                'task': TaskSerializer(task).data
            })
        except User.DoesNotExist:
            return Response({
                'error': 'Utilisateur non trouvÃ©'
            }, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'])
    def my_tasks(self, request):
        """
        Obtenir toutes MES tÃ¢ches
        """
        tasks = Task.objects.filter(user=request.user)
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def without_project(self, request):
        """
        Obtenir mes tÃ¢ches sans projet
        """
        user = request.user
        if user.is_admin or user.is_superuser:
            tasks = Task.objects.filter(project__isnull=True)
        else:
            tasks = Task.objects.filter(user=user, project__isnull=True)
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def with_project_details(self, request):
        """
        Obtenir mes tÃ¢ches avec les dÃ©tails complets du projet
        """
        user = request.user
        if user.is_admin or user.is_superuser:
            tasks = Task.objects.select_related('project', 'user').all()
        else:
            tasks = Task.objects.filter(user=user).select_related('project')
        serializer = TaskWithProjectSerializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """
        Statistiques de MES tÃ¢ches
        """
        user = request.user
        tasks = Task.objects.filter(user=user)
        
        stats = {
            'total': tasks.count(),
            'completed': tasks.filter(is_completed=True).count(),
            'pending': tasks.filter(is_completed=False).count(),
            'with_project': tasks.filter(project__isnull=False).count(),
            'without_project': tasks.filter(project__isnull=True).count(),
            'by_priority': {
                'high': tasks.filter(priority='high').count(),
                'medium': tasks.filter(priority='medium').count(),
                'low': tasks.filter(priority='low').count(),
            },
            'by_status': {
                'todo': tasks.filter(status='todo').count(),
                'in_progress': tasks.filter(status='in_progress').count(),
                'done': tasks.filter(status='done').count(),
            }
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsAdminUser])
    def admin_dashboard(self, request):
        """
        Dashboard admin : statistiques de tous les utilisateurs et projets
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        users = User.objects.annotate(
            total_tasks=Count('tasks'),
            completed_tasks=Count('tasks', filter=Q(tasks__is_completed=True)),
            pending_tasks=Count('tasks', filter=Q(tasks__is_completed=False))
        ).values('id', 'email', 'username', 'total_tasks', 'completed_tasks', 'pending_tasks')
        
        total_stats = {
            'total_users': User.objects.count(),
            'total_projects': Project.objects.count(),
            'active_projects': Project.objects.filter(status='active').count(),
            'total_tasks': Task.objects.count(),
            'completed_tasks': Task.objects.filter(is_completed=True).count(),
            'pending_tasks': Task.objects.filter(is_completed=False).count(),
        }
        
        return Response({
            'overview': total_stats,
            'users': list(users)
        })

@extend_schema(tags=['Tasks'])
class ResourceViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gÃ©rer les ressources attachÃ©es aux tÃ¢ches
    """
    serializer_class = ResourceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """
        Admins voient toutes les ressources.
        Users voient seulement les ressources de leurs tÃ¢ches.
        """
        user = self.request.user
        if user.is_admin or user.is_superuser:
            return Resource.objects.all()
        return Resource.objects.filter(task__user=user)


@extend_schema(tags=['Clients'])
class ClientViewSet(viewsets.ModelViewSet):
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['client_type']
    search_fields = ['name', 'email', 'phone']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_queryset(self):
        return Client.objects.all()

from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Comment, Notification, SubTask, TaskDependency
from .serializers import CommentSerializer, NotificationSerializer, SubTaskSerializer, TaskDependencySerializer

@extend_schema(tags=['Tasks'])
class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin or user.is_superuser:
            return Comment.objects.all()
        # Only comments on tasks the user has access to
        return Comment.objects.filter(task__project__tasks__user=user).distinct()

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user)
        # Add a notification
        if comment.task.user != self.request.user:
            Notification.objects.create(
                recipient=comment.task.user,
                type='comment',
                message=f'{self.request.user.get_full_name() or self.request.user.username} a commente votre tache: {comment.task.title}',
                link=f'/admin/tasks/{comment.task.id}'
            )

@extend_schema(tags=['Notifications'])
class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.is_read = True
        notif.save()
        return Response({'status': 'ok'})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        self.get_queryset().update(is_read=True)
        return Response({'status': 'ok'})

@extend_schema(tags=['Tasks'])
class SubTaskViewSet(viewsets.ModelViewSet):
    serializer_class = SubTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin or user.is_superuser:
            return SubTask.objects.all()
        return SubTask.objects.filter(task__user=user)

    @action(detail=True, methods=['patch'])
    def toggle(self, request, pk=None):
        subtask = self.get_object()
        subtask.is_done = not subtask.is_done
        subtask.save()
        return Response(self.get_serializer(subtask).data)

@extend_schema(tags=['Tasks'])
class TaskDependencyViewSet(viewsets.ModelViewSet):
    serializer_class = TaskDependencySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin or user.is_superuser:
            return TaskDependency.objects.all()
        return TaskDependency.objects.filter(task__project__tasks__user=user).distinct()

@extend_schema(tags=['Search'])
class SearchAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        operation_id='search_list',
        description="Recherche globale projets + tâches",
        tags=['Search']
    )
    def get(self, request):
        query = request.query_params.get('q', '')
        user = request.user
        
        if not query:
            return Response({'projects': [], 'tasks': []})
            
        if user.is_admin or user.is_superuser:
            projects = Project.objects.filter(Q(title__icontains=query) | Q(description__icontains=query))
            tasks = Task.objects.filter(Q(title__icontains=query) | Q(description__icontains=query))
        else:
            projects = Project.objects.filter(tasks__user=user).filter(Q(title__icontains=query) | Q(description__icontains=query)).distinct()
            tasks = Task.objects.filter(user=user).filter(Q(title__icontains=query) | Q(description__icontains=query))
            
        from .serializers import ProjectSerializer, TaskSerializer
        return Response({
            'projects': ProjectSerializer(projects[:10], many=True).data,
            'tasks': TaskSerializer(tasks[:10], many=True).data
        })

