"""
Postman Collection Parsing and Extracting Engine (Supports v2.0 and v2.1 JSON schemas).
Deeply extracts API endpoints, nested hierarchies, parent environment values,
inherited authentication metadata, and registers specific JavaScript assertions.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional, Tuple, Set

# Initialize Logging configuration
logger = logging.getLogger("PostmanParser")
logger.setLevel(logging.INFO)


class ExtractedAssertion:
    """Represents an isolated JavaScript assertion statement found in Postman tests."""

    def __init__(self, raw_statement: str, assertion_type: str, match_detail: str):
        self.raw_statement = raw_statement.strip()
        self.assertion_type = assertion_type  # e.g., 'status', 'header', 'json_body', 'expect', 'generic'
        self.match_detail = match_detail.strip()

    def to_dict(self) -> Dict[str, str]:
        return {
            "raw_statement": self.raw_statement,
            "assertion_type": self.assertion_type,
            "match_detail": self.match_detail
        }


class ParsedRequest:
    """Models a single, fully-extracted API request configuration."""

    def __init__(self, api_name: str, method: str, endpoint: str,
                 headers: Dict[str, str], request_body: Optional[str],
                 query_params: Dict[str, str], authentication: Dict[str, Any],
                 variables: Dict[str, Any], raw_test_script: str,
                 assertions: List[ExtractedAssertion]):
        self.api_name = api_name or "Untitled Endpoint"
        self.method = method.upper() if method else "GET"
        self.endpoint = endpoint or "/"
        self.headers = headers or {}
        self.request_body = request_body
        self.query_params = query_params or {}
        self.authentication = authentication or {}
        self.variables = variables or {}
        self.raw_test_script = raw_test_script or ""
        self.assertions = assertions or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_name": self.api_name,
            "method": self.method,
            "endpoint": self.endpoint,
            "headers": self.headers,
            "request_body": self.request_body,
            "query_params": self.query_params,
            "authentication": self.authentication,
            "variables": self.variables,
            "raw_test_script": self.raw_test_script,
            "assertions": [a.to_dict() for a in self.assertions]
        }


class PostmanParser:
    """
    Parser for v2.0 and v2.1 Postman Collections.
    Recovers folders, resolves environment fallbacks, handles nested objects, and extracts JS code lines.
    """

    def __init__(self, json_content: str):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.collection_name: str = "Untitled Collection"
        self.requests: List[ParsedRequest] = []
        self.variables: Dict[str, Any] = {}
        
        self._load_and_validate(json_content)

    def _load_and_validate(self, json_content: str) -> None:
        """Validates standard JSON specifications and Postman requirements."""
        if not json_content or not json_content.strip():
            self.errors.append("Empty file content received.")
            return

        try:
            self.data = json.loads(json_content)
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON Format. Corrupted payload: {str(e)}")
            return

        if not isinstance(self.data, dict):
            self.errors.append("Collection JSON must be a top-level dictionary.")
            return

        info = self.data.get("info", {})
        if not info or "name" not in info:
            self.errors.append("Invalid collection structure: Missing required 'info.name' node.")
            return

        self.collection_name = info.get("name", "Untitled Collection")
        logger.info(f"Initiating Postman Parser validation for suite: {self.collection_name}")

        # Process collection-level environment placeholders
        variable_list = self.data.get("variable", [])
        if isinstance(variable_list, list):
            for v in variable_list:
                if isinstance(v, dict) and "key" in v:
                    self.variables[v["key"]] = v.get("value", "")

    def _parse_url(self, url_field: Any) -> Tuple[str, Dict[str, str], Dict[str, str]]:
        """
        Parses url constraints which can be of string structure or nested objects.
        Returns Tuple[full_url, query_parameters, url_variables]
        """
        if not url_field:
            return "", {}, {}

        # 1. Simple direct string format
        if isinstance(url_field, str):
            query_map = {}
            if "?" in url_field:
                parts = url_field.split("?", 1)
                query_str = parts[1]
                for segment in query_str.split("&"):
                    if "=" in segment:
                        k, v = segment.split("=", 1)
                        query_map[k] = v
                    else:
                        query_map[segment] = ""
            return url_field, query_map, {}

        # 2. Structured modern dict format
        if isinstance(url_field, dict):
            raw_url = url_field.get("raw", "")
            
            # Resolve query variables
            query_map = {}
            query_list = url_field.get("query", [])
            if isinstance(query_list, list):
                for q in query_list:
                    if isinstance(q, dict) and "key" in q:
                        if q.get("disabled") is True:
                            continue
                        query_map[q["key"]] = q.get("value") or ""

            # Resolve url variables (such as :id placeholder maps)
            variable_map = {}
            vars_list = url_field.get("variable", [])
            if isinstance(vars_list, list):
                for v in vars_list:
                    if isinstance(v, dict) and "key" in v:
                        variable_map[v["key"]] = v.get("value") or ""

            return raw_url, query_map, variable_map

        return str(url_field), {}, {}

    def _parse_headers(self, headers_field: Any) -> Dict[str, str]:
        """Maps lists or inline structures into uniform header key-values."""
        headers = {}
        if not headers_field:
            return headers

        if isinstance(headers_field, list):
            for h in headers_field:
                if isinstance(h, dict) and "key" in h:
                    if h.get("disabled") is True:
                        continue
                    headers[h["key"]] = h.get("value") or ""
        elif isinstance(headers_field, str):
            for line in headers_field.split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip()] = v.strip()
        return headers

    def _parse_body(self, body_field: Any) -> Optional[str]:
        """Resolves body parameter rules (json, urlencoded, form fields)."""
        if not body_field or not isinstance(body_field, dict):
            return ""

        mode = body_field.get("mode")
        if mode == "raw":
            return body_field.get("raw") or ""
        elif mode in ["urlencoded", "formdata"]:
            fields_list = body_field.get(mode, [])
            fields_map = {}
            if isinstance(fields_list, list):
                for f in fields_list:
                    if isinstance(f, dict) and "key" in f:
                        if f.get("disabled") is True:
                            continue
                        if mode == "formdata" and f.get("type") == "file":
                            fields_map[f["key"]] = f"<LocalFile: {f.get('src', 'unspecified')}>"
                        else:
                            fields_map[f["key"]] = f.get("value") or ""
            return json.dumps(fields_map, indent=2)
        return ""

    def _parse_auth(self, auth_field: Any) -> Dict[str, Any]:
        """Extracts authentication types and their associated values."""
        auth_info = {}
        if not auth_field or not isinstance(auth_field, dict):
            return auth_info

        auth_type = auth_field.get("type")
        if not auth_type:
            return auth_info

        auth_info["type"] = auth_type
        params = auth_field.get(auth_type, [])
        params_map = {}

        if isinstance(params, list):
            for item in params:
                if isinstance(item, dict) and "key" in item:
                    params_map[item["key"]] = item.get("value")
        elif isinstance(params, dict):
            params_map = params

        auth_info["credentials"] = params_map
        return auth_info

    def _extract_assertions(self, script_text: str) -> List[ExtractedAssertion]:
        """
        Parses JavaScript Postman test logic for specific assertions.
        Extracts expected structures to simplify automated python mappings.
        """
        assertions = []
        if not script_text:
            return assertions

        # Common regular expression match patterns for Postman assertions
        patterns = [
            # 1. Status Code assert (e.g. pm.response.to.have.status(200))
            (r"pm\.response\.to\.have\.status\((.*?)\)", "status"),
            # 2. Strict expect assertion (e.g. pm.expect(token).to.not.be.null)
            (r"pm\.expect\((.*?)\)\.(.*)", "expect"),
            # 3. Header check assertion (e.g. pm.response.to.have.header("Content-Type"))
            (r"pm\.response\.to\.have\.header\((.*?)\)", "header"),
            # 4. JSON body content validation
            (r"pm\.response\.to\.have\.jsonBody\((.*?)\)", "json_body"),
            # 5. Shorthand success validations (e.g. pm.response.to.be.success / to.be.info)
            (r"pm\.response\.to\.be\.(success|error|info|ok|serverError)", "status_shorthand"),
            # 6. Response body exact match validation
            (r"pm\.response\.to\.have\.body\((.*?)\)", "body")
        ]

        # Scan line by line for assertions
        for line in script_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("//") or line.startswith("/*"):
                continue

            matched = False
            for regex_str, assert_type in patterns:
                matches = re.findall(regex_str, line)
                if matches:
                    matched = True
                    match_val = str(matches[0])
                    assertions.append(ExtractedAssertion(line, assert_type, match_val))
                    break

            if not matched and ("pm.test" in line or "pm.expect" in line or "tests[" in line):
                assertions.append(ExtractedAssertion(line, "generic", line))

        return assertions

    def _extract_script_logic(self, events: List[Dict[str, Any]]) -> str:
        """Gathers individual JavaScript statements associated with the 'test' listen node."""
        if not events or not isinstance(events, list):
            return ""

        for event in events:
            if isinstance(event, dict) and event.get("listen") == "test":
                script_obj = event.get("script")
                if script_obj and isinstance(script_obj, dict):
                    exec_block = script_obj.get("exec", [])
                    if isinstance(exec_block, list):
                        return "\n".join(exec_block)
                    elif isinstance(exec_block, str):
                        return exec_block
        return ""

    def _recursive_extract(self, items_list: List[Dict[str, Any]], inherited_auth: Dict[str, Any], folder_path: List[str]) -> None:
        """Traverses the collection items, inheriting authentication context & documenting levels."""
        if not items_list or not isinstance(items_list, list):
            return

        # Tracking encountered request names for duplicate warnings
        seen_names: Set[str] = set()

        for item in items_list:
            if not isinstance(item, dict):
                continue

            item_name = item.get("name", "Untitled")
            sub_items = item.get("item")

            # Extract auth layers
            local_auth = self._parse_auth(item.get("auth"))
            effective_auth = local_auth if local_auth else inherited_auth

            if sub_items is not None and isinstance(sub_items, list):
                # Node is folder, append folder context and traverse nesting depth
                nested_path = folder_path + [item_name]
                self._recursive_extract(sub_items, effective_auth, nested_path)
            else:
                # Is a leaf api request
                req_obj = item.get("request")
                if not req_obj:
                    self.warnings.append(f"Skipping leaf item '{item_name}' - Missing 'request' node.")
                    continue

                # Unpack endpoints, query paths, variables overrides
                method = "GET"
                raw_endpoint = ""
                headers_dict = {}
                body_str = None
                query_params = {}
                url_variables = {}

                # If URL / parameters is standard dictionary block
                if isinstance(req_obj, dict):
                    method = req_obj.get("method") or "GET"
                    headers_dict = self._parse_headers(req_obj.get("header"))
                    body_str = self._parse_body(req_obj.get("body"))
                    
                    raw_endpoint, query_params, url_variables = self._parse_url(req_obj.get("url"))
                    req_auth_override = self._parse_auth(req_obj.get("auth"))
                    if req_auth_override:
                        effective_auth = req_auth_override
                elif isinstance(req_obj, str):
                    # Request is string-structured URL address
                    raw_endpoint, query_params, _ = self._parse_url(req_obj)

                # Warn if URL is absent from collection configuration
                if not raw_endpoint:
                    self.warnings.append(f"API request '{item_name}' has empty or invalid URL destination.")

                # Check for duplicate names inside folder scope
                full_qualified_name = " -> ".join(folder_path + [item_name])
                if item_name in seen_names:
                    self.warnings.append(f"Detected duplicate endpoint name structure: '{full_qualified_name}'.")
                seen_names.add(item_name)

                # Resolve Javascript Assertions
                raw_script = self._extract_script_logic(item.get("event", []))
                assertions = self._extract_assertions(raw_script)

                # Assemble merged context variables
                resolved_variables = {**self.variables, **url_variables}

                self.requests.append(ParsedRequest(
                    api_name=item_name,
                    method=method,
                    endpoint=raw_endpoint,
                    headers=headers_dict,
                    request_body=body_str,
                    query_params=query_params,
                    authentication=effective_auth,
                    variables=resolved_variables,
                    raw_test_script=raw_script,
                    assertions=assertions
                ))

    def parse(self) -> Dict[str, Any]:
        """
        Executes the recursive extraction workflow.
        Returns a rich parsed collection object with any validation logs.
        """
        if self.errors:
            return {
                "collection_name": self.collection_name,
                "is_valid": False,
                "errors": self.errors,
                "warnings": self.warnings,
                "requests": []
            }

        items = self.data.get("item", [])
        if not items:
            self.warnings.append("This Postman Collection is empty. No request nodes found.")

        # Process starting recursive traversal
        try:
            self._recursive_extract(items, inherited_auth={}, folder_path=[])
        except Exception as e:
            logger.exception("An unhandled exception crashed traversal.")
            self.errors.append(f"Parser engine traversal exception: {str(e)}")
            return {
                "collection_name": self.collection_name,
                "is_valid": False,
                "errors": self.errors,
                "warnings": self.warnings,
                "requests": []
            }

        return {
            "collection_name": self.collection_name,
            "is_valid": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "requests": [r.to_dict() for r in self.requests]
        }
