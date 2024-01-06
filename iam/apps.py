from distutils.util import strtobool
import os
from django.apps import AppConfig

from .utils import create_opa_bundle

class IAMConfig(AppConfig):
    name = 'iam'

    def ready(self):
        from .signals import register_signals
        from .signals import password_reset_token_created
        register_signals(self)

        if strtobool(os.environ.get("IAM_OPA_BUNDLE", '0')):
            create_opa_bundle()
