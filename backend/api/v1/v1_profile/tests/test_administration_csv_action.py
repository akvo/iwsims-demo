import pandas as pd

from django.test import TestCase
from django.test.utils import override_settings
from django.core.management import call_command
from mis.settings import STORAGE_PATH
from api.v1.v1_profile.models import Administration, Levels
from utils.custom_generator import (
    administration_csv_add,
    administration_csv_update,
    administration_csv_delete
)


@override_settings(USE_TZ=False, TEST_ENV=True)
class AdministrationCSVTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()
        call_command("administration_seeder", "--test")
        call_command("download_all_administrations", "--test")

    def test_add_data_in_csv(self):
        last = Levels.objects.order_by('-id').first()
        parent = Administration.objects.filter(level__id=last.id - 1).first()
        new_adm = Administration(
            id=111,
            name='New village',
            level=last,
            parent=parent
        )
        new_adm.save()
        filepath = administration_csv_add(data=new_adm)
        self.assertEqual(
            filepath,
            f"{STORAGE_PATH}/master_data/test-administration.csv"
        )
        df = pd.read_csv(filepath)
        last_record = df.iloc[-1]
        self.assertEqual(last_record["village"], "New village")
        self.assertEqual(last_record["village_id"], 111)

    def test_update_data_in_csv(self):
        max_level = Levels.objects.order_by('-id').first()
        adm = Administration.objects.filter(
            level__level=max_level.level,
        ).first()
        adm.name = 'Village name changed'
        adm.save()

        filepath = administration_csv_update(data=adm)
        self.assertEqual(
            filepath,
            f"{STORAGE_PATH}/master_data/test-administration.csv"
        )
        df = pd.read_csv(filepath)
        contains_value = (df == "Village name changed").any().any()
        self.assertTrue(contains_value)

    def test_delete_data_in_csv(self):
        max_level = Levels.objects.order_by('-id').first()
        adm = Administration.objects.filter(
            level__level=max_level.level,
        ).first()
        adm_id = adm.id
        adm_name = adm.name
        adm.delete()

        filepath = administration_csv_delete(id=adm_id)
        self.assertEqual(
            filepath,
            f"{STORAGE_PATH}/master_data/test-administration.csv"
        )
        df = pd.read_csv(filepath)
        contains_value = (df == adm_name).any().any()
        self.assertFalse(contains_value)
