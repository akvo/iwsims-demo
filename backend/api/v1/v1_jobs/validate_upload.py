import datetime
import enum
import itertools
import math
import pandas as pd

from django.conf import settings
from string import ascii_uppercase
from api.v1.v1_data.models import FormData
from api.v1.v1_forms.constants import QuestionTypes
from api.v1.v1_forms.models import Questions
from api.v1.v1_jobs.functions import ValidationText, HText
from api.v1.v1_profile.models import Administration


class ExcelError(enum.Enum):
    sheet = "sheet_name"
    header = "header_name"
    value = "column_value"


def generate_excel_columns():
    n = 1
    while True:
        yield from (
            "".join(group)
            for group in itertools.product(ascii_uppercase, repeat=n)
        )
        n += 1


def validate_header_names(header, col, header_names):
    default = {"error": ExcelError.header, "cell": col}
    if header == "data_id":
        return False
    if "Unnamed:" in header:
        default.update(
            {"error_message": ValidationText.header_name_missing.value}
        )
        return default
    if "|" in header:
        if header not in header_names:
            header_id = header.split("|")[0]
            error_msg = f"{header_id} {ValidationText.header_invalid_id.value}"
            default.update(
                {
                    "error_message": error_msg,
                }
            )
            return default
    return False


def validate_number(answer, question):
    try:
        answer = float(answer)
    except ValueError:
        return {"error_message": ValidationText.numeric_validation.value}
    if question.rule:
        rule = question.rule
        qname = question.name
        for r in rule:
            if r == "allow_decimal" and not rule[r]:
                answer = int(float(answer))
            if r == "max" and float(rule[r]) < answer:
                msg = ValidationText.numeric_max_rule.value.replace(
                    "--question--", qname
                ).replace("--rule--", str(rule[r]))
                return {"error_message": msg}
            if r == "min" and float(rule[r]) > answer:
                msg = ValidationText.numeric_min_rule.value.replace(
                    "--question--", qname
                ).replace("--rule--", str(rule[r]))
                return {"error_message": msg}
    return False


def validate_geo(answer):
    answer = str(answer)
    answer = answer.strip().replace("|", ",")
    try:
        for a in answer.split(","):
            float(a.strip())
    except ValueError:
        return {"error_message": ValidationText.lat_long_validation.value}
    if "," not in answer:
        return {"error_message": ValidationText.lat_long_validation.value}
    answer = answer.split(",")
    if len(answer) != 2:
        return {"error_message": ValidationText.lat_long_validation.value}
    for a in answer:
        try:
            a = float(a.strip())
        except ValueError:
            return {"error_message": ValidationText.lat_long_validation.value}
    return False


def validate_administration(answer, adm):
    if adm["id"] == 1:
        return False
    aw = answer.split("|")
    name = adm["name"]
    if len(aw) < 2:
        return {
            "error_message": ValidationText.administration_validation.value
        }
    path = []
    for i, a in enumerate(aw):
        if not i:
            administration = Administration.objects.filter(name=a).first()
        else:
            administration = Administration.objects.filter(
                name=a, parent_id=path[-1]
            ).first()
        path.append(administration.id)

    if adm["id"] not in path:
        msg = ValidationText.administration_not_part_of.value.replace(
            "--answer--", str(aw[-1])
        ).replace("--administration--", name)
        return {"error_message": msg}
    return False


def validate_date(answer):
    try:
        answer = datetime.datetime.strptime(str(answer), "%Y-%m-%d")
    except ValueError:
        msg = f"Invalid date format: {answer}. It should be YYYY-MM-DD"
        return {"error_message": msg}
    return False


def validate_option(options, answer):
    options = [o.value for o in options]
    lower_options = [o.lower() for o in options]
    answer = str(answer).split("|")
    invalid_value = []
    invalid_case = []
    invalid = False
    for a in answer:
        if a not in options and a.lower() not in lower_options:
            invalid = True
            invalid_value.append(a)
        if a not in options and a.lower() in lower_options:
            invalid = True
            invalid_case.append(a)
    if invalid:
        message = ""
        if len(invalid_case):
            invalid_list = ", ".join(invalid_case)
            message += f"Invalid case: {invalid_list}"
        if len(invalid_case) and len(invalid_value):
            message += " and "
        if len(invalid_value):
            invalid_list = ", ".join(invalid_value)
            message += f"Invalid value: {invalid_list}"
        return {"error_message": message}
    return False


def validate_dependency(
    col, answered: bool, dependency_answer, question: Questions
):
    default = {
        "error": ExcelError.value,
        "cell": col,
        "error_message": f"{question.name} {ValidationText.is_required.value}",
    }
    if not question.required and not question.dependency:
        # no answer requirements at all (best performance)
        return False
    if (
        question.required
        and not answered
        and not question.dependency
    ):
        # answer is absolutely required
        return default
    if question.dependency:
        # check if the answer is required or should be blank
        question_is_appear = False
        all_deps_match = []
        for question_dependency in question.dependency:
            if question_dependency["id"] in dependency_answer:
                da = dependency_answer[question_dependency["id"]]
                if "options" in question_dependency:
                    for daw in str(da).split("|"):
                        if daw in question_dependency["options"]:
                            all_deps_match.append(True)
                if "min" in question_dependency and isinstance(da, int):
                    if int(da) >= int(question_dependency["min"]):
                        all_deps_match.append(True)
                if "max" in question_dependency and isinstance(da, int):
                    if int(da) <= int(question_dependency["max"]):
                        all_deps_match.append(True)
        if len(all_deps_match) == len(question.dependency):
            question_is_appear = True
        # answer should be blank
        if answered and not question_is_appear:
            msg = f"{question.name} {ValidationText.should_be_empty.value}"
            default.update({"error_message": msg})
            return default
        # answer should not be empty
        if not answered and question_is_appear and question.required:
            return default
    # no requirement wether answered or not
    return False


