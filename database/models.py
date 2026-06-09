"""
Database Entities / ORM Model structures for Pytest Migrator
Contains lightweight dictionaries and data classes representing entries.
"""

from typing import Dict, Any, List

class CollectionModel:
    def __init__(self, id: int, collection_name: str, file_name: str, uploaded_by: str, uploaded_at: str, total_apis: int, status: str):
        self.id = id
        self.collection_name = collection_name
        self.file_name = file_name
        self.uploaded_by = uploaded_by
        self.uploaded_at = uploaded_at
        self.total_apis = total_apis
        self.status = status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "collection_name": self.collection_name,
            "file_name": self.file_name,
            "uploaded_by": self.uploaded_by,
            "uploaded_at": self.uploaded_at,
            "total_apis": self.total_apis,
            "status": self.status
        }


class APIDetailModel:
    def __init__(self, id: int, collection_id: int, api_name: str, method: str, endpoint: str, headers: str, request_body: str, query_params: str):
        self.id = id
        self.collection_id = collection_id
        self.api_name = api_name
        self.method = method
        self.endpoint = endpoint
        self.headers = headers
        self.request_body = request_body
        self.query_params = query_params

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "api_name": self.api_name,
            "method": self.method,
            "endpoint": self.endpoint,
            "headers": self.headers,
            "request_body": self.request_body,
            "query_params": self.query_params
        }


class GeneratedTestCaseModel:
    def __init__(self, id: int, api_id: int, testcase_name: str, testcase_type: str, expected_result: str, generated_at: str):
        self.id = id
        self.api_id = api_id
        self.testcase_name = testcase_name
        self.testcase_type = testcase_type
        self.expected_result = expected_result
        self.generated_at = generated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "api_id": self.api_id,
            "testcase_name": self.testcase_name,
            "testcase_type": self.testcase_type,
            "expected_result": self.expected_result,
            "generated_at": self.generated_at
        }


class GeneratedScriptModel:
    def __init__(self, id: int, api_id: int, script_name: str, script_content: str, created_at: str):
        self.id = id
        self.api_id = api_id
        self.script_name = script_name
        self.script_content = script_content
        self.created_at = created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "api_id": self.api_id,
            "script_name": self.script_name,
            "script_content": self.script_content,
            "created_at": self.created_at
        }


class AIRecommendationModel:
    def __init__(self, id: int, api_id: int, recommendation: str, recommendation_type: str, generated_at: str):
        self.id = id
        self.api_id = api_id
        self.recommendation = recommendation
        self.recommendation_type = recommendation_type
        self.generated_at = generated_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "api_id": self.api_id,
            "recommendation": self.recommendation,
            "recommendation_type": self.recommendation_type,
            "generated_at": self.generated_at
        }


class ConversionReportModel:
    def __init__(self, id: int, collection_id: int, assertions_converted: int, failed_conversions: int,
                 unsupported_assertions: int, warnings: List[str], success_percentage: float, created_at: str):
        self.id = id
        self.collection_id = collection_id
        self.assertions_converted = assertions_converted
        self.failed_conversions = failed_conversions
        self.unsupported_assertions = unsupported_assertions
        self.warnings = warnings
        self.success_percentage = success_percentage
        self.created_at = created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "assertions_converted": self.assertions_converted,
            "failed_conversions": self.failed_conversions,
            "unsupported_assertions": self.unsupported_assertions,
            "warnings": self.warnings,
            "success_percentage": self.success_percentage,
            "created_at": self.created_at
        }
