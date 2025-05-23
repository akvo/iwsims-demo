from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from api.v1.v1_data.models import FormData, Forms, Answers, AnswerHistory
from api.v1.v1_forms.constants import FormAccessTypes
from api.v1.v1_profile.models import (
    UserRoleTypes,
    Access,
    SystemUser,
    Administration,
)


@override_settings(USE_TZ=False)
class DataTestCase(TestCase):
    def setUp(self):
        call_command("administration_seeder", "--test")
        call_command("form_seeder", "--test")

        user_payload = {"email": "admin@rush.com", "password": "Test105*"}
        user_response = self.client.post(
            "/api/v1/login", user_payload, content_type="application/json"
        )
        self.token = user_response.json().get("token")

        call_command("demo_approval_flow", "--test", True)
        call_command("fake_data_seeder", "-r", 1, "-t", True)
        call_command(
            "fake_data_monitoring_seeder", "-r", 5, "-t", True, "-a", True
        )
        self.form = (
            Forms.objects
            .filter(
                form_form_data__gt=0,
                pk=1,
            )
            .order_by("?").first()
        )

    def test_list_form_data(self):
        form = self.form

        user = SystemUser.objects.create_user(
            email="test@test.org",
            password="test1234",
            first_name="test",
            last_name="testing",
        )
        administration = Administration.objects.filter(level__level=1).first()
        role = UserRoleTypes.admin
        Access.objects.create(
            user=user, role=role, administration=administration
        )
        # Assign form access to user with read access
        user_form = user.user_form.create(
            form=form,
        )
        user_form.user_form_access.create(
            access_type=FormAccessTypes.read,
        )
        user_form.save()

        user_payload = {"email": "test@test.org", "password": "test1234"}

        user_response = self.client.post(
            "/api/v1/login", user_payload, content_type="application/json"
        )
        token = user_response.json().get("token")
        header = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        data = self.client.get(
            f"/api/v1/form-data/{form.id}?page=1",
            content_type="application/json",
            **header,
        )
        result = data.json()
        self.assertEqual(data.status_code, 200)
        self.assertEqual(
            list(result), ["current", "total", "total_page", "data"]
        )
        self.assertEqual(
            list(result["data"][0]),
            [
                "id",
                "uuid",
                "name",
                "form",
                "administration",
                "geo",
                "created_by",
                "updated_by",
                "created",
                "updated",
                "pending_data",
            ],
        )
        self.assertIsNotNone(result["data"][0]["uuid"])

        # PUBLIC ACCESS WITHOUT HEADER TOKEN
        data = self.client.get(
            f"/api/v1/form-data/{form.id}?page=1",
            content_type="application/json",
        )
        self.assertEqual(data.status_code, 401)

        # # EMPTY PAGE 2
        data = self.client.get(
            f"/api/v1/form-data/{form.id}?page=2",
            **header
        )
        self.assertEqual(data.status_code, 404)

    def test_unauthorized_access_list_form_data(self):
        form = self.form

        user = SystemUser.objects.create_user(
            email="test2@test.org",
            password="test1234",
            first_name="test2",
            last_name="testing",
        )
        administration = Administration.objects.filter(level__level=1).first()
        role = UserRoleTypes.admin
        Access.objects.create(
            user=user, role=role, administration=administration
        )

        user_response = self.client.post(
            "/api/v1/login",
            {
                "email": user.email,
                "password": "test1234"
            },
            content_type="application/json"
        )
        token = user_response.json().get("token")
        header = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        data = self.client.get(
            f"/api/v1/form-data/{form.id}?page=1",
            content_type="application/json",
            **header,
        )
        self.assertEqual(data.status_code, 403)

    def test_datapoint_deletion(self):
        header = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

        # NOT FOUND
        exists = FormData.objects.filter(pk=1).first()
        if not exists:
            res = self.client.delete("/api/v1/data/1", follow=True, **header)
            self.assertEqual(res.status_code, 404)

        data_id = FormData.objects.first().id

        # REQUIRE AUTH
        res = self.client.delete("/api/v1/data/{data_id}")
        self.assertEqual(res.status_code, 404)

        res = self.client.delete(
            f"/api/v1/data/{data_id}", follow=True, **header
        )
        self.assertEqual(res.status_code, 204)
        answers = Answers.objects.filter(data_id=data_id).count()
        self.assertEqual(answers, 0)

    def test_datapoint_deletion_with_read_access(self):
        form = self.form

        user = SystemUser.objects.create_user(
            email="test3@test.org",
            password="test1234",
            first_name="test",
            last_name="testing",
        )
        administration = Administration.objects.filter(level__level=1).first()
        role = UserRoleTypes.admin
        Access.objects.create(
            user=user, role=role, administration=administration
        )
        # Assign form access to user with read access
        user_form = user.user_form.create(
            form=form,
        )
        user_form.user_form_access.create(
            access_type=FormAccessTypes.read,
        )
        user_form.save()

        user_response = self.client.post(
            "/api/v1/login",
            {
                "email": user.email,
                "password": "test1234"
            },
            content_type="application/json"
        )
        token = user_response.json().get("token")
        header = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        data_id = form.form_form_data.first().id
        data = self.client.delete(
            f"/api/v1/data/{data_id}",
            content_type="application/json",
            **header,
        )
        self.assertEqual(data.status_code, 403)

    def test_datapoint_with_history_deletion(self):
        header = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

        # NOT FOUND
        exists = FormData.objects.filter(pk=1).first()
        if not exists:
            res = self.client.delete("/api/v1/data/1", follow=True, **header)
            self.assertEqual(res.status_code, 404)
        form = Forms.objects.get(pk=1)
        self.assertEqual(form.id, 1)
        # Add data to edit
        adm = Administration.objects.filter(level__level=1).first()
        payload = {
            "data": {
                "name": "Testing Data",
                "administration": adm.id,
                "geo": [6.2088, 106.8456],
            },
            "answer": [
                {"question": 101, "value": "Jane"},
                {"question": 102, "value": ["Male"]},
                {"question": 103, "value": 31208200175},
                {"question": 104, "value": 2},
                {"question": 105, "value": [6.2088, 106.8456]},
                {"question": 106, "value": ["Parent", "Children"]},
            ],
        }
        data = self.client.post(
            "/api/v1/form-data/1/",
            payload,
            content_type="application/json",
            **header,
        )
        self.assertEqual(data.status_code, 200)
        data = data.json()
        self.assertEqual(data, {"message": "ok"})

        selected_data = FormData.objects.filter(
            form=form,
        ).first()
        data_id = selected_data.id

        payload = [
            {"question": 101, "value": "Jane Doe"},
            {"question": 102, "value": ["Female"]},
        ]
        res = self.client.put(
            f"/api/v1/form-data/1?data_id={data_id}",
            payload,
            content_type="application/json",
            **header,
        )
        self.assertEqual(res.status_code, 200)
        res = res.json()
        self.assertEqual(res, {"message": "direct update success"})

        res = self.client.get(
            f"/api/v1/data/{data_id}",
            content_type="application/json",
            **header,
        )
        self.assertEqual(res.status_code, 200)
        res = res.json()
        self.assertEqual(len(res) > 0, True)
        for d in res:
            question = d.get("question")
            value = d.get("value")
            history = d.get("history")
            if question == 101:
                self.assertEqual(question, 101)
                self.assertEqual(value, "Jane Doe")
                self.assertEqual(
                    list(history[0]), ["value", "created", "created_by"]
                )
                self.assertEqual(history[0]["created_by"], "Admin RUSH")
            if question == 102:
                self.assertEqual(question, 102)
                self.assertEqual(value, ["Female"])
                self.assertEqual(
                    list(history[0]), ["value", "created", "created_by"]
                )
                self.assertEqual(history[0]["created_by"], "Admin RUSH")
        # delete with history
        res = self.client.delete(
            f"/api/v1/data/{data_id}", follow=True, **header
        )
        self.assertEqual(res.status_code, 204)
        answers = Answers.objects.filter(data_id=data_id).count()
        self.assertEqual(answers, 0)
        hitory = AnswerHistory.objects.filter(data_id=data_id).count()
        self.assertEqual(hitory, 0)

    def test_monitoring_details_by_parent_id(self):
        header = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

        parent = FormData.objects.filter(children__gt=0).first()
        form_id = parent.form.id
        url = f"/api/v1/form-data/{form_id}"
        url += f"?page=1&parent={parent.id}"
        data = self.client.get(url, follow=True, **header)
        result = data.json()
        self.assertEqual(data.status_code, 200)
        self.assertEqual(
            list(result), ["current", "total", "total_page", "data"]
        )
        # total equal to number of children + the data itself
        self.assertEqual(result["total"], parent.children.count() + 1)
        # make sure the last item is parent
        self.assertEqual(result["data"][-1]["name"], parent.name)

    def test_get_data_details_anonymously(self):
        data_id = FormData.objects.first().id
        data = self.client.get(
            f"/api/v1/data/{data_id}",
            content_type="application/json",
        )
        self.assertEqual(data.status_code, 200)

    def test_datapoint_deletion_anonymously(self):
        data_id = FormData.objects.first().id
        data = self.client.delete(
            f"/api/v1/data/{data_id}",
            content_type="application/json",
        )
        self.assertEqual(data.status_code, 401)
