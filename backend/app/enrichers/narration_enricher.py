import re

from app.services.categories import REGEX_TO_CANONICAL

_PAYMENT_METHODS_KEYWORDS = {
    "UPI": ["UPI", "IMPS/P2M", "PHONEPE", "GPAY", "PAYTM"],
    "IMPS": ["IMPS", "IMPS/P2A"],
    "NEFT": ["NEFT"],
    "RTGS": ["RTGS"],
    "BBPS": ["BBPS"],
    "CARD": ["CARD", "DEBIT CARD", "CREDIT CARD", "POS", "VPA/MMT", "VPA/MMS"],
    "CASH": ["CASH DEP", "CASH WDL"],
    "CHEQUE": ["CHQ", "CHEQUE", "CQ", "CLR"],
    "DIVIDEND": ["DIVIDEND", "DIV"],
    "INTEREST": ["INT PAID", "INT CR"],
    "ECS": ["ECS"],
    "SALARY": ["SALARY"],
    "BILL PAY": ["BILLPAY"],
    "ATM": ["ATM"],
}

_BANK_KEYWORDS = [
    "STATE BANK OF INDIA",
    "HDFC BANK",
    "ICICI BANK",
    "AXIS BANK",
    "YES BANK",
    "KOTAK MAHINDRA BANK",
    "PUNJAB NATIONAL BANK",
    "UNION BANK OF INDIA",
    "CANARA BANK",
    "INDIAN BANK",
    "INDUSIND BANK",
    "FEDERAL BANK",
    "RBL BANK",
    "BANDHAN BANK",
    "IDFC FIRST BANK",
    "BANK OF BARODA",
    "UCO BANK",
    "CENTRAL BANK OF INDIA",
    "SBI",
    "HDFC",
    "ICICI",
    "AXIS",
    "KOTAK",
    "PNB",
    "UNION",
    "CANARA",
    "INDUSIND",
    "BOB",
    "UBI",
    "IOB",
    "BOI",
    "CORP",
]

_MERCHANTS_AND_CATEGORIES = {
    "AMAZON": {"merchant": "AMAZON", "category": "E-COMMERCE"},
    "ZOMATO": {"merchant": "ZOMATO", "category": "FOOD_DELIVERY"},
    "SWIGGY": {"merchant": "SWIGGY", "category": "FOOD_DELIVERY"},
    "GOOGLE PAY": {
        "merchant": "GOOGLE PAY",
        "category": "PAYMENT_APP",
        "payment_gateway": "GOOGLE",
    },
    "PHONEPE": {
        "merchant": "PHONEPE",
        "category": "PAYMENT_APP",
        "payment_gateway": "PHONEPE",
    },
    "PAYTM": {
        "merchant": "PAYTM",
        "category": "PAYMENT_APP",
        "payment_gateway": "PAYTM",
    },
    "RELIANCE": {"merchant": "RELIANCE", "category": "RETAIL"},
    "VODAFONE": {"merchant": "VODAFONE", "category": "TELECOM_BILL"},
    "AIRTEL": {"merchant": "AIRTEL", "category": "TELECOM_BILL"},
    "JIO": {"merchant": "JIO", "category": "TELECOM_BILL"},
    "IRCTC": {"merchant": "IRCTC", "category": "TRAVEL"},
    "UBER": {"merchant": "UBER", "category": "TRANSPORT"},
    "OLA": {"merchant": "OLA", "category": "TRANSPORT"},
    "NETFLIX": {"merchant": "NETFLIX", "category": "SUBSCRIPTION"},
    "SPOTIFY": {"merchant": "SPOTIFY", "category": "SUBSCRIPTION"},
    "CRED": {
        "merchant": "CRED",
        "category": "LOAN_REPAYMENT",
        "payment_gateway": "CRED",
    },
    "ELECTRICITY": {"category": "UTILITY_BILL"},
    "WATER": {"category": "UTILITY_BILL"},
    "GAS": {"category": "UTILITY_BILL"},
    "LOAN EMI": {"category": "LOAN_REPAYMENT"},
    "RENT": {"category": "HOUSING"},
    "SALARY": {"category": "INCOME"},
    "SCHOOL FEES": {"category": "EDUCATION"},
    "INSURANCE": {"category": "INSURANCE"},
    "INVESTMENT": {"category": "INVESTMENT"},
    "SIP": {"category": "INVESTMENT"},
    "MUTUAL FUND": {"category": "INVESTMENT"},
    "FOOD": {"category": "FOOD_EXPENSE"},
    "MEDICAL": {"category": "HEALTH_EXPENSE"},
    "PHARMACY": {"category": "HEALTH_EXPENSE"},
    "CHEMIST": {"category": "HEALTH_EXPENSE"},
    "ECOM": {"category": "E-COMMERCE"},
    "GROCERY": {"category": "GROCERIES"},
    "FUEL": {"category": "TRANSPORT_FUEL"},
    "TAX": {"category": "TAXES"},
    "LOAN DISB": {"category": "LOAN_DISBURSEMENT"},
}


def extract_possible_account_numbers(description):
    if not description:
        return []

    numbers = set()

    account_pattern = re.findall(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4,12}\b", description)
    for match in account_pattern:
        numbers.add(match.replace(" ", "").replace("-", ""))

    long_number_pattern = re.findall(r"\b\d{8,20}\b", description)
    for match in long_number_pattern:
        if len(match) <= 20:
            numbers.add(match)

    upi_ref_pattern = re.findall(
        r"(?:UPI|REF|TXN)[\s\-:]*(\d{8,16})", description, re.IGNORECASE
    )
    numbers.update(upi_ref_pattern)

    transfer_ref_pattern = re.findall(
        r"(?:NEFT|RTGS|IMPS)[\s\-:]*[A-Z]*(\d{8,16})", description, re.IGNORECASE
    )
    numbers.update(transfer_ref_pattern)

    return sorted(numbers, key=lambda x: -len(x))


