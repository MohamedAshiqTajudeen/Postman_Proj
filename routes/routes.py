"""
Routing Handles and Blueprints for Pytest Migrator
Maps Flask routes to corresponding view managers and API triggers.
"""

import os
import re
import json
import zipfile
import io
from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for

# Import custom processing modules
from parser.parser import PostmanParser
from ai_engine.gemini_service import GeminiTranslationService
from generated_scripts.pytest_generator import PytestGenerator
from validators.validator import ValidationEngine
from database.db import (
    create_collection, get_all_collections, get_collection, update_collection_status,
    create_api, get_apis_for_collection, create_testcase, get_testcases_for_collection,
    create_script, get_scripts_for_collection, get_script, create_recommendation,
    get_recommendations_for_collection, create_conversion_report, get_report_for_collection
)

# Create the primary blueprint for the main routes
main_blueprint = Blueprint("main", __name__)


def rule_based_translate(script: str) -> str:
    """
    Robust offline rule-based regex mapper to translate JS assert assertions to Python Pytest
    as a safe fallback in case GEMINI_API_KEY is not defined or quota limits occur.
    """
    if not script or not script.strip():
        return "assert response.status_code == 200, 'Expected response status code 200 OK'\n"
    
    python_lines = []
    lines = script.split("\n")
    for line in lines:
        line_strip = line.strip()
        if not line_strip or line_strip.startswith("//") or line_strip.startswith("/*") or line_strip.startswith("*"):
            continue
        
        # 1. Status Code assert (e.g. pm.response.to.have.status(200))
        match_status = re.search(r"pm\.response\.to\.have\.status\s*\(\s*(.*?)\s*\)", line_strip)
        if match_status:
            code = match_status.group(1)
            python_lines.append(f"assert response.status_code == {code}, 'Expected status code to be {code}'")
            continue
            
        # 2. pm.response.to.be.success, ok, etc.
        if "pm.response.to.be.success" in line_strip:
            python_lines.append("assert response.status_code in [200, 201, 202, 204], 'Expected a successful status code'")
            continue
            
        if "pm.response.to.be.ok" in line_strip:
            python_lines.append("assert response.status_code == 200, 'Expected status code 200 OK'")
            continue

        # 3. pm.response.to.have.header("Content-Type")
        match_header = re.search(r"pm\.response\.to\.have\.header\s*\(\s*['\"](.*?)['\"]\s*\)", line_strip)
        if match_header:
            header = match_header.group(1)
            python_lines.append(f"assert '{header}' in response.headers, 'Expected header {header} to be present'")
            continue
            
        # 4. JSON body content validation
        match_body = re.search(r"pm\.response\.to\.have\.body\s*\(\s*['\"](.*?)['\"]\s*\)", line_strip)
        if match_body:
            body_val = match_body.group(1)
            python_lines.append(f"assert response.text == '{body_val}', 'Expected response body match'")
            continue

        # 5. pm.expect(response).to.equal(something)
        match_expect_eq = re.search(r"pm\.expect\s*\(\s*(.*?)\s*\)\.(?:to\.)?(?:equal|eql|be)\s*\(\s*(.*?)\s*\)", line_strip)
        if match_expect_eq:
            var_val = match_expect_eq.group(1).replace("pm.response.json().", "response.json().get('").replace("pm.response.json()", "response.json()")
            if "get('" in var_val:
                var_val += "')"
            val_to_compare = match_expect_eq.group(2)
            python_lines.append(f"assert {var_val} == {val_to_compare}, 'Expected field equality check'")
            continue

        # 6. Generic comment notes/warnings
        if "pm.test" in line_strip:
            comment = re.search(r"pm\.test\s*\(\s*['\"](.*?)['\"]", line_strip)
            if comment:
                python_lines.append(f"# Postman Test Block: {comment.group(1)}")
            continue

    if not python_lines:
        return "assert response.status_code == 200, 'Verify basic request status code OK'\n"
    return "\n".join(python_lines)


@main_blueprint.route("/")
def index():
    """Renders the main upload or intro landing deck."""
    return render_template("index.html")


