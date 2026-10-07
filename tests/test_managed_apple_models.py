"""Model mới được nhận từ cấu hình quản lý, không ghép nhầm bản Pro/Max."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class ManagedModelsTest(unittest.TestCase):
    def test_new_model_and_order_from_preferences(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            task=Path(directory)
            (task/'config').mkdir()
            shutil.copy(root/'product_standard.py',task/'product_standard.py')
            shutil.copy(root/'apple_rules.py',task/'apple_rules.py')
            shutil.copy(root/'config/apple_models.json',task/'config/apple_models.json')
            products=[{'model':'iPhone 19','color':'Đen','aliases':[]},{'model':'iPhone 19 Pro Max','color':'Đỏ Burgundy','aliases':[]}]
            (task/'config/apple_colors.json').write_text(json.dumps({'version':1,'products':products}))
            result=subprocess.run([sys.executable,'-c',"from product_standard import *; assert MODELS[:2]==['iPhone 19','iPhone 19 Pro Max']; assert canonical_model('Điện thoại iPhone 19 Pro Max 256GB')=='iPhone 19 Pro Max'; assert canonical_model('iPhone 19 256GB')=='iPhone 19'; assert canonical_model('iPhone 19 Pro 256GB') is None"],cwd=task,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
