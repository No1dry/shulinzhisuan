import re
from typing import List, Dict, Any, Tuple
from datetime import datetime

class DataValidator:
    """Data validation service for resident records"""
    
    @staticmethod
    def validate_id_card(id_card: str) -> Tuple[bool, str]:
        """Validate Chinese ID card number (15 or 18 digits)"""
        if not id_card:
            return False, "身份证号不能为空"
        
        id_card = str(id_card).strip().upper()
        
        # Remove spaces
        id_card = id_card.replace(" ", "").replace("\t", "")
        
        if len(id_card) == 15:
            # 15-digit ID card
            if not re.match(r'^\d{15}$', id_card):
                return False, "15位身份证号必须为纯数字"
            return True, ""
        
        elif len(id_card) == 18:
            # 18-digit ID card
            if not re.match(r'^\d{17}[\dX]$', id_card):
                return False, "18位身份证号格式错误（前17位数字，最后一位数字或X）"
            
            # Validate check digit
            weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
            check_codes = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
            
            try:
                sum_value = sum(int(id_card[i]) * weights[i] for i in range(17))
                if check_codes[sum_value % 11] != id_card[17]:
                    return False, "身份证号校验位错误"
            except (ValueError, IndexError):
                return False, "身份证号格式异常"
            
            return True, ""
        
        else:
            return False, f"身份证号长度错误：当前{len(id_card)}位，应为15或18位"
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, str]:
        """Validate Chinese mobile phone number"""
        if not phone:
            return True, ""  # Phone can be empty
        
        phone = str(phone).strip()
        phone = phone.replace(" ", "").replace("-", "").replace("\t", "")
        
        # Chinese mobile number pattern
        pattern = r'^1[3-9]\d{9}$'
        if not re.match(pattern, phone):
            return False, "手机号格式错误：应为11位数字，以1开头"
        
        return True, ""
    
    @staticmethod
    def validate_name(name: str) -> Tuple[bool, str]:
        """Validate name field"""
        if not name or not str(name).strip():
            return False, "姓名不能为空"
        
        name = str(name).strip()
        if len(name) < 1 or len(name) > 20:
            return False, "姓名长度应在1-20个字符之间"
        
        # Check for invalid characters
        if re.search(r'[0-9@#$%^&*()_+=\[\]{}|;:",./<>?]', name):
            return False, "姓名包含非法字符"
        
        return True, ""
    
    @staticmethod
    def validate_gender(gender: str) -> Tuple[bool, str]:
        """Validate gender field"""
        if not gender:
            return True, ""  # Can be empty
        
        gender = str(gender).strip()
        valid_genders = ["男", "女", "M", "F", "Male", "Female", "male", "female"]
        if gender not in valid_genders:
            return False, "性别应为：男/女"
        
        return True, ""
    
    @staticmethod
    def validate_age(age) -> Tuple[bool, str]:
        """Validate age field"""
        if age is None or age == "":
            return True, ""
        
        try:
            age_val = int(float(str(age)))
            if age_val < 0 or age_val > 150:
                return False, "年龄应在0-150之间"
            return True, ""
        except (ValueError, TypeError):
            return False, "年龄必须为有效数字"
    
    @staticmethod
    def validate_row(row: Dict[str, str], standard_map: Dict[str, str]) -> List[Dict]:
        """Validate a single row and return list of errors"""
        errors = []
        
        # Build reverse mapping: standard_field -> original_header
        reverse_map = {v: k for k, v in standard_map.items()}
        
        # Validate name
        name_header = reverse_map.get("name")
        if name_header and name_header in row:
            valid, msg = DataValidator.validate_name(row[name_header])
            if not valid:
                errors.append({
                    "field": name_header,
                    "standard_field": "name",
                    "error_type": "name",
                    "error_message": msg,
                    "original_value": row[name_header]
                })
        
        # Validate ID card
        id_header = reverse_map.get("id_card")
        if id_header and id_header in row and row[id_header]:
            valid, msg = DataValidator.validate_id_card(row[id_header])
            if not valid:
                errors.append({
                    "field": id_header,
                    "standard_field": "id_card",
                    "error_type": "id_card",
                    "error_message": msg,
                    "original_value": row[id_header]
                })
        
        # Validate phone
        phone_header = reverse_map.get("phone")
        if phone_header and phone_header in row and row[phone_header]:
            valid, msg = DataValidator.validate_phone(row[phone_header])
            if not valid:
                errors.append({
                    "field": phone_header,
                    "standard_field": "phone",
                    "error_type": "phone",
                    "error_message": msg,
                    "original_value": row[phone_header]
                })
        
        # Validate gender
        gender_header = reverse_map.get("gender")
        if gender_header and gender_header in row and row[gender_header]:
            valid, msg = DataValidator.validate_gender(row[gender_header])
            if not valid:
                errors.append({
                    "field": gender_header,
                    "standard_field": "gender",
                    "error_type": "gender",
                    "error_message": msg,
                    "original_value": row[gender_header]
                })
        
        # Validate age
        age_header = reverse_map.get("age")
        if age_header and age_header in row and row[age_header]:
            valid, msg = DataValidator.validate_age(row[age_header])
            if not valid:
                errors.append({
                    "field": age_header,
                    "standard_field": "age",
                    "error_type": "age",
                    "error_message": msg,
                    "original_value": row[age_header]
                })
        
        return errors
    
    @staticmethod
    def validate_batch(rows: List[Dict], standard_map: Dict[str, str]) -> Dict:
        """Validate batch of rows and return summary"""
        all_errors = []
        error_summary = {"total_rows": len(rows), "error_rows": 0, "total_errors": 0}
        
        for idx, row in enumerate(rows):
            row_errors = DataValidator.validate_row(row, standard_map)
            for err in row_errors:
                err["row_number"] = idx + 1
                all_errors.append(err)
            
            if row_errors:
                error_summary["error_rows"] += 1
                error_summary["total_errors"] += len(row_errors)
        
        return {
            "is_valid": len(all_errors) == 0,
            "errors": all_errors,
            "summary": error_summary
        }
    
    @staticmethod
    def check_duplicates(rows: List[Dict], standard_map: Dict[str, str]) -> List[Dict]:
        """Check for duplicate ID cards in upload data"""
        reverse_map = {v: k for k, v in standard_map.items()}
        id_header = reverse_map.get("id_card")
        
        if not id_header:
            return []
        
        seen = {}
        duplicates = []
        
        for idx, row in enumerate(rows):
            id_card = row.get(id_header, "").strip()
            if not id_card:
                continue
            
            if id_card in seen:
                duplicates.append({
                    "row_number": idx + 1,
                    "id_card": id_card,
                    "first_seen_row": seen[id_card],
                    "error_type": "duplicate",
                    "error_message": f"身份证号与第{seen[id_card]}行重复"
                })
            else:
                seen[id_card] = idx + 1
        
        return duplicates
