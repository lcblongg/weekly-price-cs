"""Danh mục chuẩn duy nhất cho cả năm bot và web, giữ SKU/biến thể độc lập.
Quy tắc nhận diện đọc từ config/apple_models.json (gồm cả quy tắc tự sinh do apple_rules ghi).
Model có trong apple_colors.json nhưng thiếu quy tắc (cấu hình sửa tay) được sinh quy tắc literal giống hệt
web/lib/product-standard.ts, để Python và TypeScript không bao giờ nhận diện khác nhau."""
import json,re
from pathlib import Path
from apple_rules import literal_pattern,COLORS,MODELS as MODEL_RULES
DATA=json.loads(MODEL_RULES.read_text())
preferences=json.loads(COLORS.read_text())
for rule in preferences['products']:
 if not any(r['name']==rule['model'] for r in DATA['models']):
  DATA['models'].append({'name':rule['model'],'pattern':literal_pattern(rule['model']),'generated':True})
MODELS=[r['model'] for r in preferences['products']]+[r['name'] for r in DATA['models'] if r['name'] not in {p['model'] for p in preferences['products']}]
RULES=[(r['name'],re.compile(r['pattern'],re.I)) for r in DATA['models']]
def canonical_model(name):
 matches=[label for label,pattern in RULES if pattern.search(str(name or ''))]
 return matches[0] if len(matches)==1 else None
def model_order(model):return MODELS.index(model) if model in MODELS else len(MODELS)
def display_name(name,storage=None):
 model=canonical_model(name)
 return model+(' '+storage if storage else '') if model else name
