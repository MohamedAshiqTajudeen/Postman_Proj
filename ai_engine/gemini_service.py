"""
AI Translation & Assertion Conversion Engine using Google Gemini.
Handles prompt building, response sanitation and validation, exponential backoff retries,
and transforms raw JavaScript test lines into execution-ready Python code.
"""

import os
import re
import time
import logging
import json
from typing import Dict, Any, List, Optional
import google.generativeai as genai

# Setup robust system logging
logger = logging.getLogger("GeminiService")
logger.setLevel(logging.INFO)


class GeminiTranslationService:
    """
    Service wrapping Gemini API interactions for Assertion Translation,
    Testcase Planning, and AI recommendations.
    """

    def __init__(self):
        # Retrieve security keys strictly from the verified environment
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEY environment variable is not defined.")
            # We don't crash now, but we will raise descriptive errors on execution.
        else:
            genai.configure(api_key=self.api_key)

    def _execute_with_retry(self, prompt: str, system_instr: str, max_retries: int = 3) -> str:
        """
        Executes raw generative requests with safe exponential backoff
        and handles response verification.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing. Configure API keys in Settings > Secrets to resume.")

        # Initialize Generative Model with specified system rules, falling back gracefully if system_instruction keyword is unsupported in local SDK version
        use_fallback_prompt = False
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                generation_config={"temperature": 0.1, "top_p": 0.95},
                system_instruction=system_instr
            )
        except TypeError as te:
            logger.info(f"system_instruction not supported in this google-generativeai SDK version. Using fallback behavior. Error: {te}")
            try:
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    generation_config={"temperature": 0.1, "top_p": 0.95}
                )
                use_fallback_prompt = True
            except Exception as inner_e:
                logger.error(f"Failed to instantiate fallback GenerativeModel: {inner_e}")
                raise inner_e
        except Exception as e:
            logger.error(f"Failed to instantiate GenerativeModel structure: {e}")
            raise e

        attempt = 0
        wait_seconds = 2.0  # Starting base backoff wait

        while attempt < max_retries:
            attempt += 1
            request_time = time.strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{request_time}] Gemini request attempt {attempt}/{max_retries} for execution.")

            try:
                # Issue the generation request directly, appending system instructions if fallback is active
                final_prompt = prompt
                if use_fallback_prompt and system_instr:
                    final_prompt = f"System Instructions:\n{system_instr}\n\nUser Prompt:\n{prompt}"
                
                response = model.generate_content(final_prompt)
                
                # Extract text output safely
                if not response or not response.text:
                    raise ValueError("Received empty or incomplete payload structure from Gemini.")

                raw_result = response.text.strip()
                logger.info(f"Successfully received response from Gemini API on attempt {attempt}.")
                return raw_result

            except Exception as e:
                logger.error(f"Attempt {attempt}/{max_retries} failed with exception: {e}")
                if attempt == max_retries:
                    raise RuntimeError(f"Failed to fetch response after Max ({max_retries}) retries. Core error: {str(e)}")
                
                # Apply exponential wait
                logger.info(f"Sleeping for {wait_seconds} seconds before attempting retry code...")
                time.sleep(wait_seconds)
                wait_seconds *= 2.0

        return ""

    def validate_python_syntax(self, code_segment: str) -> bool:
        """Surgically verifies that the returned code runs or parses as valid Python."""
        if not code_segment or not code_segment.strip():
            return False
        try:
            compile(code_segment, "<string>", "exec")
            return True
        except SyntaxError as e:
            logger.warning(f"Python validation syntax check failed: {e}. Output was:\n{code_segment}")
            return False

    def sanitize_code_block(self, response_text: str) -> str:
        """Cleans response text from common markdown artifacts like ```python ... ```"""
        if not response_text:
            return ""

        # Remove explicit markdown wrapper blocks
        sanitized = re.sub(r"^```python\s*", "", response_text, flags=re.IGNORECASE)
        sanitized = re.sub(r"^```\s*", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"```$", "", sanitized).strip()
        return sanitized

    def translate_assertions(self, assertions_script: str) -> Dict[str, Any]:
        """
        Translates raw Javascript Postman assertions into modern Python pytest assertions.
        No Markdown, no wrapper explanations, strictly plain python scripts return.
        """
        if not assertions_script or not assertions_script.strip():
            return {
                "success": True,
                "assertions_converted": 0,
                "failed_conversions": 0,
                "unsupported_assertions": 0,
                "pytest_assertions": "",
                "warnings": ["No input Javascript test script provided."]
            }

        system_instruction = (
            "You are an expert dual-language tester translating Postman Javascript tests to Python's Pytest syntax.\n"
            "Translate standard Postman tests using the input response object variable 'response'.\n"
            "Respond ONLY with working, executable Python 'assert' statements or parsing logic. Do not write any "
            "outer function wrapper, markdown headers, or descriptive comments. Return strictly plain python code."
        )

        prompt = (
            f"Translate these raw Postman JavaScript assertions to Python Pytest code block:\n"
            f"```javascript\n{assertions_script}\n```\n\n"
            f"Use 'response' as the HTTP response mock variable. Example maps:\n"
            f"- 'pm.response.to.have.status(200)' -> 'assert response.status_code == 200'\n"
            f"- 'pm.response.to.be.success' -> 'assert response.status_code in [200, 201, 202, 204]'\n"
            f"- 'pm.response.to.have.jsonBody(\"uid\")' -> 'assert \"uid\" in response.json()'\n"
            f"Return strictly Python statements. Place raw code directly inside your output."
        )

        try:
            raw_response = self._execute_with_retry(prompt, system_instruction)
            python_code = self.sanitize_code_block(raw_response)

            # Analyze the quality gate requirements
            is_valid = self.validate_python_syntax(python_code)
            
            # Simple assessment counts
            lines = [line for line in python_code.split("\n") if line.strip() and not line.strip().startswith("#")]
            assertions_count = sum(1 for l in lines if "assert" in l)

            return {
                "success": is_valid,
                "assertions_converted": assertions_count if is_valid else 0,
                "failed_conversions": 0 if is_valid else len(lines),
                "unsupported_assertions": 0,
                "pytest_assertions": python_code if is_valid else f"# Translation Syntax Error during analysis\n# Raw Input:\n# {assertions_script}",
                "warnings": [] if is_valid else ["The translated Python code could not be resolved as valid Python syntax."]
            }

        except Exception as e:
            logger.exception("Failed translation transaction.")
            return {
                "success": False,
                "assertions_converted": 0,
                "failed_conversions": 1,
                "unsupported_assertions": 0,
                "pytest_assertions": f"# Error during translation processing:\n# {str(e)}",
                "warnings": [f"Gemini API Error occurred: {str(e)}"]
            }

    def generate_pytest_function(self, api_name: str, method: str, endpoint: str, 
                                 headers: Dict[str, str], request_body: Optional[str], 
                                 query_params: Dict[str, str], variables: Dict[str, Any],
                                 translated_assertions: str) -> str:
        """
        Assembles clean modular pytest functions with requests, parameterized inputs,
        and translates assertion assertions within logical classes.
        """
        system_instruction = (
            "You are a systems verification AI. Your task is to output a single, complete, "
            "independent Python function test case using 'pytest' and standard 'requests'.\n"
            "Return only valid, execution-ready, lint-safe python code. Do not wrap inside "
            "markdown, do not add descriptions or comments."
        )

        # Prepare parameters description
        headers_str = json.dumps(headers, indent=4) if headers else "{}"
        params_str = json.dumps(query_params, indent=4) if query_params else "{}"
        body_str = json.dumps(request_body) if request_body else "None"
        
        prompt = (
            f"Generate a single, standard PEP-8 style pytest verification function for an API endpoint:\n"
            f"- API Name: {api_name}\n"
            f"- Method: {method}\n"
            f"- Endpoint: {endpoint}\n"
            f"- Headers Configuration:\n{headers_str}\n"
            f"- Query Parameters:\n{params_str}\n"
            f"- Request Body: {body_str}\n"
            f"- Active Variables:\n{json.dumps(variables)}\n\n"
            f"Use the standard 'requests' library to execute the call.\n"
            f"Embed these exact translated assertion rules inside the function:\n"
            f"```python\n{translated_assertions if translated_assertions else 'assert response.status_code == 200'}\n```\n\n"
            f"Your output must be executable. Avoid any markdown delimiters, headers, or explanations and start directly with 'def test_...'"
        )

        try:
            raw_response = self._execute_with_retry(prompt, system_instruction)
            python_code = self.sanitize_code_block(raw_response)

            if not self.validate_python_syntax(python_code):
                # Safe recovery layout if parsing experienced hiccups
                return (
                    f"def test_{method.lower()}_{api_name.lower().replace(' ', '_')}(client_session):\n"
                    f"    # Fallback autogenerated structure\n"
                    f"    import requests\n"
                    f"    url = '{endpoint}'\n"
                    f"    headers = {headers_str}\n"
                    f"    params = {params_str}\n"
                    f"    response = requests.request('{method}', url, headers=headers, params=params)\n"
                    f"    assert response.status_code == 200\n"
                )
            return python_code

        except Exception as e:
            logger.exception("Failed testcase code aggregation.")
            return f"# Failure during code compilation rules: {str(e)}"

    def audit_api_recommendations(self, api_name: str, method: str, endpoint: str, 
                                  request_body: Optional[str]) -> List[Dict[str, str]]:
        """
        Asynchronously queries Gemini to inspect design structures for Functional, Security, or Performance items.
        Returns serialized dictionary elements.
        """
        system_instruction = (
            "You are a Quality and Audit Security Inspector. Analyze API endpoints and suggest enhancements.\n"
            "Format your response as a valid, parsable JSON array containing objects with properties: "
            "'recommendation' (string text prompt) and 'recommendation_type' ('Functional', 'Security', or 'Performance').\n"
            "Respond ONLY with raw JSON. No explanations, no markdown prefix."
        )

        prompt = (
            f"Review this API signature for vulnerabilities, inefficiencies or logic boundaries:\n"
            f"- API: {api_name}\n"
            f"- URL: {method} {endpoint}\n"
            f"- Body: {request_body or 'No request payload provided.'}\n\n"
            f"Provide exactly 2 actionable, brief items. Example structure to return:\n"
            f"[\n"
            f"  {{\"recommendation\": \"Ensure endpoint strictly mandates HTTPS\", \"recommendation_type\": \"Security\"}},\n"
            f"  {{\"recommendation\": \"Check input boundary validation on empty strings\", \"recommendation_type\": \"Functional\"}}\n"
            f"]"
        )

        default_recommendations = [
            {"recommendation": "Configure HTTPS on security paths.", "recommendation_type": "Security"},
            {"recommendation": "Add load stress verification triggers on query constraints.", "recommendation_type": "Performance"}
        ]

        try:
            raw_response = self._execute_with_retry(prompt, system_instruction)
            sanitized = self.sanitize_code_block(raw_response)
            parsed_list = json.loads(sanitized)
            
            if isinstance(parsed_list, list):
                result = []
                for item in parsed_list:
                    if isinstance(item, dict) and "recommendation" in item and "recommendation_type" in item:
                        # Normalize type values
                        rec_type = item["recommendation_type"]
                        if rec_type not in ["Functional", "Security", "Performance"]:
                            rec_type = "Functional"
                        result.append({
                            "recommendation": item["recommendation"],
                            "recommendation_type": rec_type
                        })
                return result

            return default_recommendations
        except Exception as e:
            logger.warning(f"Unable to parse custom рекомендации: {e}")
            return default_recommendations
