from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class Client(models.Model):
    CLIENT_TYPE_CHOICES = [
        ('company', 'Entreprise'),
        ('individual', 'Particulier'),
    ]
    
    name = models.CharField(max_length=200)
    client_type = models.CharField(max_length=20, choices=CLIENT_TYPE_CHOICES, default='individual')
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.get_client_type_display()})"

class ProjectAssignment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey('Project', on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'assignation_project'
        unique_together = ('user', 'project')

class Project(models.Model):
    """
    Modèle Project - GLOBAL (pas assigné à un utilisateur)
    Un projet peut contenir plusieurs tâches assignées à différents utilisateurs
    """
    STATUS_CHOICES = [
        ('active', 'Actif'),
        ('completed', 'Terminé'),
        ('archived', 'Archivé'),
        ('on_hold', 'En pause'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_date = models.DateTimeField(blank=True, null=True)
    end_date = models.DateTimeField(blank=True, null=True)
    color = models.CharField(max_length=7, default='#3b82f6', help_text="Couleur au format hexadécimal")
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='projects')
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, through='ProjectAssignment', related_name='assigned_projects', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status'], name='projects_project_status_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                name='project_period_consistency',
                check=(
                    models.Q(start_date__isnull=True) |
                    models.Q(end_date__isnull=True) |
                    models.Q(end_date__gte=models.F('start_date'))
                ),
                violation_error_message="La date de fin doit être postérieure à la date de début."
            )
        ]
    
    def __str__(self):
        return self.title
    
    def mark_as_completed(self):
        from django.utils import timezone
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def get_tasks_count(self):
        return self.tasks.count()
    
    def get_completed_tasks_count(self):
        return self.tasks.filter(is_completed=True).count()
    
    def get_assigned_users(self):
        """Retourne la liste des utilisateurs explicitement assignés à ce projet"""
        return self.users.all()
    
    def is_within_schedule(self, date):
        """Vérifie si une date donnée se trouve dans la période du projet."""
        if not date:
            return False
        if not (self.start_date or self.end_date):
            return True
        if self.start_date and date < self.start_date:
            return False
        if self.end_date and date > self.end_date:
            return False
        return True


class Task(models.Model):
    """
    Modèle Task - Assignée à un utilisateur dans un projet
    """
    PRIORITY_CHOICES = [
        ('low', 'Basse'),
        ('medium', 'Moyenne'),
        ('high', 'Haute'),
    ]
    
    STATUS_CHOICES = [
        ('todo', 'À faire'),
        ('in_progress', 'En cours'),
        ('done', 'Terminée'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    start_date = models.DateTimeField(blank=True, null=True)
    due_date = models.DateTimeField(blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tasks')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks', blank=True, null=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='projects_task_user_status_idx'),
            models.Index(fields=['project'], name='projects_task_project_idx'),
            models.Index(fields=['priority'], name='projects_task_priority_idx'),
            models.Index(fields=['due_date'], name='projects_task_due_date_idx'),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.email}"
    
    def mark_as_completed(self):
        from django.utils import timezone
        self.is_completed = True
        self.status = 'done'
        self.completed_at = timezone.now()
        self.save()

    def clean(self):
        super().clean()
        self._validate_project_period()

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def _validate_project_period(self):
        if not self.project:
            return
        if not (self.project.start_date or self.project.end_date):
            return
        if not self.due_date:
            raise ValidationError({'due_date': "Une tâche assignée à un projet planifié doit avoir une date d'échéance."})
        if not self.project.is_within_schedule(self.due_date):
            raise ValidationError({'due_date': "La date d'échéance de la tâche doit être comprise dans la période du projet."})
        if self.start_date and self.due_date and self.due_date < self.start_date:
            raise ValidationError({'due_date': "La date de fin ne peut pas être antérieure à la date de début."})

class Resource(models.Model):
    """
    Modèle Resource - Ressource attachée à une tâche (fichier, image ou lien)
    """
    RESOURCE_TYPES = [
        ('file', 'Fichier'),
        ('image', 'Image'),
        ('link', 'Lien Web'),
    ]
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='resources')
    name = models.CharField(max_length=255)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES, default='file')
    file = models.FileField(upload_to='resources/%Y/%m/%d/', blank=True, null=True)
    link_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_resource_type_display()})"
    
    def clean(self):
        super().clean()
        if self.resource_type in ['file', 'image'] and not self.file:
            raise ValidationError({'file': "Un fichier est requis pour ce type de ressource."})
        if self.resource_type == 'link' and not self.link_url:
            raise ValidationError({'link_url': "Une URL est requise pour ce type de ressource."})

class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author} on {self.task}"

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('comment', 'Nouveau commentaire'),
        ('assignment', 'Nouvelle assignation'),
        ('deadline', 'Échéance proche'),
        ('system', 'Système'),
    ]
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='system')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient}: {self.message}"

class SubTask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='subtasks')
    title = models.CharField(max_length=255)
    is_done = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.title} ({'Done' if self.is_done else 'Todo'})"

class TaskDependency(models.Model):
    DEPENDENCY_TYPES = [
        ('finish_to_start', 'Finish to Start'),
        ('start_to_start', 'Start to Start'),
    ]
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='dependencies')
    depends_on = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='dependents')
    dependency_type = models.CharField(max_length=20, choices=DEPENDENCY_TYPES, default='finish_to_start')

    class Meta:
        unique_together = ('task', 'depends_on')

    def __str__(self):
        return f"{self.task} depends on {self.depends_on} ({self.get_dependency_type_display()})"
    
    def clean(self):
        super().clean()
        if self.task == self.depends_on:
            raise ValidationError("Une tâche ne peut pas dépendre d'elle-même.")