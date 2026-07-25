#!/usr/bin/env python3
"""整页图片 renderer/validator 的本地 fixture 测试。"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from lib.page_image_manifest import (  # noqa: E402
    PageImageError,
    render_page_images,
    sync_root_manifest,
    validate_page_images,
)


ROOT = Path(__file__).resolve().parents[1]
DEMO_PDF = ROOT / "pdf" / "demo5" / "demo5.pdf"


class TestPageImageManifest(unittest.TestCase):
    def test_render_validate_and_root_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)
            output_dir = package / "data" / "page_images"
            result = render_page_images(
                DEMO_PDF,
                output_dir,
                "demo5",
                "Demo 5",
                "test-1",
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(result["page_count"], 5)
            self.assertEqual(len(list((output_dir / "assets").glob("*.jpg"))), 5)

            report = validate_page_images(DEMO_PDF, output_dir / "manifest.json")
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["validated_pages"], 5)

            root_manifest = package / "manifest.json"
            root_manifest.write_text(
                json.dumps({"files": {"images": "images"}}, ensure_ascii=False),
                encoding="utf-8",
            )
            page_state = sync_root_manifest(root_manifest, output_dir, report)
            self.assertEqual(page_state["status"], "validated")
            root = json.loads(root_manifest.read_text(encoding="utf-8"))
            self.assertEqual(root["files"]["page_images"], "data/page_images")
            self.assertEqual(
                root["files"]["page_images_manifest"],
                "data/page_images/manifest.json",
            )
            self.assertEqual(root["files"]["images"], "images")
            self.assertEqual(root["page_images"]["data_version"], "test-1")

    def test_tampered_asset_fails_without_marking_validated(self):
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp) / "page_images"
            render_page_images(DEMO_PDF, output_dir, "demo5", "Demo 5", "test-1")
            asset = output_dir / "assets" / "pdf-0003.jpg"
            asset.unlink()
            report = validate_page_images(DEMO_PDF, output_dir / "manifest.json")
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["validated_pages"], 4)
            self.assertIn("assets/pdf-0003.jpg", report["missing_assets"])

    def test_metadata_is_required(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(PageImageError):
                render_page_images(DEMO_PDF, Path(temp) / "page_images", "", "Demo 5", "test-1")


if __name__ == "__main__":
    unittest.main()
