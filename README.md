# L3D to DICOM + PNG

<p align="center">
  <strong>Batch conversion for BK Medical <code>.l3d</code> studies</strong><br>
  Convert L3D volumes into standards-compliant DICOM files and 8-bit PNG frames on Windows.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows-0078D4?logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/python-3.x-3776AB?logo=python&logoColor=white" alt="Python 3">
  <img src="https://img.shields.io/badge/output-DICOM%20%7C%20PNG-4C1" alt="DICOM and PNG output">
  <img src="https://img.shields.io/badge/license-see%20repository-555" alt="License">
</p>

## Overview

This package provides a repeatable, scriptable workflow for converting BK Medical
L3D ultrasound studies:

```text
.l3d study  →  native BK Medical decoder  →  Enhanced US Volume DICOM  →  PNG frames
```

The bundled Electron runtime, native decoder, compiled conversion modules, DLLs,
and Node dependencies are included in the repository. The Python wrapper
orchestrates the conversion, extracts DICOM metadata, exports every volume frame
as an 8-bit grayscale PNG, and writes a machine-readable batch summary.

## Features

- **Batch processing** — discovers patient folders and processes them in parallel.
- **Native conversion** — uses the included BK Medical decoder to generate DICOM.
- **DICOM validation** — verifies the generated file before continuing.
- **Frame export** — converts all Enhanced US Volume frames to optimized PNG files.
- **Metadata capture** — writes per-patient metadata and a batch-level summary.
- **Collision protection** — derives output folders from DICOM `PatientID` values and
  stops on conflicting output folders instead of silently overwriting data.
- **Deterministic input selection** — when a patient folder contains multiple
  `.l3d` files, the largest file is selected.

## Requirements

- Windows
- Python 3.x
- A source directory containing patient subfolders with `.l3d` files
- The bundled `electron`, `electron-runner`, and `app-extracted` directories

> **Important:** Keep the bundled runtime directories in the same directory as
> `batch_l3d_to_dicom_png.py`. Do not move, rename, or delete them.

## Installation

Open PowerShell or Command Prompt in the project directory and install the
Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

The required Python packages are:

- [pydicom](https://pydicom.github.io/) — DICOM reading and metadata access
- [NumPy](https://numpy.org/) — frame and pixel-array processing
- [Pillow](https://python-pillow.org/) — PNG encoding

## Quick start

### 1. Prepare the input directory

Organize studies into one patient folder per study. Nested folders are supported
when locating `.l3d` files:

```text
demo-input\
├── patient-folder-1\
│   └── scan.l3d
└── patient-folder-2\
    └── scan.l3d
```

### 2. Run the batch conversion

Use demo paths such as these in documentation, testing, or a local trial:

<p><strong><span style="color: red;">⚠️ WARNING: Change both the <code>--source</code> and <code>--destination</code> folders below before running this command. These are example paths only. Running it without updating them may cause an error or write output to an unintended location.</span></strong></p>

```powershell
python batch_l3d_to_dicom_png.py --source "C:\path\to\source-folder" --destination "C:\path\to\output-folder" --workers 4
```

Replace the two demo paths with your own directories. `--workers 4` allows up to
four patient folders to be processed concurrently.

### 3. Review the result

The command creates a destination tree similar to:

```text
demo-output\
├── <PatientID>\
│   ├── dicom\
│   │   └── <PatientID>.dcm
│   ├── png\
│   │   ├── <PatientID>_0000.png
│   │   ├── <PatientID>_0001.png
│   │   └── ...
│   └── metadata.json
└── batch_summary.json
```

The output folder name is derived from the generated DICOM `PatientID`, not
necessarily the source folder name.

## Command-line options

| Option | Required | Description |
| --- | :---: | --- |
| `--source PATH` | Yes | Folder containing patient subfolders with `.l3d` files. |
| `--destination PATH` | Yes | Folder where DICOM, PNG, and JSON files are written. |
| `--workers N` | No | Number of concurrent patient conversions. Defaults to `1`; must be at least `1`. |

For a conservative run, use one worker:

```powershell
python batch_l3d_to_dicom_png.py --source "C:\path\to\source-folder" --destination "C:\path\to\output-folder" --workers 1
```

## Output files

- **`<PatientID>.dcm`** — the generated Enhanced US Volume DICOM object.
- **`<PatientID>_NNNN.png`** — one 8-bit grayscale PNG per DICOM frame.
- **`metadata.json`** — patient ID, modality, frame dimensions, pixel details,
  window range, and generated PNG filenames.
- **`batch_summary.json`** — source and destination paths, worker count, success
  and failure totals, per-study results, and error details.

The script writes each DICOM directly to the patient's `dicom` directory. It
does not create a shared temporary DICOM directory or a second DICOM copy.

## Processing behavior

1. Patient folders are discovered directly below `--source`.
2. The largest `.l3d` file under each patient folder is selected.
3. The bundled native converter generates a DICOM file.
4. The generated DICOM signature and Enhanced US Volume SOP Class are validated.
5. Frames are windowed using DICOM window values when available; otherwise a
   percentile-based range is calculated.
6. PNG frames and metadata are written under the derived `PatientID`.
7. `batch_summary.json` is written after all folders finish.

The process exits with code `0` only when every patient folder succeeds. If one
or more folders fail, the summary is still written and the process exits with
code `1`.

## Troubleshooting

### `Missing Electron runtime`

Run the command from the project as checked out, and confirm that these paths
exist beside the Python script:

```text
electron\electron.exe
electron-runner\
app-extracted\
```

### `No patient folders found`

Ensure that `--source` exists and contains one or more immediate subfolders.
Each patient folder must contain at least one `.l3d` file somewhere below it.

### Conversion failures

Inspect the terminal output and the `failures` array in
`batch_summary.json`. Failed folders do not prevent successful folders from
being summarized, but the overall process returns exit code `1`.

### Existing output folder

The converter intentionally stops on a `PatientID` collision rather than
overwriting an existing patient output. Choose a new destination or archive the
previous output first.

## Data handling and safety

- Work on copies of source data when possible.
- Confirm that generated DICOM metadata is appropriate for your intended use.
- Treat DICOM and PNG output as potentially sensitive medical data.
- Store input and output directories with access controls appropriate to your
  organization and applicable privacy requirements.

## Repository layout

```text
batch_l3d_to_dicom_png.py  # Python batch conversion entry point
requirements.txt           # Python dependencies
electron\                  # Bundled Electron runtime
electron-runner\           # Native conversion runner
app-extracted\             # Bundled application and decoder resources
```

## License

See the license information distributed with this repository and its bundled
components before redistributing or deploying the package.
