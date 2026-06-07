"""
LLM-based header recognition service.
Currently implemented as Mock - replace with real LLM API calls.
"""
import json
import random
from typing import List, Dict, Tuple
from app.services.file_parser import STANDARD_FIELD_MAP, standardize_field_name

# Standard field descriptions for LLM context
STANDARD_FIELDS_DESC = {
    "name": "居民姓名（必填）",
    "gender": "性别：男/女",
    "id_card": "身份证号，15或18位",
    "phone": "手机号码，11位",
    "birth_date": "出生日期，格式如1990-01-01",
    "age": "年龄，数字",
    "ethnicity": "民族，如汉族、回族等",
    "marital_status": "婚姻状况：未婚/已婚/离异/丧偶",
    "employment_status": "就业情况",
    "medical_insurance": "医保状态",
    "residence_address": "现居住地址",
    "household_address": "户籍地址",
    "grid_name": "所属网格名称",
    "building_unit": "楼栋单元号",
    "household_number": "户号",
    "is_low_income": "是否低保户：是/否",
    "is_disabled": "是否残疾人：是/否",
    "disability_type": "残疾类别",
    "is_living_alone": "是否独居：是/否",
    "is_left_behind_child": "是否留守儿童：是/否",
    "is_key_population": "是否重点人群：是/否",
    "key_population_type": "重点人群类别",
    "is_special_support": "是否特困人员：是/否",
}

class LLMHeaderRecognizer:
    """Mock LLM header recognizer - replace with real LLM API"""
    
    @staticmethod
    def recognize_headers(headers: List[str], sample_rows: List[Dict] = None) -> List[Dict]:
        """
        Mock LLM header recognition.
        In production, this calls the LLM API with headers and sample data.
        
        Returns: List of {original_header, standard_field, confidence}
        """
        results = []
        
        for header in headers:
            # First try exact/fuzzy match with our standard map
            matched_field = standardize_field_name(header)
            
            if matched_field:
                confidence = round(random.uniform(0.85, 0.99), 2)
                results.append({
                    "original_header": header,
                    "standard_field": matched_field,
                    "confidence": confidence
                })
            else:
                # Try LLM-style semantic matching (mock)
                semantic_match = LLMHeaderRecognizer._semantic_match(header)
                if semantic_match:
                    confidence = round(random.uniform(0.60, 0.84), 2)
                    results.append({
                        "original_header": header,
                        "standard_field": semantic_match,
                        "confidence": confidence
                    })
                else:
                    # Unmapped field - could be custom
                    results.append({
                        "original_header": header,
                        "standard_field": "",
                        "confidence": 0.0
                    })
        
        return results
    
    @staticmethod
    def _semantic_match(header: str) -> str:
        """Semantic matching for headers not in standard map"""
        header_lower = header.lower().strip()
        
        semantic_rules = [
            ("name", ["户主", "业主", "家庭成员姓名", "成员姓名", "联系人", "家属姓名"]),
            ("phone", ["联系人电话", "家属电话", "紧急联系人", "备用电话", "座机"]),
            ("residence_address", ["现居地址", "居住地", "住址详细", "住所地址", "门牌地址"]),
            ("grid_name", ["责任区", "管理区", "片区", "管片", "责任网格"]),
            ("is_key_population", ["关注对象", "重点关怀", "重点关注人员", "特殊人群", "特殊人员"]),
            ("employment_status", ["工作", "单位", "职务", "职称", "职业状况"]),
            ("is_disabled", ["残疾证号", "残疾证", "残障人士"]),
            ("medical_insurance", ["社保", "医保卡", "医疗保险状态", "参保险种", "新农合"]),
            ("is_low_income", ["低保金", "救助", "困难户", "贫困户", "帮扶对象"]),
            ("building_unit", ["楼号", "单元号", "房间号", "门牌", "房号", "室号"]),
        ]
        
        for field, keywords in semantic_rules:
            for kw in keywords:
                if kw in header_lower or header_lower in kw:
                    return field
        
        return ""
    
    @staticmethod
    def generate_mapping_explanation(mappings: List[Dict]) -> str:
        """Generate human-readable explanation of mapping results"""
        matched = sum(1 for m in mappings if m["standard_field"])
        total = len(mappings)
        
        explanations = [
            f"识别完成：共检测到 {total} 个字段，成功匹配 {matched} 个标准字段。",
            f"字段覆盖率：{matched / total * 100:.1f}%。",
        ]
        
        if matched < total:
            unmapped = [m["original_header"] for m in mappings if not m["standard_field"]]
            explanations.append(f"以下字段未自动识别，可手动映射或保留为自定义字段：{', '.join(unmapped)}")
        
        return "\n".join(explanations)


