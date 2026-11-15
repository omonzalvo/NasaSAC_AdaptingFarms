import tempfile
from pathlib import Path
import unittest
from integrar import integrate, BEGIN

class InstallerTests(unittest.TestCase):
 def test_install_repeat_preserves_source_and_secrets(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   source='import pandas as pd\ndf=pd.DataFrame()\nlat,lon=20,-100\ninicio=fin=pd.Timestamp("2025-01-01")\n# custom code\n'
   (root/'app.py').write_text(source)
   (root/'.streamlit').mkdir()
   (root/'.streamlit/secrets.toml').write_text('GEMINI_API_KEY="local-only"')
   (root/'requirements.txt').write_text('pandas==3.1.1\njsonschema==4.26.0\nrequests==2.34.2\n')
   backup=integrate(root,install_dependencies=False)
   self.assertEqual((backup/'app.py').read_text(),source)
   self.assertIn('# custom code',(root/'app.py').read_text())
   self.assertEqual((root/'.streamlit/secrets.toml').read_text(),'GEMINI_API_KEY="local-only"')
   integrate(root,install_dependencies=False)
   self.assertEqual((root/'app.py').read_text().count(BEGIN),1)
   self.assertEqual((root/'requirements.txt').read_text().count('jsonschema'),1)
 def test_incompatible_does_not_modify(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'app.py'; p.write_text('print("hello")')
   with self.assertRaises(ValueError): integrate(temp,install_dependencies=False)
   self.assertEqual(p.read_text(),'print("hello")')
   self.assertFalse((Path(temp)/'terrashift_ai').exists())
 def test_unmanaged_module_protected(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp); (p/'app.py').write_text('df=lat=lon=inicio=fin=None')
   (p/'terrashift_ai').mkdir()
   with self.assertRaises(ValueError): integrate(p,install_dependencies=False)
if __name__=='__main__': unittest.main()
