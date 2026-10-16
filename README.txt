L3D TO DICOM + PNG - PYTHON BATCH PACKAGE

This package is intended to be run only through:

  python batch_l3d_to_dicom_png.py --source "D:\Research\Raw" --destination "D:\Research\test" --workers 4

INPUT LAYOUT

  source\patient-folder-1\scan.l3d
  source\patient-folder-2\scan.l3d

OUTPUT LAYOUT

  destination\<derived PatientID>\dicom\<derived PatientID>.dcm
  destination\<derived PatientID>\metadata.json
  destination\<derived PatientID>\png\<PatientID>_0000.png
  destination\<derived PatientID>\png\<PatientID>_0001.png
  destination\batch_summary.json

SETUP

Install the Python dependencies once:

  python -m pip install -r requirements.txt

OPTIONS

  --source       Folder containing patient subfolders with .l3d files.
  --destination  Folder where DICOM, PNG, and JSON outputs are written.
  --workers      Number of patient folders to process in parallel. Examples:
                 --workers 4, --workers 6, or --workers 8. Default is 1.

The script writes each DICOM directly into the patient's dicom folder. It does
not create a shared .temporary DICOM folder or make a second DICOM copy.

The native Electron output is captured by the Python script, so low-level
messages such as "Write VolumeInfo" and "PrivateDataIOD" are not printed.
The script instead reports:

  Now extracting DICOM for patient folder: ...
  Now extracting PNG for PatientID: ...

The output folder name is taken from PatientID in the generated DICOM. The
script selects the largest .l3d file if a patient folder contains multiple
L3D files. PNGs are 8-bit grayscale exports of all Enhanced US Volume frames.

The Electron runtime, native BK Medical decoder, DLLs, compiled conversion
modules, and required Node dependencies are included in this package. Do not
move or delete the electron, electron-runner, or app-extracted directories.
