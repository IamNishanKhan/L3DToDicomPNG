#!/usr/bin/env python3
"""Batch BK Medical L3D -> DICOM -> PNG conversion.

Input:
    source_dir/<patient-folder>/*.l3d

Output:
    destination_dir/<derived PatientID>/dicom/<PatientID>.dcm
    destination_dir/<derived PatientID>/metadata.json
    destination_dir/<derived PatientID>/png/<PatientID>_0000.png
    destination_dir/batch_summary.json

Example:
    python batch_l3d_to_dicom_png.py --source D:\\Research\\Raw \\
        --destination D:\\Research\\test --workers 4
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pydicom
from PIL import Image

ENHANCED_US_VOLUME = "1.2.840.10008.5.1.4.1.1.6.2"


def safe_name(value: str) -> str:
    value = str(value).strip()
    for char in '<>:"/\\|?*':
        value = value.replace(char, "_")
    value = "".join("_" if ord(c) < 32 else c for c in value).rstrip(". ")
    if not value or value in {".", ".."}:
        raise ValueError("DICOM PatientID is empty or invalid")
    return value


def find_l3d(folder: Path) -> Path:
    files = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() == ".l3d"]
    if not files:
        raise FileNotFoundError(f"No .l3d file found under {folder}")
    files.sort(key=lambda p: p.stat().st_size, reverse=True)
    if len(files) > 1:
        print(f"  Multiple L3D files found; using largest: {files[0].name}")
    return files[0]


def valid_dicom(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 132:
        return False
    with path.open("rb") as handle:
        handle.seek(128)
        return handle.read(4) == b"DICM"


def run_native_converter(package_dir: Path, input_l3d: Path, output_dcm: Path) -> None:
    electron = package_dir / "electron" / "electron.exe"
    runner = package_dir / "electron-runner"
    if not electron.is_file():
        raise FileNotFoundError(f"Missing Electron runtime: {electron}")
    output_dcm.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [str(electron), str(runner), str(input_l3d), str(output_dcm)],
        cwd=str(package_dir),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    # Electron 8 can return a blank/nonzero status after native SaveDicom has
    # completed. The DICOM signature is authoritative.
    if not valid_dicom(output_dcm):
        raise RuntimeError(
            f"Native conversion failed (exit code {completed.returncode}); "
            f"no valid DICOM was created: {output_dcm}"
        )


def frames_from_dicom(ds) -> np.ndarray:
    pixels = np.asarray(ds.pixel_array)
    if pixels.ndim == 2:
        pixels = pixels[np.newaxis, ...]
    if pixels.ndim != 3:
        raise ValueError(f"Expected grayscale frames, got pixel shape {pixels.shape}")
    return pixels


def window_values(ds, pixels: np.ndarray) -> tuple[float, float]:
    try:
        center = getattr(ds, "WindowCenter", None)
        width = getattr(ds, "WindowWidth", None)
        if center is not None and width is not None:
            if not isinstance(center, str) and hasattr(center, "__getitem__"):
                center = center[0]
            if not isinstance(width, str) and hasattr(width, "__getitem__"):
                width = width[0]
            c, w = float(center), float(width)
            if w > 0:
                return c - w / 2.0, c + w / 2.0
    except (TypeError, ValueError, IndexError):
        pass
    finite = pixels[np.isfinite(pixels)]
    if finite.size == 0:
        return 0.0, 1.0
    low, high = np.percentile(finite.astype(np.float32), [0.5, 99.5])
    return float(low), float(max(high, low + 1.0))


def export_pngs(dcm_path: Path, patient_dir: Path, patient_id: str) -> dict:
    ds = pydicom.dcmread(str(dcm_path), force=True)
    if str(getattr(ds, "SOPClassUID", "")) != ENHANCED_US_VOLUME:
        raise ValueError(f"Unexpected SOPClassUID: {getattr(ds, 'SOPClassUID', None)}")
    frames = frames_from_dicom(ds)
    low, high = window_values(ds, frames)
    png_dir = patient_dir / "png"
    png_dir.mkdir(parents=True, exist_ok=True)
    names = []
    for index, frame in enumerate(frames):
        image = np.clip((frame.astype(np.float32) - low) * 255.0 / (high - low), 0, 255)
        name = f"{patient_id}_{index:04d}.png"
        Image.fromarray(np.rint(image).astype(np.uint8), mode="L").save(
            png_dir / name, format="PNG", optimize=True
        )
        names.append(name)
    metadata = {
        "patient_id": str(getattr(ds, "PatientID", "")),
        "source_dicom": str(dcm_path),
        "sop_class_uid": str(ds.SOPClassUID),
        "modality": str(getattr(ds, "Modality", "")),
        "number_of_frames": int(frames.shape[0]),
        "rows": int(frames.shape[1]),
        "columns": int(frames.shape[2]),
        "pixel_dtype": str(frames.dtype),
        "bits_allocated": int(getattr(ds, "BitsAllocated", 0)),
        "photometric_interpretation": str(getattr(ds, "PhotometricInterpretation", "")),
        "window_low": low,
        "window_high": high,
        "png_directory": str(png_dir),
        "png_files": names,
    }
    (patient_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def process_one(package_dir: Path, source_folder: Path, destination: Path) -> dict:
    l3d = find_l3d(source_folder)
    print(f"Now extracting DICOM for patient folder: {source_folder.name}", flush=True)
    # Write once directly into the final output tree. The source folder name is
    # provisional only until PatientID is read from the generated DICOM.
    provisional = destination / safe_name(source_folder.name)
    dicom_dir = provisional / "dicom"
    provisional_dcm = dicom_dir / f"{safe_name(source_folder.name)}.dcm"
    run_native_converter(package_dir, l3d, provisional_dcm)

    header = pydicom.dcmread(str(provisional_dcm), stop_before_pixels=True, force=True)
    raw_id = str(getattr(header, "PatientID", "") or "").strip()
    if not raw_id:
        raise ValueError(f"Generated DICOM has no PatientID: {provisional_dcm}")
    patient_id = safe_name(raw_id)
    patient_dir = destination / patient_id

    if patient_dir != provisional:
        if patient_dir.exists():
            raise FileExistsError(
                f"Output PatientID collision: {patient_dir} already exists "
                f"while processing {source_folder}"
            )
        provisional.rename(patient_dir)
    # After a folder rename, provisional_dcm still has the old source-folder
    # name. Rename that existing file to the required PatientID filename.
    current_dcm = patient_dir / "dicom" / provisional_dcm.name
    final_dcm = patient_dir / "dicom" / f"{patient_id}.dcm"
    if current_dcm != final_dcm:
        current_dcm.rename(final_dcm)

    print(f"Now extracting PNG for PatientID: {patient_id}", flush=True)
    metadata = export_pngs(final_dcm, patient_dir, patient_id)
    return {
        "source_folder": str(source_folder),
        "source_l3d": str(l3d),
        "patient_id": raw_id,
        "output_dicom": str(final_dcm),
        "png_directory": str(patient_dir / "png"),
        "png_count": len(metadata["png_files"]),
        "frames": metadata["number_of_frames"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch L3D -> DICOM -> PNG conversion")
    parser.add_argument("--source", required=True, type=Path, help="Folder containing patient subfolders")
    parser.add_argument("--destination", required=True, type=Path, help="Output folder")
    parser.add_argument("--workers", type=int, default=1, help="Parallel patient conversions; default: 1")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    source, destination = args.source.resolve(), args.destination.resolve()
    package_dir = Path(__file__).resolve().parent
    if not source.is_dir():
        print(f"[ERROR] Source directory does not exist: {source}")
        return 1
    destination.mkdir(parents=True, exist_ok=True)
    folders = sorted(p for p in source.iterdir() if p.is_dir())
    if not folders:
        print(f"[ERROR] No patient folders found in {source}")
        return 1

    print(f"Source folders: {len(folders)}; workers: {args.workers}")
    results, failures = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(process_one, package_dir, folder, destination): folder for folder in folders}
        for job in as_completed(jobs):
            folder = jobs[job]
            try:
                result = job.result()
                results.append(result)
                print(f"[DONE] {folder.name}: {result['png_count']} PNGs -> {result['output_dicom']}")
            except Exception as exc:
                failures.append({"source_folder": str(folder), "error": str(exc)})
                print(f"[ERROR] {folder.name}: {exc}")

    summary = {
        "source_directory": str(source),
        "destination_directory": str(destination),
        "workers": args.workers,
        "patients_succeeded": len(results),
        "folders_failed": len(failures),
        "total_png_slices": sum(r["png_count"] for r in results),
        "results": sorted(results, key=lambda r: r["patient_id"]),
        "failures": failures,
    }
    summary_path = destination / "batch_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Completed: {len(results)} succeeded, {len(failures)} failed")
    print(f"Summary: {summary_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
