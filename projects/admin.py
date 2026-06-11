from django.contrib import admin
from .models import Project, Task, Client, ProjectAssignment

@admin.register(ProjectAssignment)
class ProjectAssignmentAdmin(admin.ModelAdmin):
    list_display  = ['user', 'project', 'assigned_at']
    list_filter   = ['project', 'assigned_at']
    search_fields = ['user__email', 'user__username', 'project__title']
    raw_id_fields = ['user', 'project']


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'client_type', 'email', 'phone', 'created_at']
    list_filter = ['client_type', 'created_at']
    search_fields = ['name', 'email', 'phone']


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'client', 'status', 'get_tasks_count', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at', 'completed_at', 'get_tasks_count', 'get_completed_tasks_count']
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('title', 'client', 'description', 'status')
        }),
        ('Statistiques', {
            'fields': ('get_tasks_count', 'get_completed_tasks_count')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at', 'completed_at')
        }),
    )
    
    def get_tasks_count(self, obj):
        return obj.get_tasks_count()
    get_tasks_count.short_description = 'Nombre de tâches'
    
    def get_completed_tasks_count(self, obj):
        return obj.get_completed_tasks_count()
    get_completed_tasks_count.short_description = 'Tâches terminées'

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'project', 'priority', 'status', 'is_completed', 'due_date', 'created_at']
    list_filter = ['priority', 'status', 'is_completed', 'project', 'created_at']
    search_fields = ['title', 'description', 'user__email', 'project__title']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('title', 'description', 'user', 'project')
        }),
        ('Configuration', {
            'fields': ('priority', 'status', 'due_date', 'is_completed')
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at', 'completed_at')
        }),
    )