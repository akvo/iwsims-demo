from datetime import datetime, timedelta, time

import pandas as pd
from django.core.management import BaseCommand
from django.utils.timezone import make_aware

from faker import Faker

from iwsims.settings import COUNTRY_NAME
from api.v1.v1_data.models import FormData
from api.v1.v1_forms.models import Forms, UserForms, FormApprovalAssignment
from api.v1.v1_profile.constants import UserRoleTypes
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser
from api.v1.v1_mobile.models import MobileAssignment
from api.v1.v1_users.management.commands.fake_user_seeder import create_user
from api.v1.v1_data.functions import add_fake_answers

fake = Faker()


def get_mobile_user(user, form):
    mobile_user = user.mobile_assignments.filter(
        forms__id__in=[form.pk]
    ).first()
    if not mobile_user:
        mobile_user = MobileAssignment.objects.create_assignment(
            user=user, name=fake.user_name()
        )
        mobile_user.forms.add(form)
        user_path = "{0}{1}".format(
            user.user_access.administration.path,
            user.user_access.administration.id
        )
        mobile_adms = form.form_form_data.filter(
            administration__path__startswith=user_path
        ).values_list("administration", flat=True)
        if len(mobile_adms) == 0:
            mobile_adms = user.user_access \
                .administration \
                .parent_administration.order_by('?')[:6]
        mobile_user.administrations.set(mobile_adms)
    return mobile_user


def seed_data(
    form,
    fake_geo,
    created,
    administration,
    repeat
):
    for i in range(repeat):
        geo = fake_geo.iloc[i].to_dict()
        geo_value = [geo["X"], geo["Y"]]
        assignment = FormApprovalAssignment.objects.filter(
            form=form,
            administration=administration,
        ).first()
        if assignment:
            user = SystemUser.objects.filter(
                user_form__form_id__in=[form.pk],
                user_access__administration=administration,
                user_access__role=UserRoleTypes.admin
            ).order_by('?').first()
            if not user:
                user = create_user(
                    role=UserRoleTypes.admin,
                    administration=administration,
                    random_password=False,
                )
                UserForms.objects.get_or_create(
                    form=form, user=user
                )
            mobile_user = get_mobile_user(
                user=user, form=form
            )
            created_by = mobile_user.user
            adm_submission = mobile_user.administrations.order_by('?').first()
            data = FormData.objects.create(
                name=fake.pystr_format(),
                geo=geo_value,
                form=form,
                administration=adm_submission,
                created_by=created_by,
            )
            data.created = make_aware(created)
            data.save()
            add_fake_answers(data)
            data.save_to_file


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "-r", "--repeat", nargs="?", const=5, default=5, type=int
        )
        parser.add_argument(
            "-t", "--test", nargs="?", const=False, default=False, type=bool
        )

    def handle(self, *args, **options):
        test = options.get("test")
        repeat = options.get("repeat")
        FormData.objects.all().delete()
        fake_geo = pd.read_csv(
            f"./source/{COUNTRY_NAME}_random_points.csv"
        )
        fake_geo = fake_geo.sample(frac=1).reset_index(drop=True)
        now_date = datetime.now()
        start_date = now_date - timedelta(days=5 * 365)
        created = fake.date_between(start_date, now_date)
        created = datetime.combine(created, time.min)
        level1_admins = (
            Administration.objects.filter(level__level=1)
            .distinct("name")
            .all()
        )
        for level1_admin in level1_admins:
            level1_admin_user = SystemUser.objects.filter(
                user_access__administration=level1_admin
            ).order_by('?').first()
            if not level1_admin_user:
                create_user(
                    role=UserRoleTypes.admin,
                    administration=level1_admin,
                    random_password=False
                )
        for form in Forms.objects.filter(parent__isnull=True).all():
            if not test:
                print(f"Seeding - {form.name}")
            administrations = [
                level3_admin
                for level1_admin in level1_admins
                for level2_admin in level1_admin.parent_administration.all()
                for level3_admin in level2_admin.parent_administration.all()
            ]
            for adm in administrations:
                seed_data(
                    form=form,
                    fake_geo=fake_geo,
                    created=created,
                    administration=adm,
                    repeat=repeat
                )