def analyze_narration_details(narration):
    result = {
        "payment_method": None,
        "upi_id": None,
        "transaction_reference": None,
        "receiver_details": {"name": None, "account": None, "vpa": None},
        "bank_peer": None,
        "merchant": None,
        "category": [],
        "remarks": [],
        "payment_gateway": None,
    }

    if not narration:
        return result

    narration_upper = narration.upper()

    upi_structured_match = re.search(
        r"UPI\/(?P<upi_id>[^\/]+)\/(?P<remark>[^\/]+)\/(?P<bank>[^\/]+)\/(?P<txn_id>[^\s\/]+)",
        narration_upper,
    )
    if upi_structured_match:
        result["payment_method"] = "UPI"
        result["upi_id"] = upi_structured_match.group("upi_id").strip()
        result["transaction_reference"] = upi_structured_match.group("txn_id").strip()
        result["bank_peer"] = upi_structured_match.group("bank").strip()
        result["remarks"].append(upi_structured_match.group("remark").strip())
        return result

    vsi_pattern = re.search(
        r"VSI\/(?P<merchant>[^\/]+)\/(?P<datetime>[^\/]+)\/(?P<txn_id>[^\s\/]+)",
        narration_upper,
    )
    if vsi_pattern:
        result["payment_method"] = "CARD"
        result["merchant"] = vsi_pattern.group("merchant").strip()
        result["transaction_reference"] = vsi_pattern.group("txn_id").strip()
        return result

    imps_transfer_match = re.search(
        r"IMPS/(\d{10,})/([^/]+)/([^/]+)", narration_upper
    )
    if imps_transfer_match:
        result["payment_method"] = "IMPS"
        result["transaction_reference"] = imps_transfer_match.group(1).strip()
        result["receiver_details"]["name"] = imps_transfer_match.group(2).strip()
        result["bank_peer"] = imps_transfer_match.group(3).strip()
        result["remarks"].append("IMPS TRANSFER")
        return result

    for method, keywords in _PAYMENT_METHODS_KEYWORDS.items():
        if any(kw in narration_upper for kw in keywords):
            result["payment_method"] = method
            break

    if not result["upi_id"]:
        upi_id_match = re.search(
            r"[a-z0-9.\-_]+@[a-z]{2,}", narration_upper, re.IGNORECASE
        )
        if upi_id_match:
            result["upi_id"] = upi_id_match.group().strip()
            result["receiver_details"]["vpa"] = result["upi_id"]

    if not result["transaction_reference"]:
        txn_ref_patterns = [
            r"\b(?:RRN|REF|TRF|TXN|UTR|UTR NO|NFS|CMS|ID)\s*[:\.]?\s*([A-Z0-9]{10,25})\b",
            r"\b(YBL|AXI|ICI|KOT|PNB|PYTM|PTM|HDFC|ICICI|YES|SBI)[a-zA-Z0-9]{6,25}\b",
            r"\b(?:\d{10,})\b",
        ]
        for pattern in txn_ref_patterns:
            match = re.search(pattern, narration_upper)
            if match:
                try:
                    result["transaction_reference"] = match.group(1).strip()
                except IndexError:
                    result["transaction_reference"] = match.group().strip()
                break

    receiver_patterns = [
        r"(?:TO|FROM|BY)\s+([A-Z0-9\s.&,-_']{3,}(?:\s(?:A/C|ACC|AC|ACCOUNT|NO)\s*\d+)?)\b",
        r"(?:TRANSFER TO|PAYMENT TO)\s+([A-Z\s.&,-_']{3,})",
        r"CR BY\s+([A-Z\s.&,-_']{3,})",
    ]
    for pattern in receiver_patterns:
        match = re.search(pattern, narration_upper)
        if match:
            potential_receiver = match.group(1).strip()
            if re.search(r"\d{6,}", potential_receiver) and not re.search(
                r"[A-Z]{3,}", potential_receiver
            ):
                result["receiver_details"]["account"] = potential_receiver
            else:
                result["receiver_details"]["name"] = potential_receiver
            break

    for bank in _BANK_KEYWORDS:
        if bank in narration_upper:
            result["bank_peer"] = bank
            break

    for keyword, details in _MERCHANTS_AND_CATEGORIES.items():
        if keyword in narration_upper:
            if details.get("merchant") and not result["merchant"]:
                result["merchant"] = details["merchant"]
            if (
                details.get("category")
                and details["category"] not in result["category"]
            ):
                result["category"].append(details["category"])
            if details.get("payment_gateway") and not result["payment_gateway"]:
                result["payment_gateway"] = details["payment_gateway"]

    if "REFUND" in narration_upper and "REFUND" not in result["remarks"]:
        result["remarks"].append("REFUND")
    if "TRANSFER" in narration_upper and "TRANSFER" not in result["remarks"]:
        result["remarks"].append("TRANSFER")
    if "DEBITED" in narration_upper and "DEBITED" not in result["remarks"]:
        result["remarks"].append("DEBITED")
    if "CREDITED" in narration_upper and "CREDITED" not in result["remarks"]:
        result["remarks"].append("CREDITED")

    possible_accounts = extract_possible_account_numbers(narration_upper)
    if possible_accounts:
        result["receiver_details"]["account"] = possible_accounts[0]

    result["category"] = list(
        dict.fromkeys(REGEX_TO_CANONICAL.get(c, c) for c in result["category"])
    )

    return result
