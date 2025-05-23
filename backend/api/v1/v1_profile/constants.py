from iwsims.settings import COUNTRY_NAME


class UserRoleTypes:
    super_admin = 1
    admin = 2

    FieldStr = {
        super_admin: "Super Admin",
        admin: "Admin",
    }


class OrganisationTypes:
    member = 1
    partnership = 2

    FieldStr = {
        member: "member",
        partnership: "partnership",
    }


class EntityTypes:
    school = 1
    health_care_facility = 2
    water_treatment_plant = 3
    rural_water_supply = 4

    FieldStr = {
        school: "School",
        health_care_facility: "Health Care Facilities",
        water_treatment_plant: "Water Treatment Plant",
        rural_water_supply: "Rural Water Supply",
    }


ADMINISTRATION_CSV_FILE = f"{COUNTRY_NAME}-administration.csv"

DEFAULT_SOURCE_FILE = f"./source/{ADMINISTRATION_CSV_FILE}"

DEFAULT_ADMINISTRATION_DATA = [
    {
        "0_code": "ID",
        "0_National": "Indonesia",
        "1_code": "ID-JK",
        "1_Province": "Jakarta",
        "2_code": "ID-JK-JKE",
        "2_District": "East Jakarta",
        "3_code": "ID-JK-JKE-KJ",
        "3_Subdistrict": "Kramat Jati",
        "4_code": "ID-JK-JKE-KJ-CW",
        "4_Village": "Cawang",
    },
    {
        "0_code": "ID",
        "0_National": "Indonesia",
        "1_code": "ID-YGK",
        "1_Province": "Yogyakarta",
        "2_code": "ID-YGK-SLE",
        "2_District": "Sleman",
        "3_code": "ID-YGK-SLE-SET",
        "3_Subdistrict": "Seturan",
        "4_code": "ID-YGK-SLE-SET-CEP",
        "4_Village": "Cepit Baru",
    },
]

DEFAULT_ADMINISTRATION_LEVELS = [
    {"id": 1, "level": 0, "name": "NAME_0", "alias": "National"},
    {"id": 2, "level": 1, "name": "NAME_1", "alias": "Province"},
    {"id": 3, "level": 2, "name": "NAME_2", "alias": "District"},
    {"id": 4, "level": 3, "name": "NAME_3", "alias": "Subdistrict"},
    {"id": 5, "level": 4, "name": "NAME_4", "alias": "Village"},
]
