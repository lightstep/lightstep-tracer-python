//
// Helper script to bump the version number
//
// TODO: a Node.js dependency in a Python package is not ideal.
//
var fs = require('fs');
var _ = require('underscore');

var version = (fs.readFileSync("VERSION", "utf8") || "1.0.0").replace(/\s+$/, "");
var newVersion = require("semver").inc(version, "patch");
fs.writeFileSync("VERSION", newVersion);
fs.writeFileSync("lightstep/version.py", "LIGHTSTEP_PYTHON_TRACER_VERSION=\"" + newVersion + "\"\n");

// Naive micro-sed on setup.py
var setuppy = _.map(fs.readFileSync("setup.py", "utf8").split("\n"), function(line) {
    return line.replace("'" + version + "'", "'" + newVersion + "'");
}).join("\n");
fs.writeFileSync("setup.py", setuppy);

console.log(version + " -> " + newVersion);
