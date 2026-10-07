import unittest
from product_standard import MODELS,canonical_model,model_order
from identity import describe,chain_sku
class StandardTests(unittest.TestCase):
 def test_all_36_models_exact(self):
  self.assertEqual(len(MODELS),36)
  for model in MODELS:self.assertEqual(canonical_model(model),model)
 def test_no_pro_max_or_generation_collision(self):
  for name,model in [('Điện thoại iPhone 18 Pro Max 256GB','iPhone 18 Pro Max'),('iPad Air 11 inch M4 Wifi 256GB','iPad Air M4 11'),('MacBook Air M5 13 inch 16GB 512GB','MacBook Air 13 M5'),('Apple Watch Series 11 GPS 42mm','Apple Watch S11'),('AirPods 4 chống ồn','AirPods 4 with ANC')]:self.assertEqual(canonical_model(name),model)
  self.assertIsNone(canonical_model('AirPods Max 2026'))
  self.assertIsNone(canonical_model('MacBook Pro 16 M5 Max'))
 def test_shared_all_chains_and_order(self):
  for chain in ['TGDD','CellphoneS','FPT Shop','Viettel Store','Phong Vũ']:
   self.assertEqual(describe('iPhone 17 Pro Max 512GB','Điện thoại','Apple')['model_name'],'iPhone 17 Pro Max');self.assertTrue(chain_sku(chain,'123456'))
  self.assertLess(model_order('iPhone 18 Pro Max'),model_order('iPhone 18 Pro'))
  self.assertLess(model_order('iPad Mini 7'),model_order('MacBook Neo'))