def validate_row_data(
    col, answer, dependency_answer, question: Questions, adm
):
    default = {"error": ExcelError.value, "cell": col}
    answered = answer == answer
    dependency_errors = validate_dependency(
        col, answered, dependency_answer, question
    )
    if dependency_errors:
        return dependency_errors
    if not answered:
        return False
    if isinstance(answer, str):
        answer = HText(answer).clean
    if question.type == QuestionTypes.administration:
        err = validate_administration(answer, adm)
        if err:
            default.update(err)
            return default
    elif question.type == QuestionTypes.geo:
        err = validate_geo(answer)
        if err:
            default.update(err)
            return default
    elif question.type == QuestionTypes.number:
        err = validate_number(answer, question)
        if err:
            default.update(err)
            return default
    elif question.type == QuestionTypes.date:
        err = validate_date(answer)
        if err:
            default.update(err)
            return default
    elif question.type in [
        QuestionTypes.option,
        QuestionTypes.multiple_option,
    ]:
        err = validate_option(question.options.all(), answer)
        if err:
            default.update(err)
            return default
    else:
        pass
    return False


def validate_sheet_name(file: str):
    xl = pd.ExcelFile(file)
    return xl.sheet_names


def validate_data_id(col, data_id, collect_data_ids=[]):
    default = {"error": ExcelError.value, "cell": col}
    if data_id and not FormData.objects.filter(id=data_id).exists():
        msg = ValidationText.invalid_data_id.value.replace(
            "--data_id--", str(data_id)
        )
        default.update({"error_message": msg})
        return default
    # check duplicated data_id
    if collect_data_ids.count(data_id) > 1:
        msg = ValidationText.duplicated_data_id.value.replace(
            "--data_id--", str(data_id)
        )
        default.update({"error_message": msg})
        return default
    return False


def validate(form: int, administration: int, file: str):
    sheet_names = validate_sheet_name(file)
    template_sheets = ["data", "questions", "options"]
    TESTING = settings.TEST_ENV
    if TESTING:
        template_sheets = ["data"]
    for sheet_tab in template_sheets:
        if sheet_tab not in sheet_names:
            return [
                {
                    "error": ExcelError.sheet,
                    "error_message": ValidationText.template_validation.value,
                    "sheets": ",".join(sheet_names),
                }
            ]
    questions = Questions.objects.filter(form_id=form)
    header_names = [q.name for q in questions]
    df = pd.read_excel(file, sheet_name="data")
    collect_data_ids = []
    if "id" in list(df):
        df = df.rename(columns={"id": "data_id"})
        collect_data_ids = df["data_id"].tolist()
    if df.shape[0] == 0:
        return [
            {
                "error": ExcelError.sheet,
                "error_message": ValidationText.file_empty_validation.value,
            }
        ]
    excel_head = {}
    excel_cols = list(itertools.islice(generate_excel_columns(), df.shape[1]))
    for index, header in enumerate(list(df)):
        excel_head.update({excel_cols[index]: header})

    header_error = []
    data_error = []

    adm = Administration.objects.get(id=administration)
    adm = {"id": adm.id, "name": adm.name}
    for col in excel_head:
        header = excel_head[col]
        errors = None
        if header not in header_names + ["data_id"]:
            errors = validate_header_names(header, f"{col}1", header_names)
        if errors:
            header_error.append(errors)
        if not errors:
            if header == "data_id":
                data_ids = list(df[header])
                for i, data_id in enumerate(data_ids):
                    ix = i + 2
                    data_id = None if math.isnan(data_id) else data_id
                    errors = validate_data_id(
                        f"{col}{ix}", data_id, collect_data_ids
                    )
                    if errors:
                        data_error.append(errors)
            question = questions.filter(name=header).first()
            if question:
                dependencies = []
                if question.dependency:
                    for qd in question.dependency:
                        dependency = questions.filter(
                            id=qd.get("id")
                        ).first()
                        dependencies.append({
                            "id": dependency.id,
                            "name": dependency.name
                        })
                answers = list(df[header])
                for i, answer in enumerate(answers):
                    ix = i + 2
                    dependency_answer = {}
                    for dn in dependencies:
                        if dn["name"] in list(df):
                            dependency_answer[dn["id"]] = list(
                                df[dn["name"]]
                            )[i]
                    errors = validate_row_data(
                        f"{col}{ix}", answer, dependency_answer, question, adm
                    )
                    if errors:
                        data_error.append(errors)
    return header_error + data_error
