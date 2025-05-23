import json

from django.core.management import BaseCommand
from jsmin import jsmin

from iwsims.settings import COUNTRY_NAME
from api.v1.v1_forms.models import Forms
from api.v1.v1_profile.models import Levels
from api.v1.v1_forms.serializers import FormDataSerializer


class Command(BaseCommand):
    def handle(self, *args, **options):
        print("GENERATING CONFIG JS")
        topojson = open(f"source/{COUNTRY_NAME}.topojson").read()

        # write config
        config_file = jsmin(open("source/config/config.js").read())
        levels = []
        forms = []
        for level in Levels.objects.all():
            levels.append(
                {
                    "id": level.id,
                    "name": level.name,
                    "level": level.level,
                }
            )
        for form in Forms.objects.filter(parent__isnull=True).all():
            forms.append(
                {
                    "id": form.id,
                    "name": form.name,
                    "version": form.version,
                    "content": FormDataSerializer(instance=form).data,
                }
            )
        min_config = jsmin(
            "".join(
                [
                    "var topojson=",
                    topojson,
                    ";",
                    "var levels=",
                    json.dumps(levels),
                    ";",
                    "var forms=",
                    json.dumps(forms),
                    ";",
                    config_file,
                ]
            )
        )
        open("source/config/config.min.js", "w").write(min_config)
        # os.remove(administration_json)
        del levels
        del forms
        del min_config
