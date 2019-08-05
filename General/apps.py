from django.apps import AppConfig
from ScalaApp import scala_settings


class GeneralConfig(AppConfig):
    name = 'General'


def scala_settings_in_template(request):
    # return the value you want as a dictionnary. you may add multiple values in there.
    return {'settings': scala_settings}