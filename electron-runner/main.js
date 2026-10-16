'use strict';
const { app } = require('electron');
const fs = require('fs');
const path = require('path');

// The recovered import/export modules were compiled for a renderer and read
// localStorage while defining a few model enums. The converter does not need
// persisted UI settings, so provide the smallest compatible store before the
// modules are required.
global.localStorage = {
  _data: Object.create(null),
  getItem(k) { return Object.prototype.hasOwnProperty.call(this._data, k) ? this._data[k] : null; },
  setItem(k, v) { this._data[k] = String(v); },
  removeItem(k) { delete this._data[k]; }
};
global.window = global;
global.document = {
  createElementNS() {
    return {
      setAttribute() {},
      addEventListener() {},
      removeEventListener() {},
      style: {}
    };
  },
  createElement() { return this.createElementNS(); }
};

const root = path.dirname(__dirname);
const native = require(path.join(root, 'app-extracted/app-asar-extracted/native'));
const { ImportExport, ImportExportType } = require(path.join(
  root, 'app-extracted/app-asar-extracted/compiled/app/import-export/import-export-module'
));

function getImageData(input) {
  return new Promise((resolve, reject) => {
    native.GetImageData(input, data => {
      if (data == null) reject(new Error('Native decoder returned no image data'));
      else resolve(new Uint8Array(data));
    }, () => true, false);
  });
}
function saveDicom(output, volume) {
  return new Promise((resolve, reject) => {
    native.SaveDicom(output, 0, volume, (result, error) => {
      if (error !== undefined) reject(new Error(String(error)));
      else resolve(result);
    });
  });
}

app.whenReady().then(async () => {
  try {
    const args = process.argv.slice(1).filter(x => !x.startsWith('--app=') && !x.startsWith('--no-'));
    if (args.length < 2) throw new Error('Expected input.l3d output.dcm arguments');
    const input = path.resolve(args[args.length - 2]);
    const output = path.resolve(args[args.length - 1]);
    if (!fs.existsSync(input)) throw new Error(`Input does not exist: ${input}`);
    fs.mkdirSync(path.dirname(output), { recursive: true });
    console.error(`Decoding ${input}`);
    const imageData = await getImageData(input);
    const l3dData = ImportExport.import({
      imageData,
      cal: native.GetCal(),
      acq: native.GetAcq(),
      scanInfo: native.GetHeaders(),
      stitchLine: native.GetStitchLine(),
      clut: native.GetClut(),
      measurements: [], userViews: [], exData: null
    }, { type: ImportExportType.L3D, volume: true, dynamic: false, header: true, clear: false });
    if (!l3dData || !l3dData.volume) throw new Error('L3D conversion produced no volume');
    const dcmData = ImportExport.export(l3dData, {
      type: ImportExportType.DCM, volume: true, dynamic: false,
      header: true, anonymize: false, monochrome: false
    });
    if (!dcmData || !dcmData.volume) throw new Error('DICOM conversion produced no volume');
    await saveDicom(output, dcmData.volume);
    if (!fs.existsSync(output) || fs.statSync(output).size === 0) throw new Error('Output missing or empty');
    console.log(output);
    app.exit(0);
  } catch (e) {
    console.error(`ERROR: ${e && e.stack || e}`);
    app.exit(1);
  }
});
