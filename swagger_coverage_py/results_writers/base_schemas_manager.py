import json
import os
import pathlib
import platform
import re
import urllib

import yaml
from faker import Faker
from requests import Response

from swagger_coverage_py.configs import API_DOCS_FORMAT
from swagger_coverage_py.uri import URI


class ApiDocsManagerBase:
    def __init__(self, uri: URI, response: Response, kwargs: dict, method: str = None):
        self._uri = uri
        self._method = method
        self._response: Response = response
        self._other_request_params = kwargs

    def _get_path_params(self) -> list:
        params_ = []
        for key, value in self._uri.uri_params.items():
            params_.append(
                {
                    "name": key,
                    "in": "path",
                    "required": False,
                    "x-example": urllib.parse.unquote(str(value)),
                }
            )
        return params_

    def _get_body_params(self):
        try:
            request_body = json.loads(self._response.request.body)
        except Exception:
            request_body = None

        if request_body:
            types = {
                "object": "object",
                "str": "string",
                "int": "number",
                "float": "number",
                "bool": "boolean",
                "list": "array",
            }
            if isinstance(request_body, dict):
                properties = {}
                for k, v in request_body.items():
                    value_type = types.get(type(v).__name__, "object")
                    if value_type == "string":
                        value = urllib.parse.unquote(str(v))
                    else:
                        value = v
                    properties[k] = {k: value, "type": value_type}

                request_body: dict = {
                    "content": {
                        "application/json": {
                            "schema": {"type": "object", "properties": properties},
                            "example": json.loads(self._response.request.body),
                        }
                    }
                }
            elif isinstance(request_body, list):
                items_type = types.get(type(request_body[0]).__name__, "object")
                request_body: dict = {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "array",
                                "items": {"type": items_type},
                            },
                            "example": json.loads(self._response.request.body),
                        }
                    }
                }
            else:
                request_body: dict = {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "string",
                            },
                            "example": urllib.parse.unquote(
                                str(self._response.request.body)
                            ),
                        }
                    }
                }
        else:
            request_body = None

        return request_body

    def _get_other_request_params(self, params_key: str, params_in: str) -> list:
        prams_raw = self._other_request_params.get(params_key, {})
        if prams_raw:
            params = list(prams_raw.items())
        else:
            params = []

        raw = self._uri.raw.split("?")
        if len(raw) > 1:
            params += [tuple(x.split("=")) for x in str(raw[1]).split("&")]
        if not params:
            return []

        params_ = []
        for key, value in params:
            params_.append(
                {
                    "name": key,
                    "in": params_in,
                    "required": False,
                    "x-example": urllib.parse.unquote(str(value)),
                }
            )
        return params_

    def _get_query_params(self) -> list:
        return self._get_other_request_params(params_key="params", params_in="query")

    def _get_header_params(self) -> list:
        return self._get_other_request_params(params_key="headers", params_in="header")

    def __get_output_subdir(self):
        return re.match(r"(^\w*)://(.*)", self._uri.host).group(2).replace(".", "_").replace(":", "_")

    def write_schema(self):
        schema_dict = self._get_schema()
        rnd = Faker().pystr(min_chars=5, max_chars=5)
        file_name = f"{self._method.upper()} {self._uri.formatted[1::]}".replace(
            "/", "-"
        ).replace(":", "_")
        path_ = f"swagger-coverage-output/{self.__get_output_subdir()}"
        pathlib.Path(path_).mkdir(parents=True, exist_ok=True)
        file_path = f"{path_}/{file_name}".split("?")[0]
        file_path = f"{file_path} ({rnd}).{API_DOCS_FORMAT}"

        try:
            with open(file_path, "w+") as file:
                if API_DOCS_FORMAT == "yaml":
                    file.write(yaml.safe_dump(schema_dict, indent=4, sort_keys=False))
                elif API_DOCS_FORMAT == "json":
                    file.write(json.dumps(schema_dict, indent=4))
                else:
                    raise Exception(
                        f"Unexpected docs format: {API_DOCS_FORMAT}. Valid formats: json, yaml"
                    )

        except FileNotFoundError as e:
            system_ = platform.system()
            abs_path = os.path.abspath(file_path)

            if system_ == "Windows" and len(abs_path) > 256:
                raise EnvironmentError(
                    f"Absolute path length is greater than 256 symbols:\n"
                    f"{abs_path}\n"
                    f"To remove this restriction you can use this guide: "
                    f"https://docs.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation#enable-long-paths-in-windows-10-version-1607-and-later "
                )
            else:
                raise Exception(
                    f"Cannot write to file.\n"
                    f"Path: {abs_path}\n"
                    f"Details: {e.strerror}"
                )

        return schema_dict
