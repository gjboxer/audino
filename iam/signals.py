from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.signals import post_save, post_migrate
from users.models import User
from django.core.mail import EmailMultiAlternatives
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.urls import reverse

from django_rest_passwordreset.signals import reset_password_token_created

@receiver(reset_password_token_created)
def password_reset_token_created(sender, instance, reset_password_token, *args, **kwargs):
    """
    Handles password reset tokens
    When a token is created, an e-mail needs to be sent to the user
    :param sender: View Class that sent the signal
    :param instance: View Instance that sent the signal
    :param reset_password_token: Token Model Object
    :param args:
    :param kwargs:
    :return:
    """
    # send an e-mail to the user
    context = {
        'current_user': reset_password_token.user,
        'username': reset_password_token.user.username,
        'email': reset_password_token.user.email,
        'reset_password_url': "{}?token={}".format(
            instance.request.build_absolute_uri(reverse('password_reset:reset-password-confirm')),
            reset_password_token.key)
    }

    # render email text
    email_html_message = render_to_string('email/password_reset_email.html', context)
    email_plaintext_message = render_to_string('email/password_reset_email.txt', context)

    msg = EmailMultiAlternatives(
        # title:
        "Password Reset for {title}".format(title="Audino"),
        # message:
        email_plaintext_message,
        # from:
        "noreply@audino.com",
        # to:
        [reset_password_token.user.email]
    )
    msg.attach_alternative(email_html_message, "text/html")
    msg.send()

def register_groups(sender, **kwargs):
    # Create all groups which corresponds system roles
    for role in settings.IAM_ROLES:
        Group.objects.get_or_create(name=role)

if settings.IAM_TYPE == 'BASIC':
    def create_user(sender, instance, created, **kwargs):
        # from allauth.account import app_settings as allauth_settings
        # from allauth.account.models import EmailAddress

        if instance.is_superuser and instance.is_staff:
            db_group = Group.objects.get(name=settings.IAM_ADMIN_ROLE)
            instance.groups.add(db_group)

            # # create and verify EmailAddress for superuser accounts
            # if allauth_settings.EMAIL_REQUIRED:
            #     EmailAddress.objects.get_or_create(user=instance,
            #         email=instance.email, primary=True, verified=True)
        else: # don't need to add default groups for superuser
            if created:
                for role in settings.GET_IAM_DEFAULT_ROLES(instance):
                    db_group = Group.objects.get(name=role)
                    instance.groups.add(db_group)

elif settings.IAM_TYPE == 'LDAP':
    def create_user(sender, user=None, ldap_user=None, **kwargs):
        user_groups = []
        for role in settings.IAM_ROLES:
            db_group = Group.objects.get(name=role)

            for ldap_group in settings.DJANGO_AUTH_LDAP_GROUPS[role]:
                if ldap_group.lower() in ldap_user.group_dns:
                    user_groups.append(db_group)
                    if role == settings.IAM_ADMIN_ROLE:
                        user.is_staff = user.is_superuser = True
                    break

        user.save()
        user.groups.set(user_groups)


def register_signals(app_config):
    post_migrate.connect(register_groups, app_config)
    if settings.IAM_TYPE == 'BASIC':
        # Add default groups and add admin rights to super users.
        post_save.connect(create_user, sender=User)
    elif settings.IAM_TYPE == 'LDAP':
        import django_auth_ldap.backend
        # Map groups from LDAP to roles, convert a user to super user if he/she
        # has an admin group.
        django_auth_ldap.backend.populate_user.connect(create_user)