class LLMNLQEngine:
    """Mock Natural Language Query Engine - replace with real LLM API"""
    
    # Query pattern templates
    QUERY_PATTERNS = {
        "elderly": {
            "keywords": ["老人", " elderly", "老年人", "高龄", "岁数大", "年纪大", "老龄"],
            "conditions": {"age__gte": 60},
            "description": "老年人查询"
        },
        "elderly_alone": {
            "keywords": ["独居老人", "独居老年人", "孤寡老人", "空巢老人", "独自居住的老人"],
            "conditions": {"age__gte": 60, "is_living_alone": True},
            "description": "独居老人查询"
        },
        "elderly_80": {
            "keywords": ["80岁", "80以上", "八十岁", "80以上老人", "80岁以上"],
            "conditions": {"age__gte": 80},
            "description": "80岁以上老人"
        },
        "disabled": {
            "keywords": ["残疾人", "残障", "残疾", "disabled", "身障"],
            "conditions": {"is_disabled": True},
            "description": "残疾人查询"
        },
        "low_income": {
            "keywords": ["低保", "低保户", "低收入", "困难户", "贫困户", "最低生活保障"],
            "conditions": {"is_low_income": True},
            "description": "低保户查询"
        },
        "left_behind_child": {
            "keywords": ["留守儿童", "留守", "left behind", "留守孩子"],
            "conditions": {"is_left_behind_child": True},
            "description": "留守儿童查询"
        },
        "key_population": {
            "keywords": ["重点人群", "重点人员", "重点关注", "key population", "特殊人群"],
            "conditions": {"is_key_population": True},
            "description": "重点人群查询"
        },
        "children": {
            "keywords": ["儿童", "孩子", "未成年", "0-6", "0-3", "幼儿", "婴幼儿", "小孩"],
            "conditions": {"age__lte": 18},
            "description": "未成年人查询"
        },
        "young_children": {
            "keywords": ["0-6岁", "0到6岁", "6岁以下", "学龄前", "婴幼儿", "0-3岁"],
            "conditions": {"age__lte": 6},
            "description": "6岁以下儿童"
        },
        "grid_query": {
            "keywords": ["网格", "grid", "辖区", "片区"],
            "conditions": {},  # Will be set based on extracted grid name
            "description": "网格查询"
        },
        "special_support": {
            "keywords": ["特困", "特困人员", "五保户", "供养人员"],
            "conditions": {"is_special_support": True},
            "description": "特困人员查询"
        },
        "female": {
            "keywords": ["女性", "女", "妇女", "woman", "female"],
            "conditions": {"gender": "女"},
            "description": "女性查询"
        },
        "male": {
            "keywords": ["男性", "男", "man", "male", "男子"],
            "conditions": {"gender": "男"},
            "description": "男性查询"
        },
        "married": {
            "keywords": ["已婚", "结婚", "有配偶"],
            "conditions": {"marital_status": "已婚"},
            "description": "已婚人员查询"
        },
    }
    
    @classmethod
    def parse_natural_language(cls, question: str, grid_name: str = None) -> Dict:
        """Parse natural language question into structured query"""
        question_lower = question.lower().strip()
        
        # Detect query type
        detected_type = None
        max_score = 0
        
        for qtype, config in cls.QUERY_PATTERNS.items():
            score = 0
            for kw in config["keywords"]:
                if kw.lower() in question_lower:
                    score += 1
            if score > max_score:
                max_score = score
                detected_type = qtype
        
        # Build conditions
        conditions = {}
        if detected_type and detected_type in cls.QUERY_PATTERNS:
            conditions = dict(cls.QUERY_PATTERNS[detected_type]["conditions"])
        
        # Extract age conditions
        age_conditions = cls._extract_age_conditions(question_lower)
        conditions.update(age_conditions)
        
        # Extract grid name from question
        extracted_grid = cls._extract_grid_name(question_lower)
        if extracted_grid:
            conditions["grid_name"] = extracted_grid
        elif grid_name:
            conditions["grid_name"] = grid_name
        
        # Build mock SQL
        mock_sql = cls._build_mock_sql(conditions, question)
        
        return {
            "question": question,
            "detected_type": detected_type or "general",
            "conditions": conditions,
            "mock_sql": mock_sql,
            "explanation": cls._generate_explanation(question, detected_type, conditions)
        }
    
    @staticmethod
    def _extract_age_conditions(question: str) -> Dict:
        """Extract age conditions from question"""
        import re
        conditions = {}
        
        # Pattern: X岁以上
        match = re.search(r'(\d+)岁以[上≥]', question)
        if match:
            conditions["age__gte"] = int(match.group(1))
        
        # Pattern: X岁以下
        match = re.search(r'(\d+)岁以[下≤]', question)
        if match:
            conditions["age__lte"] = int(match.group(1))
        
        # Pattern: X-Y岁
        match = re.search(r'(\d+)[\-~到](\d+)岁', question)
        if match:
            conditions["age__gte"] = int(match.group(1))
            conditions["age__lte"] = int(match.group(2))
        
        return conditions
    
    @staticmethod
    def _extract_grid_name(question: str) -> str:
        """Extract grid name from question"""
        import re
        # Pattern: X网格 / 第X网格
        match = re.search(r'(\d+)[网格片区]', question)
        if match:
            return f"{match.group(1)}网格"
        
        match = re.search(r'第([一二三四五六七八九十\d]+)[网格片区]', question)
        if match:
            num = match.group(1)
            cn_nums = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
                      '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'}
            if num in cn_nums:
                num = cn_nums[num]
            return f"{num}网格"
        
        return ""
    
    @staticmethod
    def _build_mock_sql(conditions: Dict, question: str) -> str:
        """Build mock SQL for display"""
        where_clauses = []
        
        for key, value in conditions.items():
            if key.endswith("__gte"):
                field = key.replace("__gte", "")
                where_clauses.append(f"{field} >= {value}")
            elif key.endswith("__lte"):
                field = key.replace("__lte", "")
                where_clauses.append(f"{field} <= {value}")
            elif key.endswith("__eq"):
                field = key.replace("__eq", "")
                where_clauses.append(f"{field} = '{value}'")
            elif isinstance(value, bool):
                where_clauses.append(f"{key} = {1 if value else 0}")
            elif isinstance(value, str):
                where_clauses.append(f"{key} = '{value}'")
        
        sql = "SELECT * FROM resident_master"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        sql += " ORDER BY id LIMIT 1000"
        
        return sql
    
    @staticmethod
    def _generate_explanation(question: str, qtype: str, conditions: Dict) -> str:
        """Generate human-readable explanation"""
        parts = [f"识别到查询意图：'{question}'"]
        
        if qtype:
            parts.append(f"查询类型：{LLMNLQEngine.QUERY_PATTERNS.get(qtype, {}).get('description', '综合查询')}")
        
        condition_desc = []
        if "age__gte" in conditions and "age__lte" in conditions:
            condition_desc.append(f"年龄在 {conditions['age__gte']}-{conditions['age__lte']} 岁之间")
        elif "age__gte" in conditions:
            condition_desc.append(f"年龄在 {conditions['age__gte']} 岁以上")
        elif "age__lte" in conditions:
            condition_desc.append(f"年龄在 {conditions['age__lte']} 岁以下")
        if "is_living_alone" in conditions:
            condition_desc.append("独居状态")
        if "is_disabled" in conditions:
            condition_desc.append("残疾人")
        if "is_low_income" in conditions:
            condition_desc.append("低保户")
        if "grid_name" in conditions:
            condition_desc.append(f"所属{conditions['grid_name']}")
        if "gender" in conditions:
            condition_desc.append(f"性别：{conditions['gender']}")
        
        if condition_desc:
            parts.append(f"查询条件：{', '.join(condition_desc)}")
        
        return "；".join(parts)


class LLMReportGenerator:
    """Mock LLM report generator"""
    
    @staticmethod
    def generate_summary(report_type: str, stats: Dict) -> str:
        """Generate report summary text"""
        summaries = {
            "population_summary": (
                f"根据最新数据统计，本社区共有居民{stats.get('total_residents', 0)}人，"
                f"分布在{stats.get('total_grids', 0)}个网格中。"
                f"其中重点人群{stats.get('key_populations', 0)}人，"
                f"独居老人{stats.get('elderly_alone', 0)}人，"
                f"残疾人{stats.get('disabled_persons', 0)}人，"
                f"低保户{stats.get('low_income', 0)}人。"
                "建议持续关注重点人群的生活状况，加强网格化服务管理。"
            ),
            "grid_statistics": (
                f"各网格人口分布情况统计如下，"
                f"建议对人口密集网格加强资源配置。"
            ),
            "key_populations": (
                f"本社区共有重点人群{stats.get('key_populations', 0)}人，"
                "建议建立一对一帮扶机制，定期走访了解需求。"
            ),
        }
        
        return summaries.get(report_type, "报告已生成，请查看详细数据。")
