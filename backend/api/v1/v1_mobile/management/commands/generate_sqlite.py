from django.core.management import BaseCommand
from utils.custom_generator import generate_sqlite
from api.v1.v1_profile.models import Administration, Entity, EntityData
from api.v1.v1_users.models import Organisation


class Command(BaseCommand):
    # Add test arguments
    def add_arguments(self, parser):
        parser.add_argument(
            "-t", "--test", nargs="?", const=False, default=False, type=bool
        )

    def handle(self, *args, **options):
        test = options.get("test", False)
        file = generate_sqlite(Administration, test=test)
        if not test:
            self.log_generated(file, Administration)
        file = generate_sqlite(Organisation, test=test)
        if not test:
            self.log_generated(file, Organisation)
        file = generate_sqlite(Entity, test=test)
        if not test:
            self.log_generated(file, Entity)
        file = generate_sqlite(EntityData, test=test)
        if not test:
            self.log_generated(file, EntityData)

    def log_generated(self, file, model):
        message = (
            f"{file} Generated Successfully"
            if file
            else (
                f"Failed to generate {model._meta.db_table}, "
                "possibly empty data"
            )
        )
        print(message)
