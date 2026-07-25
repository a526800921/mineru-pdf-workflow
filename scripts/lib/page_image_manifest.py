"""全量 PDF 整页图片生成、校验和输出包根 manifest 同步。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST_VERSION = "1"
TOOL_NAME = "pdf-page-images"
TOOL_VERSION = "1"
DEFAULT_DPI = 160
DEFAULT_QUALITY = 88


class PageImageError(RuntimeError):
    """页图生成或发布失败。"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        Path(temp_name).unlink(missing_ok=True)
        raise


def _validate_metadata(model_slug: str, display_name: str, data_version: str) -> None:
    for field, value in (
        ("model_slug", model_slug),
        ("display_name", display_name),
        ("data_version", data_version),
    ):
        if not isinstance(value, str) or not value.strip():
            raise PageImageError(f"缺少必需页图元数据：{field}")


def _publish_directory(staging_dir: Path, output_dir: Path) -> None:
    """在同一父目录内替换目录，失败时恢复原目录。"""
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    backup_dir: Path | None = None
    if output_dir.exists():
        if not output_dir.is_dir():
            raise PageImageError(f"页图输出路径不是目录：{output_dir}")
        backup_dir = Path(
            tempfile.mkdtemp(prefix=f".{output_dir.name}.backup-", dir=str(output_dir.parent))
        )
        backup_dir.rmdir()
        os.replace(output_dir, backup_dir)
    try:
        os.replace(staging_dir, output_dir)
    except Exception:
        if backup_dir is not None and not output_dir.exists():
            os.replace(backup_dir, output_dir)
        raise
    if backup_dir is not None:
        shutil.rmtree(backup_dir, ignore_errors=True)