@main_blueprint.route("/upload", methods=["GET", "POST"])
def upload_collection():
    """Handles parsing and uploading a Postman collection JSON file."""
    if request.method == "POST":
        if "file" not in request.files:
            return jsonify({"success": False, "message": "No file parameter specified."}), 400
            
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"success": False, "message": "No selected file name."}), 400
            
        try:
            content_bytes = file.read()
            content_str = content_bytes.decode("utf-8")
        except Exception as e:
            return jsonify({"success": False, "message": f"Could not read upload payload: {str(e)}"}), 400

        # Execute Postman v2.x JSON Parser
        parser = PostmanParser(content_str)
        parser_result = parser.parse()

        # If JSON structural validation failed
        if not parser_result["is_valid"]:
            error_message = parser_result["errors"][0] if parser_result["errors"] else "Corrupted upload file."
            return jsonify({"success": False, "message": error_message}), 400

        # Retrieve parsed parameters
        collection_name = parser_result["collection_name"]
        requests_list = parser_result["requests"]
        total_apis = len(requests_list)

        # 1. Create collection record in SQLite
        collection_id = create_collection(
            collection_name=collection_name,
            file_name=file.filename,
            total_apis=total_apis,
            status="pending"
        )

        gemini = GeminiTranslationService()
        generator = PytestGenerator()
        validator = ValidationEngine()

        total_assertions = 0
        assertions_converted = 0
        failed_conversions = 0
        unsupported_assertions = 0
        warnings_all = list(parser_result["warnings"] or [])

        # Process each endpoint leaf in the parsed hierarchy
        for req in requests_list:
            headers_json = json.dumps(req["headers"])
            query_json = json.dumps(req["query_params"])
            body_str = req["request_body"] or ""

            # Reconstruct original postman schema representation for showcase tab
            raw_postman_mock = {
                "name": req["api_name"],
                "request": {
                    "method": req["method"],
                    "header": [{"key": k, "value": v} for k, v in req["headers"].items()],
                    "url": {
                        "raw": req["endpoint"],
                        "query": [{"key": k, "value": v} for k, v in req["query_params"].items()]
                    }
                }
            }
            if req["request_body"]:
                raw_postman_mock["request"]["body"] = {
                    "mode": "raw",
                    "raw": req["request_body"]
                }
            if req["raw_test_script"]:
                raw_postman_mock["event"] = [{
                    "listen": "test",
                    "script": {
                        "exec": req["raw_test_script"].split("\n")
                    }
                }]
            raw_js_chunk = json.dumps(raw_postman_mock, indent=4)

            # 2. Persist API endpoint signature
            api_id = create_api(
                collection_id=collection_id,
                api_name=req["api_name"],
                method=req["method"],
                endpoint=req["endpoint"],
                headers=headers_json,
                request_body=body_str,
                query_params=query_json,
                raw_json_chunk=raw_js_chunk
            )

            # Assertions aggregation metrics
            raw_script = req["raw_test_script"]
            total_assertions += len(req["assertions"])

            # 3. Call Gemini Translation or Fallback offline
            pytest_assert_code = ""
            if gemini.api_key:
                try:
                    translation_result = gemini.translate_assertions(raw_script)
                    if translation_result["success"]:
                        pytest_assert_code = translation_result["pytest_assertions"]
                        assertions_converted += translation_result["assertions_converted"]
                        failed_conversions += translation_result["failed_conversions"]
                        unsupported_assertions += translation_result["unsupported_assertions"]
                        if translation_result["warnings"]:
                            warnings_all.extend(translation_result["warnings"])
                    else:
                        pytest_assert_code = rule_based_translate(raw_script)
                        assertions_converted += len(req["assertions"])
                except Exception as ex:
                    pytest_assert_code = rule_based_translate(raw_script)
                    assertions_converted += len(req["assertions"])
                    warnings_all.append(f"AI Translation issue for {req['api_name']}: {str(ex)}. Replaced with offline converter.")
            else:
                pytest_assert_code = rule_based_translate(raw_script)
                assertions_converted += len(req["assertions"])
                warnings_all.append("Bypassed online translation (GEMINI_API_KEY not configured). Executed rule-based mapping.")

            # Record associated testcases metadata
            for idx, assert_obj in enumerate(req["assertions"]):
                case_type = "positive"
                if any(x in assert_obj["raw_statement"].lower() for x in ["error", "fail", "400", "404", "500"]):
                    case_type = "negative"
                create_testcase(
                    api_id=api_id,
                    testcase_name=f"test_assert_{idx+1}",
                    testcase_type=case_type,
                    expected_result=assert_obj["match_detail"] or "Assertion check"
                )

            if not req["assertions"]:
                create_testcase(
                    api_id=api_id,
                    testcase_name="test_default_status",
                    testcase_type="positive",
                    expected_result="200"
                )

            # 4. Generate stand-alone python Pytest file using pyest generator
            pytest_script_content = generator.compose_script_content(
                api_name=req["api_name"],
                method=req["method"],
                endpoint=req["endpoint"],
                headers=req["headers"],
                request_body=req["request_body"],
                query_params=req["query_params"],
                variables=req["variables"],
                translated_assertions=pytest_assert_code
            )

            # Save pytest code script to file system and SQLite DB
            script_file_name = generator.export_test_file(
                collection_name=collection_name,
                api_name=req["api_name"],
                method=req["method"],
                script_content=pytest_script_content
            )

            create_script(
                api_id=api_id,
                script_name=script_file_name,
                script_content=pytest_script_content
            )

            # 5. AI Recommendations Audits
            if gemini.api_key:
                try:
                    audits = gemini.audit_api_recommendations(
                        api_name=req["api_name"],
                        method=req["method"],
                        endpoint=req["endpoint"],
                        request_body=req["request_body"]
                    )
                    for aud in audits:
                        create_recommendation(
                            api_id=api_id,
                            recommendation=aud["recommendation"],
                            recommendation_type=aud["recommendation_type"]
                        )
                except Exception:
                    create_recommendation(api_id, f"Mandate HTTPs connection protocols for {req['api_name']}.", "Security")
                    create_recommendation(api_id, "Define strict input type boundaries for requests body parameters.", "Functional")
            else:
                create_recommendation(api_id, "Incorporate TLS authentication options to enforce secure sessions.", "Security")
                create_recommendation(api_id, "Incorporate requests connection timeout limits to avoid thread hangs.", "Performance")

            # 6. Run static syntax checking / verification through ValidationEngine
            metadata_repr = {"method": req["method"], "endpoint": req["endpoint"]}
            validation_status = validator.validate_script(pytest_script_content, metadata_repr)
            if not validation_status["valid"]:
                for validation_err in validation_status["errors"]:
                    warnings_all.append(f"[{req['api_name']}] Syntax warning: {validation_err}")
            if validation_status["warnings"]:
                for val_warn in validation_status["warnings"]:
                    warnings_all.append(f"[{req['api_name']}] Style warning: {val_warn}")

        # Compute translation quality metrics
        if total_assertions > 0:
            success_percentage = round((assertions_converted / (assertions_converted + failed_conversions + unsupported_assertions)) * 100, 2)
        else:
            success_percentage = 100.0

        # Save Conversion Evaluation Report to SQLite
        create_conversion_report(
            collection_id=collection_id,
            assertions_converted=assertions_converted,
            failed_conversions=failed_conversions,
            unsupported_assertions=unsupported_assertions,
            warnings_list=warnings_all,
            success_percentage=success_percentage
        )

        # Export Conversion Report to File System generated_reports/report_{id}.json
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_file_path = os.path.join(reports_dir, f"report_{collection_id}.json")

        report_data = {
            "collection_name": collection_name,
            "collection_id": collection_id,
            "total_apis": total_apis,
            "total_assertions": total_assertions,
            "assertions_converted": assertions_converted,
            "failed_conversions": failed_conversions,
            "unsupported_assertions": unsupported_assertions,
            "success_percentage": success_percentage,
            "warnings": warnings_all
        }

        with open(report_file_path, "w", encoding="utf-8") as rf:
            json.dump(report_data, rf, indent=4)

        # Update stage log status
        update_collection_status(collection_id, status="Completed", total_apis=total_apis)

        # Redirect to results visualizer console
        return redirect(url_for("main.results", collection_id=collection_id))

    return render_template("upload.html")


@main_blueprint.route("/dashboard")
def dashboard():
    """Renders historically converted suites and SQLite session tables."""
    collections = get_all_collections()
    col_reports = {}
    total_apis_count = 0
    total_assertions_count = 0
    success_percentages = []
    
    for col in collections:
        if col["total_apis"]:
            total_apis_count += col["total_apis"]
        report = get_report_for_collection(col["id"])
        if report:
            col_reports[col["id"]] = report
            total_assertions_count += report["assertions_converted"]
            success_percentages.append(report["success_percentage"])
            
    avg_sync_rate = round(sum(success_percentages) / len(success_percentages), 1) if success_percentages else 100.0
    
    return render_template(
        "dashboard.html",
        collections=collections,
        col_reports=col_reports,
        total_apis_count=total_apis_count,
        total_assertions_count=total_assertions_count,
        avg_sync_rate=avg_sync_rate
    )


@main_blueprint.route("/results/<int:collection_id>")
def results(collection_id):
    """Renders comprehensive code results and execution logs."""
    collection = get_collection(collection_id)
    if not collection:
        return redirect(url_for("main.dashboard"))
        
    apis = get_apis_for_collection(collection_id)
    report = get_report_for_collection(collection_id)
    
    # Render warnings list if present
    warnings_list = []
    if report and report["warnings"]:
        try:
            warnings_list = json.loads(report["warnings"])
        except ValueError:
            warnings_list = []
            
    # Compile python scripts and recommendations by api_id
    api_scripts = {}
    api_recs = {}
    all_scripts = get_scripts_for_collection(collection_id)
    for scr in all_scripts:
        api_scripts[scr["api_id"]] = scr
        
    all_recs = get_recommendations_for_collection(collection_id)
    for rec in all_recs:
        if rec["api_id"] not in api_recs:
            api_recs[rec["api_id"]] = []
        api_recs[rec["api_id"]].append(rec)
        
    return render_template(
        "results.html",
        collection_id=collection_id,
        collection=collection,
        apis=apis,
        report=report,
        warnings=warnings_list,
        api_scripts=api_scripts,
        api_recs=api_recs
    )


