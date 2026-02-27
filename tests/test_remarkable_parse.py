
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from src.remarkable.parse import list_notebooks, get_notebook, NotebookInfo, PageInfo

class TestRemarkableParse(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path("temp_test_data")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.xochitl_dir = self.tmp_dir / "xochitl"
        self.xochitl_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    def create_dummy_notebook(self, uuid, name, pages_ids):
        # Metadata
        meta = {
            "visibleName": name,
            "type": "DocumentType",
            "lastModified": "1678886400000",
            "parent": ""
        }
        (self.xochitl_dir / f"{uuid}.metadata").write_text(json.dumps(meta))
        
        # Content
        content = {
            "fileType": "notebook",
            "pageCount": len(pages_ids),
            "cPages": {"pages": [{"id": pid} for pid in pages_ids]}
        }
        (self.xochitl_dir / f"{uuid}.content").write_text(json.dumps(content))
        
        # Page files
        nb_dir = self.xochitl_dir / uuid
        nb_dir.mkdir(exist_ok=True)
        for pid in pages_ids:
            (nb_dir / f"{pid}.rm").touch()
            # thumbnails are optional but let's mock one
            (self.xochitl_dir / f"{uuid}.thumbnails").mkdir(exist_ok=True)
            (self.xochitl_dir / f"{uuid}.thumbnails" / f"{pid}.png").touch()

    def test_list_notebooks_empty(self):
        notebooks = list_notebooks(self.xochitl_dir)
        self.assertEqual(len(notebooks), 0)

    def test_list_notebooks_valid(self):
        self.create_dummy_notebook("nb1", "Notebook 1", ["p1", "p2"])
        notebooks = list_notebooks(self.xochitl_dir)
        self.assertEqual(len(notebooks), 1)
        nb = notebooks[0]
        self.assertEqual(nb.uuid, "nb1")
        self.assertEqual(nb.visible_name, "Notebook 1")
        self.assertEqual(nb.page_count, 2)
        self.assertEqual(len(nb.pages), 2)
        self.assertEqual(nb.pages[0].page_id, "p1")
        self.assertEqual(nb.pages[1].page_id, "p2")
        self.assertTrue(nb.pages[0].rm_path.exists())

    def test_list_notebooks_invalid_metadata(self):
        # Create a file that looks like metadata but has invalid JSON
        (self.xochitl_dir / "bad.metadata").write_text("not json")
        notebooks = list_notebooks(self.xochitl_dir)
        self.assertEqual(len(notebooks), 0)

    def test_list_notebooks_not_notebook_type(self):
        # Create a document that is not a notebook (e.g. PDF)
        uuid = "pdf_doc"
        meta = {"visibleName": "My PDF", "type": "DocumentType"}
        (self.xochitl_dir / f"{uuid}.metadata").write_text(json.dumps(meta))
        content = {"fileType": "pdf"}
        (self.xochitl_dir / f"{uuid}.content").write_text(json.dumps(content))
        
        notebooks = list_notebooks(self.xochitl_dir)
        self.assertEqual(len(notebooks), 0)

    def test_get_notebook_by_uuid(self):
        self.create_dummy_notebook("nb1", "Notebook 1", ["p1"])
        self.create_dummy_notebook("nb2", "Notebook 2", ["p1"])
        
        nb = get_notebook(self.xochitl_dir, uuid="nb1")
        self.assertIsNotNone(nb)
        self.assertEqual(nb.visible_name, "Notebook 1")

    def test_get_notebook_by_name(self):
        self.create_dummy_notebook("nb1", "Notebook 1", ["p1"])
        
        nb = get_notebook(self.xochitl_dir, name="Notebook 1")
        self.assertIsNotNone(nb)
        self.assertEqual(nb.uuid, "nb1")
        
        nb_missing = get_notebook(self.xochitl_dir, name="Missing")
        self.assertIsNone(nb_missing)

if __name__ == "__main__":
    unittest.main()
