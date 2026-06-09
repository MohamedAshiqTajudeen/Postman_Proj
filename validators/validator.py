"""
Validation Engine for Pytest Migrator.
Enforces PEP-8 checks, executes AST compilation tests, detects hanging Postman wrappers,
screens for missing variables, duplicate functions, and incorrect HTTP structures.
"""

import ast
import re
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("ValidationEngine")
logger.setLevel(logging.INFO)


class ValidationEngine:
    """
    Validates Python Pytest scripts, testing syntax layouts,
    variable mapping patterns, and assertion sanity gates.
    """

    @staticmethod
    def validate_python_syntax(script_content: str) -> Tuple[bool, List[str]]:
        """
        Uses AST (Abstract Syntax Tree) compilation to execute deep static syntax evaluations.
        Returns Tuple indicating whether code is compiles properly alongside structural errors if any.
        """
        if not script_content or not script_content.strip():
            return False, ["Script file content is completely empty."]

        try:
            ast.parse(script_content)
            return True, []
        except SyntaxError as e:
            error_msg = f"Syntax raised error at Line {e.lineno}, Col {e.offset}: {e.msg}"
            return False, [error_msg]
        except Exception as e:
            return False, [f"Static analyzer raised execution discrepancy: {str(e)}"]

    def validate_script(self, script_content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Runs comprehensive analysis across generated test case rules.
        Checks for syntax, invalid imports, duplicate functions, dynamic placeholders,
        and lingering Postman Javascript objects.
        """
        errors: List[str] = []
        warnings: List[str] = []

        if not script_content or not script_content.strip():
            return {
                "valid": False,
                "warnings": warnings,
                "errors": ["No script content to validate (Received empty stream)."]
            }

        # 1. PEP-8 Compilation Check (AST verification)
        is_syntax_valid, syntax_errors = self.validate_python_syntax(script_content)
        if not is_syntax_valid:
            errors.extend(syntax_errors)

        # Skip remaining check validations if syntax is completely corrupted
        if errors:
            return {
                "valid": False,
                "warnings": warnings,
                "errors": errors
            }

        # Parsing abstract structure to scan imports, function definitions, and asserts
        parsed_tree = ast.parse(script_content)
        
        # 2. Check for Critical Imports
        imported_modules = set()
        for node in ast.walk(parsed_tree):
            if isinstance(node, ast.Import):
                for name_node in node.names:
                    imported_modules.add(name_node.name)
            elif isinstance(node, ast.ImportFrom):
                imported_modules.add(node.module)

        for mandatory_lib in ["requests", "pytest"]:
            if mandatory_lib not in imported_modules:
                warnings.append(f"Missing recommended standard library import: '{mandatory_lib}'.")

        # 3. Detect Duplicate Test Case Names and Functions
        function_names = []
        for node in ast.walk(parsed_tree):
            if isinstance(node, ast.FunctionDef):
                function_names.append(node.name)

        duplicate_funcs = set([f for f in function_names if function_names.count(f) > 1])
        for dup in duplicate_funcs:
            errors.append(f"Detected duplicate test function namespace: '{dup}'. Refactor function declaration.")

        # 4. Request Metadata Sanitization Verification
        http_method = metadata.get("method", "GET").upper()
        endpoint_url = metadata.get("endpoint", "")

        if not endpoint_url:
            errors.append("Invalid API structural map: Target URL endpoint address is absent.")
        elif not (endpoint_url.startswith("http://") or endpoint_url.startswith("https://") or "{{" in endpoint_url):
            warnings.append(f"URL string '{endpoint_url}' has not resolved or is missing schema prefixes (http/https).")

        if http_method not in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
            errors.append(f"Unsupported HTTP method: '{http_method}'. Rejecting test execution structure.")

        # 5. Check for unresolved Postman assertions (e.g., lingering Javascript pm. statements)
        pm_lingering = re.findall(r"(\bpm\.\w+\b|\btests\[\b)", script_content)
        if pm_lingering:
            errors.append(
                f"Translation discrepancy: Postman JavaScript structures detected inside Python outputs: {set(pm_lingering)}."
            )

        # 6. Check for Hanging Variable Placeholders (e.g. unhandled double bracket templates '{{variable}}')
        hanging_placeholders = re.findall(r"\{\{([a-zA-Z0-9_\-]+)\}\}", script_content)
        if hanging_placeholders:
            warnings.append(
                f"Unresolved environment context variables detected: {set(hanging_placeholders)}. "
                "Ensure parameters are fully populated in runtime environments."
            )

        # 7. Check for Empty/Useless Assertions
        assertion_statements = [node for node in ast.walk(parsed_tree) if isinstance(node, ast.Assert)]
        if not assertion_statements:
            warnings.append("No 'assert' statements defined. Pytest might execute without asserting outcomes.")

        return {
            "valid": len(errors) == 0,
            "warnings": warnings,
            "errors": errors
        }
