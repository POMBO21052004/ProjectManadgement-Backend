from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet, basename='project')
router.register(r'tasks', views.TaskViewSet, basename='task')
router.register(r'resources', views.ResourceViewSet, basename='resource')
router.register(r'clients', views.ClientViewSet, basename='client')
router.register(r'comments', views.CommentViewSet, basename='comment')
router.register(r'notifications', views.NotificationViewSet, basename='notification')
router.register(r'subtasks', views.SubTaskViewSet, basename='subtask')
router.register(r'task-dependencies', views.TaskDependencyViewSet, basename='taskdependency')

urlpatterns = [
    path('management/', include(router.urls)),
    path('management/search/', views.SearchAPIView.as_view(), name='search'),
]
