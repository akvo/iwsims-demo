import random
import re
import uuid

from django.core.management import BaseCommand
from faker import Faker

from api.v1.v1_profile.constants import UserRoleTypes
from api.v1.v1_profile.constants import OrganisationTypes
from api.v1.v1_profile.models import Levels, Access, Administration
from api.v1.v1_users.models import SystemUser, Organisation
from api.v1.v1_forms.models import Forms, UserForms, FormAccess
from api.v1.v1_forms.constants import FormAccessTypes
from api.v1.v1_users.functions import (
    check_form_approval_assigned,
    assign_form_approval,
)

fake = Faker()

DEFAULT_PASSWORD = "Test#123"


def create_user(
    administration: Administration,
    is_superadmin: bool = False,
    test: bool = False
) -> SystemUser:
    first_name = fake.first_name()
    last_name = fake.last_name()
    email = (
        "{}.{}@test.com").format(
        re.sub("[^A-Za-z0-9]+", "", first_name.lower()),
        str(uuid.uuid4())[:4]
    )
    organisation = Organisation.objects.filter(
        organisation_organisation_attribute=OrganisationTypes.member
    ).order_by("?").first()
    user = SystemUser.objects.create(
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone_number=fake.msisdn(),
    )
    if organisation:
        user.organisation = organisation
    if test:
        password = random.choice(["test", None])
        if password:
            user.set_password(password)
    if not test:
        user.set_password(DEFAULT_PASSWORD)
    user.save()
    role = UserRoleTypes.super_admin if is_superadmin else UserRoleTypes.admin
    Access.objects.create(
        user=user,
        role=role,
        administration=administration
    )
    if is_superadmin:
        forms = Forms.objects.filter(parent__isnull=True).all()
        for form in forms:
            user_form, _ = UserForms.objects.get_or_create(
                user=user,
                form=form
            )
            FormAccess.objects.get_or_create(
                user_form=user_form,
                access_type=FormAccessTypes.edit
            )
            if random.choice([True, False]):
                FormAccess.objects.get_or_create(
                    user_form=user_form,
                    access_type=FormAccessTypes.approve
                )
    if not is_superadmin:
        form = (
            Forms.objects
            .filter(parent__isnull=True)
            .order_by("?")
            .first()
        )
        user_form, _ = UserForms.objects.get_or_create(
            user=user,
            form=form
        )
        if random.choice([True, False]):
            FormAccess.objects.get_or_create(
                user_form=user_form,
                access_type=FormAccessTypes.read
            )
        else:
            FormAccess.objects.get_or_create(
                user_form=user_form,
                access_type=FormAccessTypes.edit
            )
            is_approver = random.choice([True, False])
            if is_approver:
                is_approver_assigned = check_form_approval_assigned(
                    role=UserRoleTypes.admin,
                    administration=administration,
                    access_forms=[{
                        "form_id": form
                    }],
                )
                # Check if the user already has approver access
                if not is_approver_assigned:
                    # Assign approver access to the user
                    FormAccess.objects.get_or_create(
                        user_form=user_form,
                        access_type=FormAccessTypes.approve
                    )
                    assign_form_approval(
                        role=UserRoleTypes.admin,
                        forms=[form],
                        administration=administration,
                        user=user,
                        access_forms=[{
                            "form_id": form,
                            "access_type": FormAccessTypes.approve
                        }],
                    )
    return user


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "-r",
            "--repeat",
            nargs="?",
            const=1,
            default=5,
            type=int
        )
        parser.add_argument(
            "-t",
            "--test",
            nargs="?",
            const=False,
            default=False,
            type=bool
        )

    def handle(self, *args, **options):
        repeat = options.get("repeat")
        test = options.get("test")
        level = 0
        total_levels = Levels.objects.count() - 1
        for _ in range(repeat):
            if level > total_levels:
                level = 0
            is_superadmin = level == 0
            # Get administrations with entity data
            administration = Administration.objects.filter(
                level__level=level
            ).exclude(
                entity_data=None
            ).order_by("?").first()

            # Fall back to any administration if none with entity data exists
            if not administration:
                administration = Administration.objects.filter(
                    level__level=level,
                ).order_by("?").first()

            level += 1
            create_user(
                administration=administration,
                is_superadmin=is_superadmin,
                test=test
            )
        if not test:
            self.stdout.write(
                self.style.SUCCESS(
                    "Successfully created {} users".format(repeat)
                )
            )
