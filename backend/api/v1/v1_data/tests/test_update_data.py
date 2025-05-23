from django.core.management import call_command
from django.test import TestCase
from django.core import signing
from django.test.utils import override_settings

from api.v1.v1_forms.models import Forms
from api.v1.v1_forms.constants import FormAccessTypes
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser
from api.v1.v1_profile.constants import UserRoleTypes


@override_settings(USE_TZ=False)
class FormDataUpdateTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.maxDiff = None
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")
        self.adm = Administration.objects.filter(
            level__level=2
        ).order_by("?").first()
        self.form = Forms.objects.get(pk=1)

    def test_update_datapoint_by_superadmin(self):
        # Login as super admin
        user = {"email": "admin@rush.com", "password": "Test105*"}
        user = self.client.post('/api/v1/login',
                                user,
                                content_type='application/json')
        user = user.json()
        # Assign super admin role to the user
        su_user = SystemUser.objects.filter(
            email="admin@rush.com"
        ).first()
        su_user.user_access.role = UserRoleTypes.super_admin
        su_user.user_access.save()

        form = self.form
        self.assertEqual(form.id, 1)
        self.assertEqual(form.name, "Test Form")
        # Add data to edit
        payload = {
            "data": {
                "name": "Testing Data",
                "administration": self.adm.id,
                "geo": [6.2088, 106.8456]
            },
            "answer": [{
                "question": 101,
                "value": "Jane"
            }, {
                "question": 102,
                "value": ["Male"]
            }, {
                "question": 103,
                "value": 31208200175
            }, {
                "question": 104,
                "value": 2
            }, {
                "question": 105,
                "value": [6.2088, 106.8456]
            }, {
                "question": 106,
                "value": ["Parent", "Children"]
            }]
        }
        token = user.get("token")
        self.assertTrue(token)
        data = self.client.post('/api/v1/form-data/1/',
                                payload,
                                content_type='application/json',
                                **{'HTTP_AUTHORIZATION': f'Bearer {token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "ok"})
        # Get all data from form
        data = self.client.get('/api/v1/form-data/1?page=1',
                               content_type='application/json',
                               **{'HTTP_AUTHORIZATION': f'Bearer {token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(len(data['data']) > 0, True)
        data_id = data['data'][0]['id']  # get data_id here
        # Get answer from data
        data = self.client.get(f'/api/v1/data/{data_id}',
                               content_type='application/json',
                               **{'HTTP_AUTHORIZATION': f'Bearer {token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(len(data) > 0, True)
        for d in data:
            question = d.get('question')
            value = d.get('value')
            history = d.get('history')
            if question == 101:
                self.assertEqual(question, 101)
                self.assertEqual(value, 'Jane')
                self.assertEqual(history, None)
            if question == 102:
                self.assertEqual(question, 102)
                self.assertEqual(value, ['Male'])
                self.assertEqual(history, None)
        # Update data for question 101 and 102
        payload = [{
            "question": 101,
            "value": "Jane Doe"
        }, {
            "question": 102,
            "value": ["Female"]
        }]
        data = self.client.put(f'/api/v1/form-data/1?data_id={data_id}',
                               payload,
                               content_type='application/json',
                               **{'HTTP_AUTHORIZATION': f'Bearer {token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "direct update success"})
        # Get all data from form
        data = self.client.get('/api/v1/form-data/1?page=1',
                               content_type='application/json',
                               **{'HTTP_AUTHORIZATION': f'Bearer {token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(len(data['data']) > 0, True)
        self.assertEqual(data['data'][0]['name'], 'Testing Data')
        # Get answer from data with history
        data = self.client.get(f'/api/v1/data/{data_id}',
                               content_type='application/json',
                               **{'HTTP_AUTHORIZATION': f'Bearer {token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(len(data) > 0, True)
        for d in data:
            question = d.get('question')
            value = d.get('value')
            history = d.get('history')
            if question == 101:
                self.assertEqual(question, 101)
                self.assertEqual(value, 'Jane Doe')
                self.assertEqual(list(history[0]), [
                    'value', 'created', 'created_by'])
                self.assertEqual(history[0]['value'], 'Jane')
                self.assertEqual(history[0]['created_by'], 'Admin RUSH')
            if question == 102:
                self.assertEqual(question, 102)
                self.assertEqual(value, ['Female'])
                self.assertEqual(list(history[0]), [
                    'value', 'created', 'created_by'])
                self.assertEqual(history[0]['value'], ['Male'])
                self.assertEqual(history[0]['created_by'], 'Admin RUSH')

    def test_update_datapoint_by_editor_access(self):
        form = self.form
        self.assertEqual(form.id, 1)
        self.assertEqual(form.name, "Test Form")

        user = {"email": "admin@rush.com", "password": "Test105*"}
        user = self.client.post('/api/v1/login',
                                user,
                                content_type='application/json')
        user = user.json()
        token = user.get('token')
        self.assertTrue(token)
        # Add data to edit
        payload = {
            "data": {
                "name": "Testing Data #2",
                "administration": self.adm.id,
                "geo": [6.2088, 106.8456]
            },
            "answer": [{
                "question": 101,
                "value": "Wayan"
            }, {
                "question": 102,
                "value": ["Female"]
            }, {
                "question": 103,
                "value": 31208200175
            }, {
                "question": 104,
                "value": 2
            }, {
                "question": 105,
                "value": [6.2088, 106.8456]
            }, {
                "question": 106,
                "value": ["Parent", "Children"]
            }]
        }
        data = self.client.post('/api/v1/form-data/1/',
                                payload,
                                content_type='application/json',
                                **{'HTTP_AUTHORIZATION': f'Bearer {token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "ok"})
        # create a new user
        payload = {
            "first_name": "User",
            "last_name": "Wayan",
            "email": "wayan@example.com",
            "administration": self.adm.id,
            "access_forms": [
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.read
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.edit
                }
            ],
            "role": UserRoleTypes.admin
        }
        header = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        res = self.client.post("/api/v1/user",
                               payload,
                               content_type='application/json',
                               **header)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'message': 'User added successfully'})
        new_user = SystemUser.objects.filter(
            email="wayan@example.com").first()
        # check invitation
        invite_payload = signing.dumps(new_user.pk)
        invite_response = self.client.get(
            '/api/v1/invitation/{0}'.format(invite_payload),
            content_type='application/json')
        self.assertEqual(invite_response.status_code, 200)
        self.assertEqual(invite_response.json(), {'name': "User Wayan"})
        # set password
        password_payload = {
            'invite': invite_payload,
            'password': 'Test123*',
            'confirm_password': 'Test123*'
        }
        invite_response = self.client.put('/api/v1/user/set-password',
                                          password_payload,
                                          content_type='application/json')
        self.assertEqual(invite_response.status_code, 200)

        call_command("demo_approval_flow", "--test", True)

        # data entry user login
        new_user_user = {
            "email": "wayan@example.com",
            "password": "Test123*"
        }
        new_user_user = self.client.post(
            '/api/v1/login',
            new_user_user,
            content_type='application/json',
        )
        new_user_user = new_user_user.json()
        new_user_user_token = new_user_user.get('token')
        self.assertTrue(new_user_user_token)
        # get profile
        header = {'HTTP_AUTHORIZATION': f'Bearer {new_user_user_token}'}
        response = self.client.get("/api/v1/profile",
                                   content_type='application/json',
                                   **header)
        self.assertEqual(response.status_code, 200)
        response = response.json()
        self.assertEqual(response['email'], 'wayan@example.com')
        self.assertEqual(response['role']['id'], UserRoleTypes.admin)
        # Get all data from form
        data = self.client.get('/api/v1/form-data/1?page=1',
                               content_type='application/json',
                               **{'HTTP_AUTHORIZATION':
                                   f'Bearer {new_user_user_token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(len(data['data']) > 0, True)
        data_id = data['data'][0]['id']  # get data_id here
        # Get answer from data
        data = self.client.get(f'/api/v1/data/{data_id}',
                               content_type='application/json',
                               **{'HTTP_AUTHORIZATION':
                                   f'Bearer {new_user_user_token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(len(data) > 0, True)
        for d in data:
            question = d.get('question')
            value = d.get('value')
            history = d.get('history')
            if question == 101:
                self.assertEqual(question, 101)
                self.assertEqual(value, 'Wayan')
                self.assertEqual(history, None)
            if question == 102:
                self.assertEqual(question, 102)
                self.assertEqual(value, ['Female'])
                self.assertEqual(history, None)
        # Update data for question 101 and 102
        payload = [{
            "question": 101,
            "value": "User Wayan"
        }, {
            "question": 102,
            "value": ["Male"]
        }]
        data = self.client.put(f'/api/v1/form-data/1?data_id={data_id}',
                               payload,
                               content_type='application/json',
                               **{'HTTP_AUTHORIZATION':
                                   f'Bearer {new_user_user_token}'})
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "direct update success"})

    def test_update_datapoint_by_reader_access(self):
        user = {
            "email": "admin@rush.com",
            "password": "Test105*"
        }
        user = self.client.post(
            "/api/v1/login",
            user,
            content_type="application/json"
        )
        user = user.json()
        token = user.get("token")
        self.assertTrue(token)
        # Add data to edit
        payload = {
            "data": {
                "name": "Testing Data #3",
                "administration": self.adm.id,
                "geo": [6.2088, 106.8456]
            },
            "answer": [{
                "question": 101,
                "value": "John"
            }, {
                "question": 102,
                "value": ["Male"]
            }, {
                "question": 103,
                "value": 31208200175
            }, {
                "question": 104,
                "value": 1
            }, {
                "question": 105,
                "value": [6.2088, 106.8456]
            }, {
                "question": 106,
                "value": ["Parent"]
            }]
        }
        data = self.client.post(
            "/api/v1/form-data/1/",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"}
        )
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "ok"})
        # create a new user
        email = "user.reader@test.com"
        payload = {
            "first_name": "User",
            "last_name": "Reader",
            "email": email,
            "administration": self.adm.id,
            "access_forms": [
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.read
                },
            ],
            "role": UserRoleTypes.admin
        }
        header = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        res = self.client.post(
            "/api/v1/user",
            payload,
            content_type="application/json",
            **header
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"message": "User added successfully"})
        new_user = SystemUser.objects.filter(
            email=email).first()
        # check invitation
        invite_payload = signing.dumps(new_user.pk)
        invite_response = self.client.get(
            "/api/v1/invitation/{0}".format(invite_payload),
            content_type="application/json")
        self.assertEqual(invite_response.status_code, 200)
        self.assertEqual(
            invite_response.json(),
            {"name": "User Reader"}
        )
        # set password
        password_payload = {
            "invite": invite_payload,
            "password": "Test123*",
            "confirm_password": "Test123*"
        }
        invite_response = self.client.put(
            "/api/v1/user/set-password",
            password_payload,
            content_type="application/json"
        )
        self.assertEqual(invite_response.status_code, 200)

        # Login as reader user
        reader_user = {
            "email": "user.reader@test.com",
            "password": "Test123*"
        }
        reader_user = self.client.post(
            "/api/v1/login",
            reader_user,
            content_type="application/json"
        )
        reader_user = reader_user.json()
        reader_user_token = reader_user.get("token")
        self.assertTrue(reader_user_token)

        # Get all data from form
        data = self.client.get(
            '/api/v1/form-data/1?page=1',
            content_type='application/json',
            **{'HTTP_AUTHORIZATION': f'Bearer {reader_user_token}'}
        )
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(len(data['data']) > 0, True)
        data_id = data['data'][0]['id']  # get data_id here
        # Update data for question 101 and 104
        payload = [{
            "question": 101,
            "value": "User Reader"
        }, {
            "question": 104,
            "value": 999999
        }]
        data = self.client.put(
            f"/api/v1/form-data/1?data_id={data_id}",
            payload,
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {reader_user_token}"}
        )
        self.assertEqual(data.status_code, 403)
        data = data.json()
        self.assertEqual(data, {
            "detail": "You do not have permission to perform this action."
        })