def _safe_asset_path(manifest_dir: Path, asset: Any) -> tuple[Path | None, str | None]:
    if not isinstance(asset, str) or not asset:
        return None, "asset 不是非空字符串"
    asset_path = Path(asset)
    if asset_path.is_absolute():
        return None, "asset 不得是绝对路径"
    root = manifest_dir.resolve()
    resolved = (manifest_dir / asset_path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, "asset 路径越出 manifest 目录"
    return resolved, None


def _empty_validation(status: str, pdf_path: Path, manifest_path: Path) -> dict[str, Any]:
    return {
        "status": status,
        "pdf": str(pdf_path),
        "manifest": str(manifest_path),
        "model_slug": None,
        "display_name": None,
        "data_version": None,
        "page_count": 0,
        "validated_pages": 0,
        "missing_assets": [],
        "path_errors": [],
        "format_errors": [],
        "dimension_mismatches": [],
        "size_mismatches": [],
        "sha256_mismatches": [],
        "pdf_page_mapping_errors": [],
        "errors": [],
    }


def validate_page_images(
    pdf_path: Path,
    manifest_path: Path,
    validation_path: Path | None = None,
) -> dict[str, Any]:
    """校验页数、路径、图片属性、单页 hash 和源 PDF hash。"""
    report = _empty_validation("failed", pdf_path, manifest_path)
    validation_path = validation_path or manifest_path.parent / "validation.json"
    try:
        import fitz
    except Exception as exc:  # pragma: no cover - 环境错误由 CLI 报告
        report["errors"].append(f"无法导入 PyMuPDF/fitz：{exc}")
        _atomic_write_json(validation_path, report)
        return report

    try:
        source_hash = sha256_file(pdf_path)
        doc = fitz.open(str(pdf_path))
        actual_page_count = doc.page_count
        doc.close()
    except Exception as exc:
        report["errors"].append(f"无法读取源 PDF：{exc}")
        _atomic_write_json(validation_path, report)
        return report

    report["source_pdf_sha256"] = source_hash
    report["page_count"] = actual_page_count
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report["errors"].append(f"无法读取页图 manifest：{exc}")
        _atomic_write_json(validation_path, report)
        return report

    if not isinstance(manifest, dict):
        report["errors"].append("页图 manifest 顶层必须是对象")
        _atomic_write_json(validation_path, report)
        return report

    report["model_slug"] = manifest.get("model_slug")
    report["display_name"] = manifest.get("display_name")
    report["data_version"] = manifest.get("data_version")
    for field in ("model_slug", "display_name", "data_version"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            report["errors"].append(f"{field} 必须是非空字符串")
    if manifest.get("image_format") != "jpeg":
        report["errors"].append("image_format 必须为 jpeg")
    generation = manifest.get("generation")
    if not isinstance(generation, dict):
        report["errors"].append("generation 必须是对象")
    else:
        for field in ("tool", "tool_version", "generated_at"):
            if not isinstance(generation.get(field), str) or not generation[field].strip():
                report["errors"].append(f"generation.{field} 必须是非空字符串")
        if not isinstance(generation.get("dpi"), int) or generation["dpi"] < 1:
            report["errors"].append("generation.dpi 必须是正整数")
        if (
            not isinstance(generation.get("quality"), int)
            or not 1 <= generation["quality"] <= 100
        ):
            report["errors"].append("generation.quality 必须在 1-100 之间")
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        report["errors"].append("manifest_version 不受支持")
    if manifest.get("source_pdf") != pdf_path.name:
        report["errors"].append("source_pdf 与实际输入 PDF 文件名不一致")
    if manifest.get("source_pdf_sha256") != source_hash:
        report["errors"].append("source_pdf_sha256 与实际输入 PDF 不一致")
        report["sha256_mismatches"].append("source_pdf")
    if manifest.get("page_count") != actual_page_count:
        report["errors"].append("page_count 与源 PDF 实际页数不一致")

    pages = manifest.get("pages")
    if not isinstance(pages, list):
        report["errors"].append("pages 必须是数组")
        _atomic_write_json(validation_path, report)
        return report
    if len(pages) != actual_page_count:
        report["errors"].append("pages 数量与源 PDF 实际页数不一致")

    seen_ids: set[str] = set()
    seen_pages: set[int] = set()
    manifest_dir = manifest_path.parent
    for index, page in enumerate(pages, start=1):
        page_errors = False
        if not isinstance(page, dict):
            report["errors"].append(f"pages[{index - 1}] 必须是对象")
            continue
        page_id = page.get("page_id")
        pdf_page = page.get("pdf_page")
        if not isinstance(page_id, str) or not page_id:
            report["errors"].append(f"pages[{index - 1}].page_id 不是非空字符串")
            page_id_key = repr(page_id)
            page_errors = True
        else:
            page_id_key = page_id
        if page_id_key in seen_ids:
            report["errors"].append(f"重复 page_id：{page_id}")
            page_errors = True
        seen_ids.add(page_id_key)
        if not isinstance(pdf_page, int) or isinstance(pdf_page, bool):
            report["errors"].append(f"pages[{index - 1}].pdf_page 不是整数")
            page_errors = True
            page_number = None
        else:
            page_number = pdf_page
            if page_number in seen_pages:
                report["errors"].append(f"重复 pdf_page：{page_number}")
                page_errors = True
            seen_pages.add(page_number)
            if page_number != index:
                report["pdf_page_mapping_errors"].append(
                    {"index": index, "pdf_page": page_number}
                )
                page_errors = True
            if page_number < 1 or page_number > actual_page_count:
                report["errors"].append(f"pdf_page 越界：{page_number}")
                page_errors = True
            if page_id != f"pdf-{page_number:04d}":
                report["errors"].append(f"page_id 与 pdf_page 不匹配：{page_id}")
                page_errors = True

        asset_path, path_error = _safe_asset_path(manifest_dir, page.get("asset"))
        if path_error:
            report["path_errors"].append({"page": page_number, "error": path_error})
            page_errors = True
        elif asset_path is None or not asset_path.is_file():
            report["missing_assets"].append(page.get("asset"))
            page_errors = True
        else:
            raw = asset_path.read_bytes()
            if Path(str(page.get("asset"))).suffix.lower() not in {".jpg", ".jpeg"}:
                report["format_errors"].append(str(page.get("asset")))
                page_errors = True
            if not raw.startswith(b"\xff\xd8\xff"):
                report["format_errors"].append(str(page.get("asset")))
                page_errors = True
            try:
                pix = fitz.Pixmap(str(asset_path))
                width, height = pix.width, pix.height
            except Exception as exc:
                report["format_errors"].append(
                    {"asset": str(page.get("asset")), "error": str(exc)}
                )
                page_errors = True
            else:
                if page.get("format") != "jpeg" or manifest.get("image_format") != "jpeg":
                    report["format_errors"].append(str(page.get("asset")))
                    page_errors = True
                if page.get("width") != width or page.get("height") != height:
                    report["dimension_mismatches"].append(str(page.get("asset")))
                    page_errors = True
            if page.get("size_bytes") != len(raw):
                report["size_mismatches"].append(str(page.get("asset")))
                page_errors = True
            actual_hash = hashlib.sha256(raw).hexdigest()
            if page.get("sha256") != actual_hash:
                report["sha256_mismatches"].append(str(page.get("asset")))
                page_errors = True
        if not page_errors:
            report["validated_pages"] += 1

    if (
        not report["errors"]
        and not report["missing_assets"]
        and not report["path_errors"]
        and not report["format_errors"]
        and not report["dimension_mismatches"]
        and not report["size_mismatches"]
        and not report["sha256_mismatches"]
        and not report["pdf_page_mapping_errors"]
        and report["validated_pages"] == actual_page_count
    ):
        report["status"] = "passed"
    else:
        report["status"] = "failed"
    _atomic_write_json(validation_path, report)
    return report


def render_page_images(
    pdf_path: Path,
    output_dir: Path,
    model_slug: str,
    display_name: str,
    data_version: str,
    dpi: int = DEFAULT_DPI,
    quality: int = DEFAULT_QUALITY,
) -> dict[str, Any]:
    """将 PDF 所有物理页渲染为 JPEG，并在校验通过后发布整个目录。"""
    _validate_metadata(model_slug, display_name, data_version)
    if dpi < 1 or quality < 1 or quality > 100:
        raise PageImageError("dpi 必须为正整数，quality 必须在 1-100 之间")
    try:
        import fitz
    except Exception as exc:
        raise PageImageError(f"无法导入 PyMuPDF/fitz：{exc}") from exc

    if not pdf_path.is_file():
        raise PageImageError(f"找不到源 PDF：{pdf_path}")
    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=str(output_dir.parent))
    )
    try:
        assets_dir = staging_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        source_hash = sha256_file(pdf_path)
        doc = fitz.open(str(pdf_path))
        try:
            page_count = doc.page_count
            if page_count < 1:
                raise PageImageError("源 PDF 没有物理页")
            pages: list[dict[str, Any]] = []
            for pdf_page in range(1, page_count + 1):
                page = doc[pdf_page - 1]
                pix = page.get_pixmap(dpi=dpi, alpha=False)
                raw = pix.tobytes("jpg", jpg_quality=quality)
                asset_name = f"pdf-{pdf_page:04d}.jpg"
                asset_path = assets_dir / asset_name
                asset_path.write_bytes(raw)
                pages.append(
                    {
                        "page_id": f"pdf-{pdf_page:04d}",
                        "pdf_page": pdf_page,
                        "markdown_page": None,
                        "source_page": None,
                        "asset": f"assets/{asset_name}",
                        "format": "jpeg",
                        "width": pix.width,
                        "height": pix.height,
                        "size_bytes": len(raw),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                )
        finally:
            doc.close()

        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "model_slug": model_slug,
            "display_name": display_name,
            "data_version": data_version,
            "source_pdf": pdf_path.name,
            "source_pdf_sha256": source_hash,
            "page_count": page_count,
            "image_format": "jpeg",
            "generation": {
                "tool": TOOL_NAME,
                "tool_version": TOOL_VERSION,
                "dpi": dpi,
                "quality": quality,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "pages": pages,
        }
        manifest_path = staging_dir / "manifest.json"
        _atomic_write_json(manifest_path, manifest)
        report = validate_page_images(pdf_path, manifest_path, staging_dir / "validation.json")
        if report["status"] != "passed":
            raise PageImageError("页图生成后的独立校验失败")
        _publish_directory(staging_dir, output_dir)
        published_manifest = output_dir / "manifest.json"
        return {
            "status": "passed",
            "output_dir": str(output_dir),
            "manifest_path": str(published_manifest),
            "validation_path": str(output_dir / "validation.json"),
            "model_slug": model_slug,
            "display_name": display_name,
            "data_version": data_version,
            "page_count": page_count,
            "validated_pages": page_count,
            "manifest_sha256": sha256_file(published_manifest),
            "source_pdf_sha256": source_hash,
        }
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def sync_root_manifest(
    root_manifest_path: Path,
    page_images_dir: Path,
    validation_report: dict[str, Any],
) -> dict[str, Any]:
    """将页图机器入口和状态合并写入输出包根 manifest。"""
    root_manifest_path = root_manifest_path.resolve()
    package_dir = root_manifest_path.parent
    page_images_dir = page_images_dir.resolve()
    try:
        page_images_dir.relative_to(package_dir)
    except ValueError as exc:
        raise PageImageError("页图目录必须位于输出包根目录内") from exc
    rel_dir = page_images_dir.relative_to(package_dir).as_posix()
    manifest_file = page_images_dir / "manifest.json"
    validation_file = page_images_dir / "validation.json"
    try:
        root = json.loads(root_manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        root = {}
    except Exception as exc:
        raise PageImageError(f"根 manifest 无法读取：{exc}") from exc
    if not isinstance(root, dict):
        raise PageImageError("根 manifest 顶层必须是对象")
    files = root.setdefault("files", {})
    if not isinstance(files, dict):
        raise PageImageError("根 manifest.files 必须是对象")
    files["page_images"] = rel_dir
    files["page_images_manifest"] = f"{rel_dir}/manifest.json"
    files["page_images_validation"] = f"{rel_dir}/validation.json"
    manifest_hash = sha256_file(manifest_file) if manifest_file.is_file() else ""
    passed = validation_report.get("status") == "passed" and bool(manifest_hash)
    page_images: dict[str, Any] = {
        "status": "validated" if passed else "error",
        "manifest_version": MANIFEST_VERSION,
        "source_pdf_sha256": validation_report.get("source_pdf_sha256", ""),
        "page_count": validation_report.get("page_count", 0),
        "validated_pages": validation_report.get("validated_pages", 0),
        "manifest_sha256": manifest_hash,
    }
    if validation_report.get("model_slug"):
        page_images["model_slug"] = validation_report["model_slug"]
    if validation_report.get("display_name"):
        page_images["display_name"] = validation_report["display_name"]
    if validation_report.get("data_version"):
        page_images["data_version"] = validation_report["data_version"]
    if validation_report.get("errors"):
        page_images["errors"] = validation_report["errors"]
    if not passed:
        page_images["validation_status"] = validation_report.get("status", "failed")
    root["page_images"] = page_images
    _atomic_write_json(root_manifest_path, root)
    return page_images


def write_page_image_error(
    root_manifest_path: Path,
    page_images_dir: Path,
    source_pdf_sha256: str,
    page_count: int,
    error: str,
) -> dict[str, Any]:
    report = _empty_validation("failed", Path(""), page_images_dir / "manifest.json")
    report["source_pdf_sha256"] = source_pdf_sha256
    report["page_count"] = page_count
    report["errors"].append(error)
    page_images_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(page_images_dir / "validation.json", report)
    return sync_root_manifest(root_manifest_path, page_images_dir, report)
