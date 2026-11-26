"""Bound JSON reads before decoding, including streams with no length hint."""

from io import BytesIO

from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.parsers import JSONParser


class PayloadTooLarge(APIException):
    status_code = 413
    default_detail = "Request body is too large."
    default_code = "payload_too_large"


class LimitedJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise PayloadTooLarge()
        return super().parse(BytesIO(data), media_type, parser_context)
