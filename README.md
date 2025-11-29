# Bank-Statement-Analyzer

## PDF / Excel / CSV Parser • Flask API • React + TypeScript Frontend

This repository provides a complete bank statement analysis system built with a Flask backend and a React (TypeScript + Vite) frontend.

It extracts, normalizes, and analyzes transactions from financial documents including PDF, Excel, and CSV statements.

The system detects:

- Dates
- Credit/Debit amounts
- Narration fields
- UPI IDs
- Payment methods
- Reference numbers
- Metadata (account numbers, bank name, statement period)
- Confidence score (0–1) for each transaction

This project is designed as a portfolio-grade full-stack application showcasing backend engineering, document parsing, and frontend integration.

## 🚀 Features

### 🧾 Supported Formats

- PDF (digital tables)
- Excel (.xlsx, .xls)
- CSV

### 📘 Smart Extraction

- Automatic header row detection
- Dynamic column mapping
- Date parsing (handles multiple formats)
- Amount normalization
- CR/DR identification

### 🔍 Narration Analysis

Extracts:

- UPI ID
- Payment method (UPI / IMPS / NEFT / CARD / CASH etc.)
- RRN / UTR / TXN references
- Basic merchant detection

### 🎯 Confidence Scoring

Each transaction is scored based on:
- Date correctness
- Amount accuracy
- Narration quality
- Transaction type detection

### 🧠 Metadata Extraction
- Account number
- Bank name (from PDF text)
- Statement date range

### 🖥 Frontend UI
- File upload
- Results preview
- Transaction table
- Summary view (Total credit, total debit, average confidence)

## 📁 Project Structure
```
BANK-STATEMENT-ANALYZER/
│
├── backend/
│   ├── app/
│   │   ├── config/
│   │   ├── constants/
│   │   ├── controllers/
│   │   │   ├── analyzeController.py
│   │   ├── models/
│   │   │   ├── analyzeModel.py
│   │   ├── routes/
│   │   │   ├── analyze.py
│   │   ├── __init__.py
│   ├── uploads/
│   ├── requirements.txt
│   ├── .env
│   ├── run.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   ├── App.tsx
│   │   ├── index.tsx
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── .env.local
│
├── samples/ (optional)
│
├── README.md
└── .gitignore
```


## 🛠 Backend Setup (Flask)

### 1. Go to backend folder
``` bash
cd backend
```

