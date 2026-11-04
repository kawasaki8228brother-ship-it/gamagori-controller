import hashlib
import unittest
from runtime_check import inspect_runtime,parse_pins,known_vectors

RAW=b'Alpha==1.0\nbeta_core==2.0\n'
SHA=hashlib.sha256(RAW).hexdigest()

class Tests(unittest.TestCase):
 def test_known_vectors(self):self.assertTrue(known_vectors())
 def test_complete_and_pip_exclusion(self):
  r=inspect_runtime(RAW,SHA,[('ALPHA','1.0'),('beta-core','2.0'),('pip','25.3')],'3.14.3')
  self.assertEqual(r['status'],'REFERENCE_ENV_MATCH');self.assertFalse(r['production_GO'])
 def test_all_diagnostics(self):
  r=inspect_runtime(RAW,'0'*64,[('alpha','0.9'),('other','1')],'3.12.14')
  self.assertFalse(r['requirements_sha_match']);self.assertFalse(r['python_exact_match'])
  self.assertEqual(r['missing'],['beta-core']);self.assertEqual(r['extras_excluding_pip'],['other'])
  self.assertEqual(r['version_mismatches']['alpha']['actual'],'0.9')
 def test_duplicate_distribution_not_hidden(self):
  r=inspect_runtime(RAW,SHA,[('alpha','1.0'),('ALPHA','1.0'),('beta-core','2.0')],'3.14.3')
  self.assertEqual(r['status'],'ENV_DIFFERS');self.assertEqual(r['duplicate_installed_names'],['alpha'])
 def test_invalid_pins(self):
  for raw in [b'',b'alpha>=1',b'alpha @ https://example.invalid/a',b'-e ./a',b'a==1; os_name=x',b'a_b==1\na-b==1',b'pip==25',b'\xff']:
   with self.subTest(raw=raw):
    with self.assertRaises(ValueError):parse_pins(raw)
 def test_reference_format_and_type(self):
  with self.assertRaises(ValueError):inspect_runtime(RAW,'invalid',[],'3.14.3')
  with self.assertRaises(TypeError):parse_pins('a==1')

if __name__=='__main__':unittest.main(verbosity=2)
