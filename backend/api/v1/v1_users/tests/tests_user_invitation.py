from django.core import signing
from django.core.management import call_command
from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from django.test.utils import override_settings
from api.v1.v1_profile.constants import UserRoleTypes
from api.v1.v1_profile.models import Administration
from api.v1.v1_users.models import SystemUser, Organisation
from api.v1.v1_forms.models import FormApprovalAssignment
from api.v1.v1_forms.constants import FormAccessTypes
from utils.email_helper import EmailTypes


@override_settings(USE_TZ=False)
class UserInvitationTestCase(TestCase):
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

    def test_user_list(self):
        adm = Administration.objects.filter(level__level=0).first()
        response = self.client.get(
            f"/api/v1/users?administration={adm.id}&role=1",
            follow=True,
            **self.header
        )
        users = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(users['data'][0]['first_name'], 'Admin')
        self.assertEqual(users['data'][0]['last_name'], 'RUSH')
        self.assertEqual(users['data'][0]['email'], 'admin@rush.com')
        self.assertEqual(users['data'][0]['administration'], {
            'id': adm.id,
            'name': adm.name,
            'level': 0,
            'full_name': adm.full_name,
        })
        self.assertEqual(users['data'][0]['role'], {
            'id': 1,
            'value': 'Super Admin'
        })
        call_command("fake_user_seeder", "-r", 25, "--test", True)
        response = self.client.get(
            "/api/v1/users?page=1",
            follow=True,
            **self.header
        )
        users = response.json()
        self.assertEqual([
            'id',
            'first_name',
            'last_name',
            'email',
            'administration',
            'organisation',
            'trained',
            'role',
            'phone_number',
            'invite',
            'forms',
            'last_login'
        ], list(users['data'][0]))
        response = self.client.get("/api/v1/users?pending=true",
                                   follow=True,
                                   **self.header)

        self.assertGreater(len(response.json().get('data')), 0)
        self.assertEqual(response.status_code, 200)
        # test trained filter
        response = self.client.get("/api/v1/users?trained=true",
                                   follow=True,
                                   **self.header)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json().get('data')), 0)
        # search by fullname
        response = self.client.get("/api/v1/users?search=admin rush",
                                   follow=True,
                                   **self.header)
        users = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(users['data'][0]['email'], 'admin@rush.com')
        self.assertEqual(users['data'][0]['first_name'], 'Admin')
        self.assertEqual(users['data'][0]['last_name'], 'RUSH')
        # search by email
        response = self.client.get("/api/v1/users?search=admin@rush",
                                   follow=True,
                                   **self.header)
        users = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(users['data'][0]['email'], 'admin@rush.com')
        self.assertEqual(users['data'][0]['first_name'], 'Admin')
        self.assertEqual(users['data'][0]['last_name'], 'RUSH')

        find_user = SystemUser.objects.filter(
            user_access__role=UserRoleTypes.admin).first()
        token = RefreshToken.for_user(find_user)
        response = self.client.get(
            "/api/v1/users?page=1&administration={}".format(
                find_user.user_access.administration_id),
            follow=True,
            **{'HTTP_AUTHORIZATION': f'Bearer {token.access_token}'})
        users = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(users),
                         ['current', 'data', 'total', 'total_page'])

    def test_add_edit_user(self):
        adm1, adm2 = Administration.objects.filter(level__level=1)[:2]
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "administration": adm1.id,
            "organisation": self.org.id,
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
            "trained": True,
            "inform_user": True,
        }
        add_response = self.client.post("/api/v1/user",
                                        payload,
                                        content_type='application/json',
                                        **self.header)
        self.assertEqual(add_response.status_code, 400)
        payload["role"] = UserRoleTypes.admin
        add_response = self.client.post("/api/v1/user",
                                        payload,
                                        content_type='application/json',
                                        **self.header)

        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(add_response.json(),
                         {'message': 'User added successfully'})

        edit_payload = {
            "first_name": "Joe",
            "last_name": "Doe",
            "email": "john@example.com",
            "administration": adm1.id,
            "organisation": self.org.id,
            "trained": False,
            "role": 6,
            "access_forms": [
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.read
                },
                {
                    "form_id": 2,
                    "access_type": FormAccessTypes.read
                }
            ],
            "inform_user": True,
        }
        list_response = self.client.get("/api/v1/users?pending=true",
                                        follow=True,
                                        **self.header)
        users = list_response.json()
        fl = list(
            filter(lambda x: x['email'] == 'john@example.com', users['data']))

        add_response = self.client.put("/api/v1/user/{0}".format(fl[0]['id']),
                                       edit_payload,
                                       content_type='application/json',
                                       **self.header)
        self.assertEqual(add_response.status_code, 400)
        edit_payload["role"] = UserRoleTypes.admin
        add_response = self.client.put("/api/v1/user/{0}".format(fl[0]['id']),
                                       edit_payload,
                                       content_type='application/json',
                                       **self.header)
        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(add_response.json(),
                         {'message': 'User updated successfully'})
        edit_payload["role"] = UserRoleTypes.admin
        edit_payload["access_forms"] = [
            {
                "form_id": 2,
                "access_type": FormAccessTypes.read
            }
        ]
        add_response = self.client.put("/api/v1/user/{0}".format(fl[0]['id']),
                                       edit_payload,
                                       content_type='application/json',
                                       **self.header)
        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(add_response.json(),
                         {'message': 'User updated successfully'})
        # change administration
        edit_payload["administration"] = adm2.id
        add_response = self.client.put("/api/v1/user/{0}".format(fl[0]['id']),
                                       edit_payload,
                                       content_type='application/json',
                                       **self.header)
        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(add_response.json(),
                         {'message': 'User updated successfully'})

        get_response = self.client.get("/api/v1/user/{0}".format(fl[0]['id']),
                                       content_type='application/json',
                                       **self.header)
        self.assertEqual(get_response.status_code, 200)
        responses = get_response.json()
        self.assertEqual([
            'first_name', 'last_name', 'email', 'administration',
            'organisation', 'trained', 'role', 'phone_number',
            'forms', 'approval_assignment', 'pending_approval', 'data',
            'pending_batch'
        ], list(responses))
        self.assertEqual(
            responses["forms"],
            [
                {
                    "id": 2,
                    "name": "Test Form 2",
                    "access": [
                        {
                            "label": "Read",
                            "value": FormAccessTypes.read,
                        }
                    ]
                }
            ]
        )
        edit_payload["access_forms"] = [
            {
                "form_id": 1,
                "access_type": FormAccessTypes.read
            },
            {
                "form_id": 2,
                "access_type": FormAccessTypes.read
            }
        ]
        add_response = self.client.put("/api/v1/user/{0}".format(fl[0]['id']),
                                       edit_payload,
                                       content_type='application/json',
                                       **self.header)
        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(add_response.json(),
                         {'message': 'User updated successfully'})
        get_response = self.client.get("/api/v1/user/{0}".format(fl[0]['id']),
                                       content_type='application/json',
                                       **self.header)
        self.assertEqual(get_response.status_code, 200)
        responses = get_response.json()
        self.assertEqual([
            'first_name', 'last_name', 'email', 'administration',
            'organisation', 'trained', 'role', 'phone_number',
            'forms', 'approval_assignment', 'pending_approval', 'data',
            'pending_batch'
        ], list(responses))
        self.assertEqual(
            responses["forms"],
            [
                {
                    "id": 1,
                    "name": "Test Form",
                    "access": [
                        {
                            "label": "Read",
                            "value": FormAccessTypes.read,
                        }
                    ]
                },
                {
                    "id": 2,
                    "name": "Test Form 2",
                    "access": [
                        {
                            "label": "Read",
                            "value": FormAccessTypes.read,
                        }
                    ]
                }
            ]
        )

        # test_update_user_with_pending_approval
        call_command("fake_pending_data_seeder", "--test")
        find_user = SystemUser.objects.filter(
            user_access__role=UserRoleTypes.admin).order_by('-id').first()
        edit_payload = {
            "first_name": find_user.first_name,
            "last_name": find_user.last_name,
            "email": find_user.email,
            "administration": find_user.user_access.administration_id + 1,
            "organisation": self.org.id,
            "trained": False,
            "role": find_user.user_access.role,
            "access_forms": [
                {
                    "form_id": form.id,
                    "access_type": FormAccessTypes.read
                } for form in find_user.user_form.all()
            ],
            "inform_user": True,
        }
        response = self.client.put("/api/v1/user/{0}".format(find_user.id),
                                   edit_payload,
                                   content_type='application/json',
                                   **self.header)
        self.assertEqual(response.status_code, 400)

    def test_add_admin_user(self):
        adm1, adm2 = Administration.objects.filter(level__level=1)[:2]
        payload = {
            "first_name": "User",
            "last_name": "Admin",
            "email": "admin@example.com",
            "administration": adm1.id,
            "organisation": self.org.id,
            "role": 2,
            "access_forms": [
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.read
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.edit
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.approve
                }
            ],
            "trained": False,
        }
        add_response = self.client.post("/api/v1/user",
                                        payload,
                                        content_type='application/json',
                                        **self.header)
        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(add_response.json(),
                         {'message': 'User added successfully'})
        user = SystemUser.objects.filter(
            email="admin@example.com").first()
        form_approval_assignment = FormApprovalAssignment.objects.filter(
            form=1, administration=adm1.id, user=user).first()
        self.assertEqual(form_approval_assignment.user, user)
        # Add user for same form and administration
        payload = {
            "first_name": "Second User",
            "last_name": "Admin",
            "email": "admin2@example.com",
            "administration": adm1.id,
            "organisation": self.org.id,
            "role": 2,
            "access_forms": [
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.read
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.edit
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.approve
                }
            ],
            "trained": False,
        }
        add_response = self.client.post("/api/v1/user",
                                        payload,
                                        content_type='application/json',
                                        **self.header)
        self.assertEqual(add_response.status_code, 403)
        # Add user for different administration
        payload = {
            "first_name": "Third User",
            "last_name": "Admin",
            "email": "admin3@example.com",
            "administration": adm2.id,
            "organisation": self.org.id,
            "role": 2,
            "access_forms": [
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.read
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.edit
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.approve
                }
            ],
            "trained": False,
        }
        add_response = self.client.post("/api/v1/user",
                                        payload,
                                        content_type='application/json',
                                        **self.header)
        self.assertEqual(add_response.status_code, 200)

    def test_add_aprroval_user(self):
        adm1, adm2 = Administration.objects.filter(level__level=1)[:2]
        payload = {
            "first_name": "Test",
            "last_name": "Approver",
            "email": "test_approver@example.com",
            "administration": adm1.id,
            "organisation": self.org.id,
            "role": UserRoleTypes.admin,
            "access_forms": [
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.read
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.approve
                }
            ],
            "trained": True,
        }
        add_response = self.client.post("/api/v1/user",
                                        payload,
                                        content_type='application/json',
                                        **self.header)
        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(add_response.json(),
                         {'message': 'User added successfully'})
        user = SystemUser.objects.filter(
            email="test_approver@example.com").first()
        form_approval_assignment = FormApprovalAssignment.objects.filter(
            form=1, administration=adm1.id, user=user).first()
        self.assertEqual(form_approval_assignment.user, user)
        # Add user for same form and administration
        payload = {
            "first_name": "Test Second",
            "last_name": "Approver",
            "email": "test2_approver@example.com",
            "administration": adm1.id,
            "organisation": self.org.id,
            "role": UserRoleTypes.admin,
            "access_forms": [
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.read
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.approve
                }
            ],
            "trained": True,
        }
        add_response = self.client.post("/api/v1/user",
                                        payload,
                                        content_type='application/json',
                                        **self.header)
        self.assertEqual(add_response.status_code, 403)
        # Add user for different administration
        payload = {
            "first_name": "Test Third",
            "last_name": "Approver",
            "email": "test3_approver@example.com",
            "administration": adm2.id,
            "organisation": self.org.id,
            "role": UserRoleTypes.admin,
            "access_forms": [
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.read
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.approve
                }
            ],
            "trained": True,
        }
        add_response = self.client.post("/api/v1/user",
                                        payload,
                                        content_type='application/json',
                                        **self.header)
        self.assertEqual(add_response.status_code, 200)
        # Add another role with same form and administration
        payload = {
            "first_name": "Data",
            "last_name": "Entry",
            "email": "data_entry@example.com",
            "administration": adm2.id,
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
                }
            ],
            "trained": True,
        }
        add_response = self.client.post("/api/v1/user",
                                        payload,
                                        content_type='application/json',
                                        **self.header)
        self.assertEqual(add_response.status_code, 200)
        # Add national super admin approver
        payload = {
            "first_name": "National Approver",
            "last_name": "Entry",
            "email": "national_approver@example.com",
            "organisation": self.org.id,
            "role": UserRoleTypes.super_admin,
            "access_forms": [
                {
                    "form_id": 1
                }
            ],
            "trained": True,
        }
        add_response = self.client.post("/api/v1/user",
                                        payload,
                                        content_type='application/json',
                                        **self.header)
        self.assertEqual(add_response.status_code, 400)
        self.assertEqual(
            add_response.json(),
            {"message": "access_type is required."}
        )
        payload["access_forms"] = [
            {
                "form_id": 2,
                "access_type": FormAccessTypes.read
            },
            {
                "form_id": 2,
                "access_type": FormAccessTypes.approve
            }
        ]
        add_response = self.client.post("/api/v1/user",
                                        payload,
                                        content_type='application/json',
                                        **self.header)
        self.assertEqual(add_response.status_code, 200)

    def test_get_user_profile(self):
        response = self.client.get("/api/v1/profile",
                                   content_type='application/json',
                                   **self.header)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([
            'email', 'name', 'administration', 'trained',
            'role', 'phone_number', 'forms',
            'organisation', 'last_login', 'passcode',
        ], list(response.json().keys()))

    def test_get_user_roles(self):
        response = self.client.get(
            "/api/v1/user/roles",
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(UserRoleTypes.FieldStr.items()),
            len(response.json())
        )
        self.assertEqual(['id', 'value'], list(response.json()[0].keys()))

    def test_verify_invite(self):
        user = SystemUser.objects.first()
        invite_payload = 'dummy-token'
        invite_response = self.client.get(
            '/api/v1/invitation/{0}'.format(invite_payload),
            content_type='application/json')
        self.assertEqual(invite_response.status_code, 400)

        invite_payload = signing.dumps(user.pk)
        invite_response = self.client.get(
            '/api/v1/invitation/{0}'.format(invite_payload),
            content_type='application/json')
        self.assertEqual(invite_response.json(), {'name': "Admin RUSH"})
        self.assertEqual(invite_response.status_code, 200)

    def test_set_user_password(self):
        user_payload = {"email": "admin@rush.com", "password": "Test105*"}
        self.client.post('/api/v1/login',
                         user_payload,
                         content_type='application/json')
        user = SystemUser.objects.first()
        password_payload = {
            'invite': 'dummy-token',
            'password': 'Test105*',
            'confirm_password': 'Test105*'
        }
        invite_response = self.client.put('/api/v1/user/set-password',
                                          password_payload,
                                          content_type='application/json')
        self.assertEqual(invite_response.status_code, 400)
        password_payload = {
            'invite': signing.dumps(user.pk),
            'password': 'Test105*',
            'confirm_password': 'Test105*'
        }
        invite_response = self.client.put('/api/v1/user/set-password',
                                          password_payload,
                                          content_type='application/json')
        self.assertEqual(invite_response.status_code, 200)

    def test_get_email_template(self):
        # test get user_register template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.user_register))
        self.assertEqual(response.status_code, 200)
        # test get user_approval template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.user_approval))
        self.assertEqual(response.status_code, 200)
        # test get user_forgot_password template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.user_forgot_password))
        self.assertEqual(response.status_code, 200)
        # test get user_invite template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.user_invite))
        self.assertEqual(response.status_code, 200)
        # test get data_approval template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.data_approval))
        self.assertEqual(response.status_code, 200)
        # test get data_rejection template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.data_rejection))
        self.assertEqual(response.status_code, 200)
        # test get batch_approval template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.batch_approval))
        self.assertEqual(response.status_code, 200)
        # test get batch_rejection template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.batch_rejection))
        self.assertEqual(response.status_code, 200)
        # test get inform_batch_rejection_to_approval template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.inform_batch_rejection_approver))
        self.assertEqual(response.status_code, 200)
        # test get pending_approval template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.pending_approval))
        self.assertEqual(response.status_code, 200)
        # test get upload_error template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.upload_error))
        self.assertEqual(response.status_code, 200)
        # test get new_request template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.new_request))
        self.assertEqual(response.status_code, 200)
        # test get unchanged_data template
        response = self.client.get('/api/v1/email_template?type={0}'.format(
            EmailTypes.unchanged_data))
        self.assertEqual(response.status_code, 200)
        # not send type
        response = self.client.get('/api/v1/email_template')
        self.assertEqual(response.status_code, 400)
        # test invalid type
        response = self.client.get('/api/v1/email_template?type=registration')
        self.assertEqual(response.status_code, 400)

    def test_delete_user(self):
        call_command("administration_seeder", "--test")
        user_payload = {"email": "admin@rush.com", "password": "Test105*"}
        user_response = self.client.post('/api/v1/login',
                                         user_payload,
                                         content_type='application/json')
        user = user_response.json()
        token = user.get('token')
        header = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        call_command("fake_user_seeder", "--test", True)
        call_command("demo_approval_flow", "--test", True)
        u = SystemUser.objects.filter(
            user_access__role=UserRoleTypes.admin,
            password__isnull=False
        ).first()
        response = self.client.delete('/api/v1/user/{0}'.format(u.id),
                                      content_type='application/json',
                                      **header)
        self.assertEqual(response.status_code, 204)
        user = SystemUser.objects_deleted.get(pk=u.id)
        self.assertEqual(user.deleted_at is not None, True)
        # test login with deleted user
        deleted_user = {"email": user.email, "password": "test"}
        response = self.client.post('/api/v1/login',
                                    deleted_user,
                                    content_type='application/json')
        self.assertEqual(response.status_code, 401)
        # get deleted user
        response = self.client.get('/api/v1/user/{0}'.format(u.id),
                                   content_type='application/json',
                                   **header)
        self.assertEqual(response.status_code, 404)

    def test_re_adding_user(self):
        call_command("fake_organisation_seeder", "--repeat", 3)
        user_payload = {"email": "admin@rush.com", "password": "Test105*"}
        user_response = self.client.post('/api/v1/login',
                                         user_payload,
                                         content_type='application/json')
        user = user_response.json()
        token = user.get('token')
        header = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        call_command("fake_user_seeder", "--test", True)
        u = SystemUser.objects.filter(
            user_access__role__in=[
                UserRoleTypes.admin,
                UserRoleTypes.admin
            ],
            password__isnull=False).first()
        adm_id = u.user_access.administration_id
        # delete the user first
        response = self.client.delete('/api/v1/user/{0}'.format(u.id),
                                      content_type='application/json',
                                      **header)
        self.assertEqual(response.status_code, 204)
        user = SystemUser.objects_deleted.get(pk=u.id)
        self.assertEqual(user.deleted_at is not None, True)

        header = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        # re adding the deleted user
        org = Organisation.objects.order_by('?').last()
        payload = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "organisation": org.id,
            "role": UserRoleTypes.admin,
            "access_forms": [
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.read
                },
                {
                    "form_id": 1,
                    "access_type": FormAccessTypes.approve
                }
            ],
            "administration": adm_id,
            "trained": True,
        }
        add_response = self.client.post(
            "/api/v1/user",
            payload,
            content_type='application/json',
            **header
        )
        self.assertEqual(add_response.status_code, 200)
        self.assertEqual(
            add_response.json(),
            {'message': 'User added successfully'}
        )
        form_approval_assignment = FormApprovalAssignment.objects.filter(
            form=1, administration=adm_id, user=user).first()
        self.assertEqual(form_approval_assignment.user, user)