### 2. Create and activate virtual environment
``` bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
``` bash
pip install -r requirements.txt
```

### 4. Create .env file
Example

```env
FLASK_APP=run.py
FLASK_ENV=development
CORS_URLS=["http://localhost:3000"]
FLASK_DEBUG=True
```

### 5. Run backend
``` bash
flask run 
```

or

``` bash
python run.py
```

Backend will start at: 👉 http://localhost:5000

## 🎨 Frontend Setup (React + TypeScript)

### 1. Go to frontend folder
``` bash
cd frontend
```

### 2. Install dependencies
``` bash
npm install
```

### 3. Create .env.local
``` bash
VITE_API_URL=http://localhost:5000
```

### 4. Run frontend
``` bash
npm run dev
```

Frontend will start at:
👉 http://localhost:3000

## 📡 API Endpoint
POST /api/analyze

### Form-Data:

| Key         | Type   | Required | Description   |
| ----------- | ------ | -------- | ------------- |
| file        | File   | Yes      | PDF/Excel/CSV |

### cURL
``` c
curl --location 'http://localhost:5000/api/analyze/bank/statement' \
--form 'file=@"/C:/Users/ronit/Downloads/SBI CSR HUDCO.xls.xlsx"'
```

### Example Response

``` json
{
    "message": "3 transactions parsed from Excel/CSV",
    "result": {
        "account_info": {
            "account_holder": "BRAMHRISHI MISSION SAMITI",
            "account_number": "2025-03-01",
            "bank_name": "Acco",
            "branch": "BHEDAGHAT VB Drawing Power",
            "email": null,
            "ifsc_code": "SBIN0007207",
            "phone": null,
            "statement_period": {
                "from": "2025-05-02",
                "to": "2025-05-02"
            }
        },
        "confidence_summary": {
            "high_confidence_txns": 3,
            "overall_score": 1.0,
            "total_transactions": 3
        },
        "merchant_insights": {
            "38976288": {
                "avg_amount": 177.0,
                "common_days": [],
                "count": 1,
                "first_seen": "2025-02-13",
                "last_seen": "2025-02-13",
                "median_amount": 177.0,
                "std_amount": null
            },
            "IDF-XX991-CASHFREE": {
                "avg_amount": 1.0,
                "common_days": [],
                "count": 1,
                "first_seen": "2025-02-13",
                "last_seen": "2025-02-13",
                "median_amount": 1.0,
                "std_amount": null
            },
            "KMB-XX325-CASHFREE": {
                "avg_amount": 1.0,
                "common_days": [],
                "count": 1,
                "first_seen": "2025-02-05",
                "last_seen": "2025-02-05",
                "median_amount": 1.0,
                "std_amount": null
            }
        },
        "transactions": [
            {
                "account": null,
                "amount": 1.0,
                "balance": 5003.0,
                "bank_peer": "BANK ACCO--",
                "category": [],
                "confidence_score": 1.0,
                "merchant": null,
                "narration": "BY TRANSFER-INB IMPS/503618836110/kmb-XX325-Cashfree/Bank Acco--",
                "payment_gateway": null,
                "payment_method": "IMPS",
                "receiver_details": {
                    "account": null,
                    "name": "KMB-XX325-CASHFREE",
                    "vpa": null
                },
                "remarks": [
                    "IMPS TRANSFER"
                ],
                "transaction_date": "2025-02-05",
                "transaction_reference": "503618836110",
                "transaction_type": "CREDIT",
                "upi_id": null
            },
            {
                "account": null,
                "amount": 177.0,
                "balance": 4826.0,
                "bank_peer": null,
                "category": [],
                "confidence_score": 1.0,
                "merchant": null,
                "narration": "CHEQUE BOOK ISSUE CHARGE---38976288",
                "payment_gateway": null,
                "payment_method": "CHEQUE",
                "receiver_details": {
                    "account": "38976288",
                    "name": null,
                    "vpa": null
                },
                "remarks": [],
                "transaction_date": "2025-02-13",
                "transaction_reference": null,
                "transaction_type": "DEBIT",
                "upi_id": null
            },
            {
                "account": null,
                "amount": 1.0,
                "balance": 4827.0,
                "bank_peer": "BANKACCOU--",
                "category": [],
                "confidence_score": 1.0,
                "merchant": null,
                "narration": "BY TRANSFER-INB IMPS/504415336069/IDF-XX991-CASHFREE/BankAccou--",
                "payment_gateway": null,
                "payment_method": "IMPS",
                "receiver_details": {
                    "account": null,
                    "name": "IDF-XX991-CASHFREE",
                    "vpa": null
                },
                "remarks": [
                    "IMPS TRANSFER"
                ],
                "transaction_date": "2025-02-13",
                "transaction_reference": "504415336069",
                "transaction_type": "CREDIT",
                "upi_id": null
            }
        ]
    },
    "status_code": 200,
    "success": 1
}
```

## 🚧 Future Improvements

- OCR for scanned PDFs
- Merchant categorization using ML
- Insights dashboard (monthly spending, category charts)
- Export parsed transactions to CSV/Excel
- User authentication

## 👨‍💻 Author

**Ronit Jain**

Backend Engineer | Python | Node.js | Financial Automation | PDF/Excel Parsing

GitHub: https://github.com/RonitRohil

LinkedIn: https://www.linkedin.com/in/ronitjain0402/

## ⭐ Support

If you like this project, give it a star ⭐ on GitHub — it motivates me to build more tools.