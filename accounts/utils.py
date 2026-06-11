from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import OTP


def send_otp_email(user):
    """
    Génère et envoie un code OTP par email
    """
    # Générer le code OTP
    otp_code = OTP.generate_code()
    
    # Créer l'objet OTP dans la base de données
    otp = OTP.objects.create(user=user, code=otp_code)
    
    subject = 'Code de vérification - TodoApp'
    context = {
        'user': user,
        'otp_code': otp_code,
        'otp_expiry': settings.OTP_EXPIRY_MINUTES,
    }
    html_message = render_to_string('emails/otp_email.html', context)
    plain_message = strip_tags(html_message)
    
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@todoapp.com')
    recipient_list = [user.email]
    
    send_mail(
        subject,
        plain_message,
        from_email,
        recipient_list,
        html_message=html_message,
        fail_silently=False
    )
    
    return otp_code


def send_credentials_email(user, raw_password: str | None = None):
    """
    Envoie un email avec les identifiants de connexion (email + éventuellement mot de passe).
    ATTENTION : l'envoi du mot de passe en clair n'est pas recommandé en production.
    """
    subject = "Vos identifiants de connexion - TodoApp"
    context = {
        "user": user,
        "email": user.email,
        "raw_password": raw_password,
    }
    html_message = render_to_string("emails/user_credentials_email.html", context)
    plain_message = strip_tags(html_message)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@todoapp.com")

    send_mail(
        subject,
        plain_message,
        from_email,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )