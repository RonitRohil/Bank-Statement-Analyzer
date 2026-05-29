import os
import uuid
from flask import jsonify, request
from werkzeug.utils import secure_filename

from app.models.analyzeModel import AnalyzeModel
from app.config.config import Config

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xlsx", ".xls"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


class AnalyzeController:
    @staticmethod
    def analyze_statement():
        # 1. Validate file presence
        if "file" not in request.files:
            return jsonify({"success": False, "message": "No file uploaded."}), 400

        uploaded_file = request.files["file"]
        if not uploaded_file.filename:
            return jsonify({"success": False, "message": "Invalid file."}), 400

        # 2. Validate file extension
        ext = os.path.splitext(secure_filename(uploaded_file.filename))[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({
                "success": False,
                "message": f"Unsupported file type '{ext}'. Allowed: PDF, CSV, XLSX, XLS."
            }), 400

        # 3. Validate file size
        uploaded_file.seek(0, 2)
        file_size = uploaded_file.tell()
        uploaded_file.seek(0)
        if file_size > Config.MAX_UPLOAD_SIZE:
            max_mb = Config.MAX_UPLOAD_SIZE // (1024 * 1024)
            return jsonify({
                "success": False,
                "message": f"File too large. Maximum allowed size is {max_mb} MB."
            }), 400

        # 4. Save with UUID prefix to prevent filename collisions
        safe_name = f"{uuid.uuid4().hex}_{secure_filename(uploaded_file.filename)}"
        file_path = os.path.join(UPLOAD_FOLDER, safe_name)
        uploaded_file.save(file_path)

        # 5. Analyze — always clean up the file after, success or failure
        try:
            data = {"local_file_path": file_path}
            analyzer = AnalyzeModel()
            result, status_code = analyzer.bank_statement_analysis(data)
            return result, status_code
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
