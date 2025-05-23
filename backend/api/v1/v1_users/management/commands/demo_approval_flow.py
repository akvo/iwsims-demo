import re
import random
from faker import Faker
from django.core.management import BaseCommand
from api.v1.v1_profile.constants import UserRoleTypes
from api.v1.v1_profile.models import Administration, Access, Levels
from api.v1.v1_users.models import SystemUser, Organisation
from api.v1.v1_forms.models import (
    Forms, UserForms, FormAccess, FormApprovalAssignment
)
from api.v1.v1_forms.constants import FormAccessTypes
from api.v1.v1_mobile.models import MobileAssignment
fake = Faker()


def create_approver(form, administration, organisation):
    email = ("{0}.{1}@test.com").format(
        re.sub('[^A-Za-z0-9]+', '', administration.name.lower()),
        random.randint(10, 100)
    )
    last_name = "Approver"
    role = UserRoleTypes.admin  # Default to admin role
    if administration.level.level == 1:
        last_name = "Admin"
    # check if someone has access to ancestor adminisration
    approver, created = SystemUser.objects.get_or_create(
        email=email,
    )
    if created:
        approver.set_password("test")
        approver.organisation = organisation
        approver.first_name = administration.name
        approver.last_name = last_name
        approver.phone_number = fake.msisdn()
        approver.save()
        Access.objects.create(
            user=approver,
            role=role,
            administration=administration
        )
    # Create UserForms with approver access type
    user_form, _ = UserForms.objects.get_or_create(form=form, user=approver)
    # Ensure the user has approver access for this form
    FormAccess.objects.get_or_create(
        user_form=user_form,
        access_type=FormAccessTypes.approve
    )
    # Create form approval assignment
    assignment = FormApprovalAssignment.objects.create(
        form=form,
        administration=administration,
        user=approver
    )
    return assignment


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "-t", "--test", nargs="?", const=False, default=False, type=bool
        )

    def handle(self, *args, **options):
        test = options.get("test")
        forms = Forms.objects.filter(parent__isnull=True).all()
        for form in forms:
            last_level = Levels.objects.order_by('-level')[1:2].first()
            administrations = Administration.objects.filter(
                level=last_level
            )
            administrations = administrations.all()
            for administration in administrations:
                ancestors = administration.ancestors.filter(
                    level__level__gt=0
                )
                ancestors |= Administration.objects.filter(
                    id=administration.id
                )
                organisation = Organisation.objects.order_by('?').first()
                for ancestor in ancestors:
                    assignment = FormApprovalAssignment.objects \
                        .filter(
                            form=form,
                            administration=ancestor
                        ).first()
                    last_name = "Approver"
                    if ancestor.level.level == 1:
                        last_name = "Admin"
                    if not assignment:
                        assignment = create_approver(
                            form=form,
                            administration=ancestor,
                            organisation=organisation,
                        )
                    if not test:
                        print("Level: {} ({})".format(
                            ancestor.level.level,
                            ancestor.level.name
                        ))  # pragma: no cover
                        print(
                            f"- Administration Name: {ancestor.name}"
                        )  # pragma: no cover
                        print("- Approver: {} ({})".format(
                            assignment.user.email,
                            last_name
                        ))  # pragma: no cover
                # create user
                email = "{0}.{1}@test.com".format(
                    re.sub(
                        '[^A-Za-z0-9]+', '', administration.name.lower()
                    ),
                    random.randint(200, 300)
                )
                submitter, created = SystemUser.objects.get_or_create(
                    email=email,
                )
                if created:
                    submitter.set_password("test")
                    submitter.organisation = organisation
                    submitter.first_name = administration.name
                    submitter.last_name = "User"
                    submitter.phone_number = fake.msisdn()
                    submitter.save()
                    Access.objects.create(
                        user=submitter,
                        role=UserRoleTypes.admin,
                        administration=ancestor
                    )
                user_form, _ = UserForms.objects.get_or_create(
                    form=form,
                    user=submitter
                )
                FormAccess.objects.get_or_create(
                    user_form=user_form,
                    access_type=FormAccessTypes.read
                )
                mobile_assignment = MobileAssignment.objects.create_assignment(
                    user=submitter,
                    name=fake.user_name(),
                )
                mobile_adms = administration.parent_administration\
                    .order_by('?')[:2]
                mobile_assignment.administrations.add(
                    *mobile_adms
                )
                mobile_assignment.forms.add(form)
