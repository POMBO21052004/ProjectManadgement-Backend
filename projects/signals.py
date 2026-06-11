from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import Task


@receiver(post_save, sender=Task)
def send_task_assignment_email(sender, instance, created, **kwargs):
    """
    Envoie un email stylisé lorsqu'une nouvelle tâche est assignée.
    """
    if not created:
        return

    user = instance.user
    if not user or not user.email:
        return

    subject = f"Nouvelle tâche assignée : {instance.title}"
    context = {
        'user': user,
        'task': instance,
        'project': instance.project,
    }
    html_message = render_to_string('emails/task_assignment_email.html', context)
    plain_message = strip_tags(html_message)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER)

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=from_email,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=True,
    )

