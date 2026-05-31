from flask import Blueprint, jsonify
from  app.controllers.analyzeController import AnalyzeController

analyze_statement_bp = Blueprint('analyze_statement', __name__)

analyze_statement_bp.route('/analyze/bank/statement', methods=['POST'])(AnalyzeController.analyze_statement)

@analyze_statement_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "service": "bank-statement-analyzer"
    }), 200