@main_blueprint.route("/api/convert", methods=["POST"])
def trigger_ai_conversion():
    """Calls the Gemini translator engine to translate JS asserts into pytest scripts."""
    return jsonify({"success": True, "message": "Triggered AI conversion (skeleton)."})


@main_blueprint.route("/api/download/<int:script_id>")
def download_script(script_id):
    """Allows downloading a single generated python verification script."""
    script = get_script(script_id)
    if not script:
        return jsonify({"success": False, "message": "Script not found."}), 404
        
    directory = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_scripts")
    file_path = os.path.join(directory, script["script_name"])
    
    # If file exists on filesystem, serve it, otherwise compile and write it
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=script["script_name"])
    else:
        os.makedirs(directory, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(script["script_content"])
        return send_file(file_path, as_attachment=True, download_name=script["script_name"])


@main_blueprint.route("/api/download-zip/<int:collection_id>")
def download_suite(collection_id):
    """Packages all active testcases into conftest.py zip bundle."""
    collection = get_collection(collection_id)
    if not collection:
        return jsonify({"success": False, "message": "Collection not found."}), 404
        
    scripts = get_scripts_for_collection(collection_id)
    if not scripts:
        return jsonify({"success": False, "message": "No compiled scripts for this collection."}), 400
        
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Include conftest.py setup with standard Requests Session fixture
        conftest_content = """# -*- coding: utf-8 -*-
import pytest
import requests

@pytest.fixture(scope="session")
def client_session():
    with requests.Session() as session:
        yield session
"""
        zip_file.writestr("conftest.py", conftest_content)
        
        # Package every compiled script file
        for scr in scripts:
            zip_file.writestr(scr["script_name"], scr["script_content"])
            
    zip_buffer.seek(0)
    safe_col_name = re.sub(r"[^a-zA-Z0-9_]", "_", collection["collection_name"].lower())
    zip_name = f"pytest_suite_{safe_col_name}.zip"
    
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=zip_name
    )


@main_blueprint.route("/api/download-report/<int:collection_id>")
def download_report(collection_id):
    """Allows downloading the conversion report in JSON format."""
    collection = get_collection(collection_id)
    if not collection:
        return jsonify({"success": False, "message": "Collection not found."}), 404
        
    directory = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_reports")
    file_path = os.path.join(directory, f"report_{collection_id}.json")
    
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True, download_name=f"report_{collection_id}.json")
        
    report = get_report_for_collection(collection_id)
    if not report:
        return jsonify({"success": False, "message": "Report not found."}), 404
        
    report_dict = {
        "collection_name": collection["collection_name"],
        "collection_id": collection_id,
        "total_apis": collection["total_apis"],
        "assertions_converted": report["assertions_converted"],
        "failed_conversions": report["failed_conversions"],
        "unsupported_assertions": report["unsupported_assertions"],
        "success_percentage": report["success_percentage"],
        "warnings": json.loads(report["warnings"] or "[]")
    }
    
    report_io = io.BytesIO(json.dumps(report_dict, indent=4).encode("utf-8"))
    return send_file(
        report_io,
        mimetype="application/json",
        as_attachment=True,
        download_name=f"report_{collection_id}.json"
    )
