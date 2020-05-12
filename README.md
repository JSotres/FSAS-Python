# Nanoscope Force Volume Data into SQLite Database with Python

In the future this will be a bigger project on the analysis of AFM Force Volume Data.
At present, we provide a function, nanoscopeToSQLite.py, that reads raw Nanoscope Force Volume files and stores their data in SQLite databases.

Developed with python 3.7

Packages used: re, numpy, argparse, sqlite3, io

## Usage

```python
python nanoscopeToSQLite.py -i input_file -o database_file
```

where:

input_file: path to Nanoscope Force Volume file

database_file: path to output sqlite database

## Outcome

The output database will contain two tables: ExperimentsTable and another one named as the input_file (with any dots in the name replaced by \_).

### ExperimentsTable

One row for each experiment.
Only created if it does not already exists.

Columns/fields (experiment general data i.e., not specific for each sample point):

* id (INTEGER): PRIMARY KEY
* ExperimentName (TEXT NOT NULL UNIQUE): name of the input_file
* nRows (INTEGER): number of scan rows (fast axis)
* nColumns (INTEGER): number of scan columns (slow axis)
* nRampPoints (INTEGER): number of points for each ramp/direction
* mapLength (REAL): lateral length of the scanned area (nm).
* rampLength (REAL): ramped distance (nm).

<em>The following are not updated with this program, as the input_file does not contain information on them. They need to be updated afterwards by the user</em>

* photodiodeSensitivity (REAL DEFAULT 1): sensitivity of the photodiode (nm/V)
* forceConstant (REAL DEFAULT 1): spring constant of the cantilever (N/m)
* probeRadius (REAL DEFAULT 1): radius of the probe (nm)

If an entry with a similar ExperimentName already exists, it is replaced, and the corresponding children table dropped before created again.

### Table named as the input_file

Each row corresponds to a sample point of the input_file. 

Columns/fields (data specific for each sample point):

* id (INTEGER): PRIMARY KEY
* ExperimentID (INTEGER NOT NULL): FOREIGN KEY REFERENCES ExperimentsTable(id)
* NX (INTEGER): fast axis index
* NY (INTEGER): slow axis index
* ForceForward (array): numpy array corresponding to the photodetector signal of the approach ramp (V).
* ForceBackward (array): numpy array corresponding to the photodetector signal of the withdrawal ramp  (V).
* Height (REAL): height/topography of the sample point (nm).

Note that SQLite does not support numpy arrays. In order to allow it, the following [approach was followed](https://stackoverflow.com/a/18622264)

## Contributor
[Javier Sotres](https://github.com/JSotres)