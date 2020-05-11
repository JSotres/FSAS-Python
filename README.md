# Analysis of AFM Force Volume Data with Python

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

The output database will contain one table, FVData. 

One row for each surface point. 

Columns/fields:
* id: primary key
* NX: fast axis index
* NY: slow axis index
* ForceForward: numpy array corresponding to the photodetector signal of the approach ramp
* ForceBackward: numpy array corresponding to the photodetector signal of the withdrawal ramp
* Height: height(topography)

## Contributor
[Javier Sotres](https://github.com/JSotres)