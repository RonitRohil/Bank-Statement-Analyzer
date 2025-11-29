from flask import Blueprint
from  app.controllers.analyzeController import AnalyzeController

analyze_statement_bp = Blueprint('analyze_statement', __name__)

analyze_statement_bp.route('/analyze/bank/statement', methods=['POST'])(AnalyzeController.analyze_statement)