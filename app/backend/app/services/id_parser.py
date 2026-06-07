"""
ID card parser - extract gender, birth date, age from Chinese ID card number.
"""
import datetime
from typing import Optional, Tuple

def parse_id_card(id_card: str) -> dict:
    """
    Parse Chinese ID card number.
    Returns: {gender, birth_date, age, is_valid}
    """
    result = {
        "gender": "",
        "birth_date": "",
        "age": None,
        "is_valid": False
    }
    
    if not id_card:
        return result
    
    id_str = str(id_card).strip().replace(" ", "")
    
    # Try 18-digit first
    if len(id_str) == 18:
        try:
            year = int(id_str[6:10])
            month = int(id_str[10:12])
            day = int(id_str[12:14])
            
            result["birth_date"] = f"{year}-{month:02d}-{day:02d}"
            result["gender"] = "男" if int(id_str[16]) % 2 == 1 else "女"
            
            # Calculate age
            today = datetime.date.today()
            birth = datetime.date(year, month, day)
            result["age"] = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            result["is_valid"] = True
        except (ValueError, IndexError):
            pass
    
    # Try 15-digit
    elif len(id_str) == 15:
        try:
            year = 1900 + int(id_str[6:8])
            month = int(id_str[8:10])
            day = int(id_str[10:12])
            
            result["birth_date"] = f"{year}-{month:02d}-{day:02d}"
            result["gender"] = "男" if int(id_str[14]) % 2 == 1 else "女"
            
            today = datetime.date.today()
            birth = datetime.date(year, month, day)
            result["age"] = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
            result["is_valid"] = True
        except (ValueError, IndexError):
            pass
    
    return result


def infer_from_id_card(id_card: str, existing_data: dict = None) -> dict:
    """
    Infer gender, birth_date, age from ID card.
    Only fills in missing values (doesn't override existing data).
    """
    parsed = parse_id_card(id_card)
    result = existing_data.copy() if existing_data else {}
    
    if parsed["is_valid"]:
        if not result.get("gender") and parsed["gender"]:
            result["gender"] = parsed["gender"]
        if not result.get("birth_date") and parsed["birth_date"]:
            result["birth_date"] = parsed["birth_date"]
        if result.get("age") is None and parsed["age"] is not None:
            result["age"] = parsed["age"]
    
    return result
