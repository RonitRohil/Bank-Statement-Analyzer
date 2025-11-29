from flask import jsonify, request
from werkzeug.utils import secure_filename
import os
from app.models.analyzeModel import AnalyzeModel

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class AnalyzeController:
    @staticmethod
    def analyze_statement():
        if "file" not in request.files:
                return jsonify({"success": False, "message": "No file uploaded."}), 400

        uploaded_file = request.files["file"]
        if uploaded_file.filename == "":
            return jsonify({"success": False, "message": "Invalid file."}), 400

        # 2. Save file to uploads/
        filename = secure_filename(uploaded_file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)   
        uploaded_file.save(file_path)

        # 3. Create input payload for AnalyzeModel
        data = {
            "local_file_path": file_path
        }

        analyzer = AnalyzeModel()
        result, status_code = analyzer.bank_statement_analysis(data)

        # 4. analyzer already returns proper JSON + status code → return directly
        return result, status_code
