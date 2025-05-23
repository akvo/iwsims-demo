from django.core.management import BaseCommand
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.constants import UserRoleTypes
from api.v1.v1_profile.models import Access, Administration, Levels
from api.v1.v1_forms.models import Forms, FormAccessTypes


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("email", nargs="+", type=str)
        parser.add_argument(
            "-t", "--test", nargs="?", const=1, default=False, type=int
        )
        parser.add_argument(
            "-a", "--admin", nargs="?", const=1, default=False, type=int
        )

    def handle(self, *args, **options):
        email = options.get("email")
        user = SystemUser.objects.filter(email=email[0]).first()
        if not user:
            self.stdout.write("User doesn't exist")
            exit()
        if not user.is_superuser:
            self.stdout.write("User is not super admin")
            exit()
        administration = Administration.objects.filter(
            parent__isnull=True
        ).first()
        role = UserRoleTypes.super_admin
        if options.get("admin"):
            administration = (
                Administration.objects.filter(
                    level=Levels.objects.filter(level=1).first()
                )
                .order_by("?")
                .first()
            )
            role = UserRoleTypes.admin
        access = Access.objects.filter(user=user).first()
        if not access:
            Access.objects.create(
                user=user, role=role, administration=administration
            )
        else:
            access.administration = administration
            access.save()
        if role == UserRoleTypes.super_admin:
            # Create all forms for super admin
            # and give access to all forms
            forms = Forms.objects.filter(parent__isnull=True).all()
            for form in forms:
                user_form = user.user_form.create(
                    form=form
                )
                # Create access for super admin
                user_form.user_form_access.create(
                    access_type=FormAccessTypes.edit,
                )
            user.save()
        if not options.get("test"):
            self.stdout.write(
                f"{user.email} now has access to {administration.name}"
            )
