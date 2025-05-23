from django.core.management import call_command
from django.test import TestCase

from django.test.utils import override_settings
from api.v1.v1_profile.constants import UserRoleTypes
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser, Organisation
from api.v1.v1_forms.models import Forms
from api.v1.v1_forms.constants import FormAccessTypes


@override_settings(USE_TZ=False)
class AddNewUserTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("fake_organisation_seeder")
        call_command("form_seeder", "--test")
        user_payload = {"email": "admin@rush.com", "password": "Test105*"}
        user_response = self.client.post('/api/v1/login',
                                         user_payload,
                                         content_type='application/json')
        user = user_response.json()
        self.token = user.get('token')
        self.header = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}
        self.org = Organisation.objects.order_by('?').first()

    def test_add_superadmin_user(self):
        payload = {
            "first_name": "Super",
            "last_name": "Admin",
            "email": "super.admin1@mail.com",
            "organisation": self.org.id,
            "role": UserRoleTypes.super_admin,
            "access_forms": [],
            "trained": True,
        }
        add_response = self.client.post(
            "/api/v1/user",
            payload,
            content_type='application/json',
            **self.header
        )
        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(
            add_response.json(),
            {'message': 'User added successfully'}
        )
        user = SystemUser.objects.filter(
            email="super.admin1@mail.com"
        ).first()
        self.assertEqual(user.user_access.role, UserRoleTypes.super_admin)
        # Check UserFomrAccess
        user_forms = user.user_form.all()
        self.assertEqual(
            len(user_forms),
            Forms.objects.filter(parent__isnull=True).count()
        )
        user_form = user_forms.first()
        self.assertEqual(
            user_form.user_form_access.count(),
            2  # read and edit
        )

    def test_add_admin_with_national_level_access(self):
        national_adm = Administration.objects.filter(
            level__level=0
        ).first()
        payload = {
            "first_name": "Admin",
            "last_name": "National",
            "email": "admin.national@test.com",
            "administration": national_adm.id,
            "organisation": self.org.id,
            "role": UserRoleTypes.admin,
            "access_forms": [
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.read
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.edit
                },
            ],
            "trained": True,
        }
        add_response = self.client.post(
            "/api/v1/user",
            payload,
            content_type='application/json',
            **self.header
        )
        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(
            add_response.json(),
            {'message': 'User added successfully'}
        )
