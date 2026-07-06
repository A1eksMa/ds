from enum import Enum


class Act(str, Enum):
    POST = "POST"
    GET = "GET"
    PATCH = "PATCH"
    DELETE = "DELETE"
