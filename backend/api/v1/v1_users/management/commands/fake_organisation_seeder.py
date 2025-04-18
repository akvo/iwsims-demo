from django.core.management import BaseCommand
from faker import Faker

from api.v1.v1_profile.constants import OrganisationTypes
from api.v1.v1_users.models import Organisation, OrganisationAttribute

fake = Faker()


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("-r",
                            "--repeat",
                            nargs="?",
                            const=1,
                            default=1,
                            type=int)

    def handle(self, *args, **options):
        for r in range(options.get("repeat")):
            organisation, _ = Organisation.objects.update_or_create(
                name=fake.company() if r != 0 else "Akvo",
            )
            org_types = [
                OrganisationTypes.member, OrganisationTypes.partnership
            ]
            for org_type in org_types:
                OrganisationAttribute.objects.update_or_create(
                    organisation=organisation,
                    type=org_type
                )
