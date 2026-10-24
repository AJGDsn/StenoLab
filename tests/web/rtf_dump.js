// Prints the entries web/rtf.js reads from an RTF file as JSON, for
// check_rtf_parity.py and test_rtf_parity.py.
const fs = require("fs");
const path = require("path");
const { readRtfDictionary, decodeRtfBytes } = require(path.join(__dirname, "..", "..", "web", "rtf.js"));
const entries = readRtfDictionary(decodeRtfBytes(fs.readFileSync(process.argv[2])));
process.stdout.write(JSON.stringify(entries));
