from django.urls import path
from . import views

urlpatterns = [
    path('generate-subtasks/', views.GenerateSubtasksView.as_view(), name='ai-generate-subtasks'),
    path('project-summary/<int:project_id>/', views.GenerateProjectSummaryView.as_view(), name='ai-project-summary'),
    path('suggest-assignment/', views.SuggestAssignmentView.as_view(), name='ai-suggest-assignment'),
    path('chat/', views.ChatView.as_view(), name='ai-chat'),
]
