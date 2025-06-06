import typing
from django.test import TestCase
from django.http import HttpResponse
from django.test.utils import override_settings
from api.v1.v1_profile.management.commands import administration_seeder
from api.v1.v1_profile.models import Administration


@override_settings(USE_TZ=False, TEST_ENV=True)
class UpdateAdministrationPathTestCase(TestCase):

    def setUp(self):
        super().setUp()
        rows = [
            {
                "code_0": "ID",
                "National_0": "Indonesia",
                "code_1": "ID-JK",
                "Provinsi_1": "Jakarta/DKI Jakarta",
                "code_2": "ID-JKE",
                "Kabupaten_2": "East Jakarta",
                "code_3": "ID-JKE-KJ",
                "Kecamatan_3": "Kramat Djati",
                "code_4": "ID-JKE-KJ-CW",
                "Kelurahan_4": "Cawang",
            },
            {
                "code_0": "ID",
                "National_0": "Indonesia",
                "code_1": "ID-JK",
                "Provinsi_1": "Jakarta",
                "code_2": "ID-JKE",
                "Kabupaten_2": "East-Jakarta",
                "code_3": "ID-JKE-KJ",
                "Kecamatan_3": "Kramat Jati",
                "code_4": "ID-JKE-KJ-BK",
                "Kelurahan_4": "Balekambang",
            },
            {
                "code_0": "ID",
                "National_0": "Indonesia",
                "code_1": "ID-YGK",
                "Provinsi_1": "Yogyakarta",
                "code_2": "ID-YGK-SL",
                "Kabupaten_2": "Sleman",
                "code_3": "ID-YGK-SL-SET",
                "Kecamatan_3": "Seturan",
                "code_4": "ID-YGK-SL-SET-CP",
                "Kelurahan_4": "Cepit Baru",
            },
        ]
        geo_config = [
            {"id": 1, "level": 0, "name": "NAME_0", "alias": "National"},
            {"id": 2, "level": 1, "name": "NAME_1", "alias": "Provinsi"},
            {"id": 3, "level": 2, "name": "NAME_1", "alias": "Kabupaten"},
            {"id": 4, "level": 3, "name": "NAME_2", "alias": "Kecamatan"},
            {"id": 5, "level": 4, "name": "NAME_3", "alias": "Kelurahan"},
        ]
        administration_seeder.seed_administration_test(
            rows=rows,
            geo_config=geo_config
        )

        user_payload = {"email": "admin@akvo.org", "password": "Test105*"}
        user_response = self.client.post(
            "/api/v1/login", user_payload, content_type="application/json"
        )
        self.token = user_response.json().get("token")

    def test_update_parent_of_village(self):
        target = Administration.objects.filter(
            name="Cawang"
        ).first()
        correct_parent = Administration.objects.filter(
            name="Kramat Jati"
        ).first()
        payload = {
            'parent': correct_parent.id,
            'name': target.name,
        }

        response = typing.cast(
                HttpResponse,
                self.client.put(
                    f"/api/v1/administrations/{target.id}",
                    payload,
                    content_type='application/json',
                    HTTP_AUTHORIZATION=f'Bearer {self.token}'))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], target.name)
        self.assertEqual(
            f"{correct_parent.path}{correct_parent.id}.",
            body["path"]
        )

    def test_update_parent_of_ward(self):
        target = Administration.objects.filter(
            name="Kramat Jati"
        ).first()
        correct_parent = Administration.objects.filter(
            name="East Jakarta"
        ).first()
        payload = {
            'parent': correct_parent.id,
            'name': target.name,
        }

        response = typing.cast(
                HttpResponse,
                self.client.put(
                    f"/api/v1/administrations/{target.id}",
                    payload,
                    content_type='application/json',
                    HTTP_AUTHORIZATION=f'Bearer {self.token}'))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], target.name)
        self.assertEqual(
            f"{correct_parent.path}{correct_parent.id}.",
            body["path"]
        )
        for child in target.parent_administration.all():
            self.assertTrue(str(correct_parent.id) in child.path)

    def test_update_parent_of_second_level(self):
        target = Administration.objects.filter(
            name="East Jakarta"
        ).first()
        correct_parent = Administration.objects.filter(
            name="Jakarta"
        ).first()
        payload = {
            'parent': correct_parent.id,
            'name': target.name,
        }

        response = typing.cast(
                HttpResponse,
                self.client.put(
                    f"/api/v1/administrations/{target.id}",
                    payload,
                    content_type='application/json',
                    HTTP_AUTHORIZATION=f'Bearer {self.token}'))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], target.name)

        current_path = f"{correct_parent.path}{correct_parent.id}."
        self.assertEqual(current_path, body["path"])

        villages_count = Administration.objects.filter(
            path__startswith=current_path,
            level__name="Kelurahan",
        ).count()
        self.assertEqual(villages_count, 2)
