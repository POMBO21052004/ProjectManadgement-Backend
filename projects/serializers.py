from rest_framework import serializers
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import Task, Project, Resource, Comment, Notification, SubTask, TaskDependency, Client

User = get_user_model()


def validate_project_period(start_date, end_date):
    if start_date and end_date and end_date < start_date:
        raise serializers.ValidationError(
            "La date de fin doit être postérieure ou égale à la date de début."
        )


def ensure_task_within_project(attrs, instance=None):
    project = attrs.get('project')
    due_date = attrs.get('due_date')

    if instance:
        project = project if project is not None else instance.project
        due_date = due_date if due_date is not None else instance.due_date

    if not project:
        return attrs

    # Si le projet a une période définie, forcer la présence d'une date d'échéance
    if (project.start_date or project.end_date) and not due_date:
        raise serializers.ValidationError(
            "Une date d'échéance est obligatoire lorsque la tâche est assignée à un projet planifié."
        )

    if due_date:
        if project.start_date and due_date < project.start_date:
            raise serializers.ValidationError(
                "La date d'échéance doit être postérieure ou égale à la date de début du projet."
            )
        if project.end_date and due_date > project.end_date:
            raise serializers.ValidationError(
                "La date d'échéance doit être antérieure ou égale à la date de fin du projet."
            )

    return attrs


class DueDateValidationMixin:
    def validate_due_date(self, value):
        if value and value < timezone.now():
            raise serializers.ValidationError("La date d'échéance ne peut pas être dans le passé.")
        return value

class ProjectSerializer(serializers.ModelSerializer):
    tasks_count = serializers.SerializerMethodField()
    completed_tasks_count = serializers.SerializerMethodField()
    assigned_users = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'title', 'description', 'status',
            'start_date', 'end_date', 'color', 'client', 'client_name',
            'tasks_count', 'completed_tasks_count', 'assigned_users',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = ['completed_at', 'created_at', 'updated_at']
    
    def get_tasks_count(self, obj):
        return obj.get_tasks_count()
    
    def get_completed_tasks_count(self, obj):
        return obj.get_completed_tasks_count()
    
    def get_assigned_users(self, obj):
        users = obj.get_assigned_users()
        return [{'id': user.id, 'email': user.email, 'username': user.username} for user in users]

    def get_client_name(self, obj):
        return obj.client.name if obj.client else None


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['title', 'description', 'status', 'start_date', 'end_date', 'color', 'client', 'users']
    
    def validate(self, attrs):
        validate_project_period(attrs.get('start_date'), attrs.get('end_date'))
        return attrs


class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['title', 'description', 'status', 'start_date', 'end_date', 'color', 'client', 'users']
    
    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        validate_project_period(start_date, end_date)
        return attrs


class UserSimpleSerializer(serializers.ModelSerializer):
    """Serializer simple pour afficher les infos utilisateur"""
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name']

class ClientSerializer(serializers.ModelSerializer):
    client_type_display = serializers.CharField(source='get_client_type_display', read_only=True)
    projects_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Client
        fields = ['id', 'name', 'client_type', 'client_type_display', 'email', 'phone', 'address', 'projects_count', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_projects_count(self, obj):
        return obj.projects.count()


class ResourceSerializer(serializers.ModelSerializer):
    resource_type_display = serializers.CharField(source='get_resource_type_display', read_only=True)

    class Meta:
        model = Resource
        fields = ['id', 'task', 'name', 'resource_type', 'resource_type_display', 'file', 'link_url', 'created_at']
        read_only_fields = ['created_at']

class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    author_email = serializers.EmailField(source='author.email', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'task', 'author', 'author_name', 'author_email', 'content', 'created_at']
        read_only_fields = ['author', 'created_at']

    def get_author_name(self, obj):
        return f"{obj.author.first_name} {obj.author.last_name}".strip() or obj.author.username

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'recipient', 'type', 'message', 'is_read', 'link', 'created_at']
        read_only_fields = ['recipient', 'created_at']

class SubTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubTask
        fields = ['id', 'task', 'title', 'is_done', 'order', 'created_at']
        read_only_fields = ['created_at']

class TaskDependencySerializer(serializers.ModelSerializer):
    dependency_type_display = serializers.CharField(source='get_dependency_type_display', read_only=True)
    depends_on_title = serializers.CharField(source='depends_on.title', read_only=True)

    class Meta:
        model = TaskDependency
        fields = ['id', 'task', 'depends_on', 'depends_on_title', 'dependency_type', 'dependency_type_display']

class TaskSerializer(DueDateValidationMixin, serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.SerializerMethodField()
    project_title = serializers.CharField(source='project.title', read_only=True)
    assigned_to = UserSimpleSerializer(source='user', read_only=True)
    resources = ResourceSerializer(many=True, read_only=True)
    subtasks = SubTaskSerializer(many=True, read_only=True)
    dependencies = TaskDependencySerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'priority', 'status', 
            'start_date', 'due_date', 'user', 'user_email', 'user_name', 'assigned_to',
            'project', 'project_title', 'resources', 'subtasks', 'dependencies', 'comments',
            'is_completed', 'completed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['completed_at', 'created_at', 'updated_at']
    
    def get_user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username


class TaskCreateSerializer(DueDateValidationMixin, serializers.ModelSerializer):
    """Serializer pour créer une tâche - user peut être spécifié par l'admin"""
    class Meta:
        model = Task
        fields = ['title', 'description', 'priority', 'status', 'start_date', 'due_date', 'project', 'user']
        extra_kwargs = {
            'user': {'required': False}  # Optionnel, sera automatique si non fourni
        }
    
    def validate(self, attrs):
        attrs = super().validate(attrs)
        return ensure_task_within_project(attrs)


class TaskUpdateSerializer(DueDateValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['title', 'description', 'priority', 'status', 'start_date', 'due_date', 'project', 'user', 'is_completed']
    
    def validate(self, attrs):
        attrs = super().validate(attrs)
        return ensure_task_within_project(attrs, instance=self.instance)


class TaskWithProjectSerializer(serializers.ModelSerializer):
    """Serializer avec détails complets du projet"""
    project_details = ProjectSerializer(source='project', read_only=True)
    assigned_to = UserSimpleSerializer(source='user', read_only=True)
    resources = ResourceSerializer(many=True, read_only=True)
    subtasks = SubTaskSerializer(many=True, read_only=True)
    dependencies = TaskDependencySerializer(many=True, read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'priority', 'status', 
            'start_date', 'due_date', 'user', 'assigned_to',
            'project', 'project_details', 'resources', 'subtasks', 'dependencies', 'comments',
            'is_completed', 'completed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['completed_at', 'created_at', 'updated_at']


class ProjectWithTasksSerializer(serializers.ModelSerializer):
    """Serializer avec toutes les tâches du projet"""
    tasks = TaskSerializer(many=True, read_only=True)
    tasks_count = serializers.SerializerMethodField()
    completed_tasks_count = serializers.SerializerMethodField()
    client_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'title', 'description', 'status',
            'start_date', 'end_date', 'color', 'client', 'client_name',
            'tasks', 'tasks_count', 'completed_tasks_count',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = ['completed_at', 'created_at', 'updated_at']
    
    def get_tasks_count(self, obj):
        return obj.get_tasks_count()
    
    def get_completed_tasks_count(self, obj):
        return obj.get_completed_tasks_count()
        
    def get_client_name(self, obj):
        return obj.client.name if obj.client else None