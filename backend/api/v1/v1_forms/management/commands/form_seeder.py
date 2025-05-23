import json
import os
import re

from iwsims.settings import PROD
from django.core.management import BaseCommand

from api.v1.v1_forms.constants import QuestionTypes, AttributeTypes
from api.v1.v1_forms.models import (
    Forms, Questions,
    QuestionGroup as QG,
    QuestionOptions as QO,
    QuestionAttribute as QA)
from api.v1.v1_forms.constants import SubmissionTypes


def clean_string(input_string):
    stripped_string = input_string.strip()
    lowercase_string = stripped_string.lower()
    no_special_chars_string = re.sub(r'[^a-z0-9 ]', '', lowercase_string)
    underscore_string = no_special_chars_string.replace(' ', '_')
    final_string = underscore_string.strip('_')
    return final_string


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("-t",
                            "--test",
                            nargs="?",
                            const=1,
                            default=False,
                            type=int)
        parser.add_argument("-f",
                            "--file",
                            nargs="?",
                            default=False,
                            type=int)

    def handle(self, *args, **options):
        TEST = options.get("test")
        JSON_FILE = options.get("file")
        # Form source
        source_folder = './source/forms/'
        source_files = [
            f"{source_folder}{json_file}"
            for json_file in os.listdir(source_folder)
        ]
        source_files = list(
            filter(lambda x: "example" in x
                   if TEST else "example" not in x, source_files))
        if PROD:
            source_files = list(filter(lambda x: "prod" in x, source_files))
        if JSON_FILE:
            source_files = [f"{source_folder}{JSON_FILE}.prod.json"]
        for source in source_files:
            json_form = open(source, 'r')
            json_form = json.load(json_form)
            form = Forms.objects.filter(id=json_form["id"]).first()
            QA.objects.filter(question__form=form).all().delete()
            submission_types = json_form.get("submission_types")
            submission_types = [
                getattr(SubmissionTypes, st) for st in submission_types
            ]
            if not form:
                form = Forms.objects.create(
                    id=json_form["id"],
                    name=json_form["form"],
                    version=1,
                    approval_instructions=json_form.get(
                        'approval_instructions'
                    ),
                    submission_types=submission_types,
                )
                if not TEST:
                    self.stdout.write(
                        f"Form Created | {form.name} V{form.version}")
            else:
                form.name = json_form["form"]
                form.version += 1
                form.submission_types = submission_types
                if json_form.get("approval_instructions"):
                    form.approval_instructions = json_form.get(
                        "approval_instructions"
                    )
                else:
                    form.approval_instructions = None
                form.save()
                if not TEST:
                    self.stdout.write(
                        f"Form Updated | {form.name} V{form.version}")
            # question group loop
            list_of_question_ids = []
            list_of_question_group_ids = []
            for qgi, qg in enumerate(json_form["question_groups"]):
                question_group = QG.objects.filter(pk=qg["id"]).first()
                list_of_question_group_ids.append(qg["id"])
                list_of_question_ids += [q["id"] for q in qg["questions"]]
                if not question_group:
                    question_group = QG.objects.create(
                        id=qg["id"],
                        name=qg["name"],
                        label=qg["label"],
                        form=form,
                        order=qg["order"],
                        repeatable=qg.get("repeatable", False),
                        repeat_text=qg.get("repeatText"),
                    )
                else:
                    question_group.name = qg["name"]
                    question_group.label = qg["label"]
                    question_group.order = qg["order"]
                    question_group.repeatable = qg.get("repeatable", False)
                    question_group.repeat_text = qg.get("repeatText")
                    question_group.save()
                for qi, q in enumerate(qg["questions"]):
                    question = Questions.objects.filter(pk=q["id"]).first()
                    if not question:
                        question = Questions.objects.create(
                            id=q.get("id"),
                            name=q["name"],
                            label=q["label"],
                            short_label=q.get("short_label"),
                            form=form,
                            order=q.get("order") or qi + 1,
                            meta=q.get("meta"),
                            question_group=question_group,
                            rule=q.get("rule"),
                            required=q.get("required"),
                            hidden=q.get("hidden"),
                            dependency=q.get("dependency"),
                            api=q.get("api"),
                            type=getattr(QuestionTypes, q["type"]),
                            tooltip=q.get("tooltip"),
                            fn=q.get("fn"),
                            pre=q.get("pre"),
                            display_only=q.get("displayOnly"),
                            meta_uuid=q.get("meta_uuid"),
                            extra=q.get("extra"),
                            default_value=q.get("default_value"),
                            disabled=q.get("disabled"),
                        )
                    else:
                        question.question_group = question_group
                        question.name = q["name"]
                        question.label = q["label"]
                        question.short_label = q.get("short_label")
                        question.order = q.get("order") or qi + 1
                        question.meta = q.get("meta")
                        question.rule = q.get("rule")
                        question.required = q.get("required")
                        question.dependency = q.get("dependency")
                        question.type = getattr(QuestionTypes, q["type"])
                        question.api = q.get("api")
                        question.extra = q.get("extra")
                        question.tooltip = q.get("tooltip")
                        question.fn = q.get("fn")
                        question.hidden = q.get("hidden")
                        question.display_only = q.get("displayOnly")
                        question.pre = q.get("pre")
                        question.meta_uuid = q.get("meta_uuid")
                        question.extra = q.get("extra")
                        question.default_value = q.get("default_value")
                        question.disabled = q.get("disabled")
                        question.save()
                    QO.objects.filter(question=question).all().delete()
                    if q.get("options"):
                        QO.objects.bulk_create([
                            QO(
                                label=o["label"].strip(),
                                value=o["value"] if o.get("value")
                                else clean_string(
                                    o["label"]
                                ),
                                question=question,
                                order=io + 1,
                                color=o.get("color")
                            ) for io, o in enumerate(q.get("options"))
                        ])
                    QA.objects.filter(question=question).all().delete()
                    if q.get("attributes"):
                        QA.objects.bulk_create([
                            QA(
                                attribute=getattr(AttributeTypes, a),
                                question=question,
                            ) for a in q.get("attributes")
                        ])

            # delete questions that are not in the json
            Questions.objects.filter(
                form=form).exclude(id__in=list_of_question_ids).delete()

            # delete question groups that are not in the json
            QG.objects.filter(
                form=form).exclude(id__in=list_of_question_group_ids).delete()
