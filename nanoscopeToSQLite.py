###############################################################################
# Import of neccesary packages
###############################################################################
import re
import numpy as np
import argparse
import sqlite3
import io

###############################################################################
# numpy arrays are not supported by sqlite. We need to register them as new
# data types. For this, we need to create an adapter and a converter.
###############################################################################


def adapt_array(arr):
    out = io.BytesIO()
    np.save(out, arr)
    out.seek(0)
    return sqlite3.Binary(out.read())


def convert_array(text):
    out = io.BytesIO(text)
    out.seek(0)
    return np.load(out)

###############################################################################
# A class named NanoscopeForceVolumeFileToDataBase is declared, which contains
# all neccesary methods for reading data from force volume files and storing
# it in a sqlite database
###############################################################################


class NanoscopeForceVolumeFileToDataBase():
    '''
    Class that open and read Nanoscope Force Volume Files,
    then saves data in SQLite database.
    Attributes:
        file_name: Name of the Nanoscope Force Volume File
        database_name: Name of the database.
        header_end: For checking whether the end of the Force Volume
                    file header has been reached.
        eof: For checking whether the end of the Force Volume file
             has been reached.
        headerParameters: Dictionary for parameters of relevance within
                          the Force Volume file header.

        *** Attributes specific for the Force Volume Measurement ***

        numberOfMapRows: Number of rows (fast axis) in the Force
                         Volume measurement.
        numberOfMapColumns: Number of columns (slow axis) in the Force
                            Volume measurement.
        mapLength: Lateral dimension (in nm) of the scanned area.
        rampLength: Ramped distance (in nm).
        numberOfRampPoints: number of points in each ramp.
        scanIncrement: distance between ramp points.
        pixelLengthColumn: Lateral dimension of a pixel in the slow axis.
        pixelLengthRow: Lateral dimension of a pixel in the fast axis.

        *** Numpy arrays where the data read from the FV file are stored ***
        FVDataArray: For storing FV data.
        topographyArray: For storing topography(height) data.

        *** Connector anc cursor for sqlite ***
        connector
        cursor

    Methods:
        __init__()
        readHeader()
        searchForParameters()
        searchForHeaderEnd()
        headerToParameters()
        readTopography()
        readFV()
        connectToDataBase()
        closeDataBaseConnection()
        createTable()
        populateFVTable()
    '''

    def __init__(self, file_name, database_name):
        '''
        Initializes an object of the class NanoscopeForceVolumeFiles,
        uses it for reading the data in the parsed Force Volume file
        and saves it in a sqlite database.
        Input parameters:
        file_name: name of the Force Volume file.
        database_name: name of the sqlite database
        '''

        # We initialize the attribute headerParameters, a dictionary
        # with keys corresponding to strings that identify the lines
        # in the Force Volume file header with relevant information
        self.headerParameters = {'Sens. Zsens:': [], '2:Z scale:': [],
                                 'Samps/line:': [], 'Data offset': [],
                                 'Scan Size:': [], 'Z magnify:': [],
                                 '4:Ramp size:': [], 'Force Data Points:': [],
                                 'Number of lines:': []}

        # At the beginning we are not at the end of the header
        # or at the endof the file
        self.header_end = 0
        self.eof = 0

        # Name of the Force Volume file
        self.file_name = file_name

        # Reads the header of file_name, and populates the
        # headerParameters dictionary
        self.readHeader()

        # Finds meaningful parameters from the key values in headerParameters
        self.headerToParameters()

        # Reads Topography (binary) data from file_name
        self.readTopography()

        # Reads Force Volume (FV) data from file_name
        self.readFV()

        # Name of the database
        self.database_name = database_name

        # Connects to the database
        self.connectToDataBase()

        # Creates a table in the database
        self.createTable()

        # Inserts FV and Tpography data into the table
        self.populateFVTable()

        # Closes the connection to the database
        self.closeDataBaseConnection()

    def readHeader(self):
        '''
        Reads the header of the Force Volume File file_name
        '''
        file = open(self.file_name, 'r', encoding='cp1252')

        # Keep reading the file line by line until the end of
        # the header (or the end of the file) is reached.
        # For each line, check whether it contains the keys
        # of headParameters, and if so populate their values, by
        # calling to searchForParameters(). Then, check if the end
        # of the header has been reached by calling searchForHeaderEnd()
        while (not self.header_end) and (not self.eof):
            for line in file:
                self.searchForParameters(line)
                self.searchForHeaderEnd(line, r'\*File list end')
                if self.header_end == 1:
                    break
            else:
                self.eof = 1
        file.close()

    def searchForParameters(self, _line):
        '''
        Identifies whether the input string, _line, contains one of the
        keys of headParameters. If so, pupulates its values with numbers
        contained in _line as well.
        '''
        for key in self.headerParameters:
            if re.search(re.escape(key), _line):
                # print(_line)
                numbers = re.findall(r'\d+\.?\d+', _line)
                # If _line contains the strings 'LSB' or '@', only populate
                # the key value with the last number from _line. If not,
                # populate it with all numbers.
                if re.search(r'LSB', _line) or re.search(r'@', _line):
                    self.headerParameters[key].append(float(numbers[-1]))
                else:
                    for number in numbers:
                        self.headerParameters[key].append(float(number))

    def searchForHeaderEnd(self, _line, _string):
        '''
        Checks if the end of the header has been reached
        '''
        if re.search(r'\*File list end', _line):
            self.header_end = 1
        else:
            self.header_end = 0

    def headerToParameters(self):
        '''
        Obtains meaningful, understandable, parameters from the key values
        from headParameters.
        '''
        self.numberOfMapRows = int(
                self.headerParameters['Number of lines:'][1])
        self.numberOfMapColumns = int(
                self.headerParameters['Samps/line:'][6])
        self.mapLength = self.headerParameters[
                'Scan Size:'][0]
        self.rampLength = (self.headerParameters['4:Ramp size:'][0]
                           * self.headerParameters['Sens. Zsens:'][0])
        self.numberOfRampPoints = int(self.headerParameters['Samps/line:'][1])

        self.scanIncrement = self.rampLength/(self.numberOfRampPoints-1)
        self.pixelLengthColumn = self.mapLength/self.numberOfMapRows
        self.pixelLengthRow = self.mapLength/self.numberOfMapColumns

    def readTopography(self):
        '''
        Reads (binary) topography data contained in the Force Volume file
        and (temporally) saves it in the attribute topographyArray 
        '''
        file = open(self.file_name, 'rb')
        file.seek(int(self.headerParameters['Data offset'][0]))
        s = file.read(2*int(self.headerParameters['Samps/line:'][0])**2)
        self.topographyArray = np.frombuffer(s, dtype='int16').reshape(
                (self.numberOfMapRows, self.numberOfMapColumns)
        )
        self.topographyArray = self.topographyArray * (
                (self.headerParameters['Sens. Zsens:'][0] *
                 self.headerParameters['2:Z scale:'][0]) /
                (65535+1)
        )
        file.close()

    def readFV(self):
        '''
        Reads (binary) force volume data contained in the Force Volume file
        and (temporally) saves it in the attribute FVDataArray
        '''
        file = open(self.file_name, 'rb')
        file.seek(int(self.headerParameters['Data offset'][1]))
        bufferedData = file.read(
                4 * self.numberOfRampPoints *
                self.numberOfMapRows *
                self.numberOfMapColumns)
        self.FVDataArray = np.frombuffer(
                bufferedData, dtype='int16', count=-1
        ).reshape(
                (self.numberOfMapRows,
                 self.numberOfMapColumns,
                 2,
                 self.numberOfRampPoints)
        )*0.000375
        file.close()

    def connectToDataBase(self):
        '''
        Connects to the database
        '''
        self.connector = sqlite3.connect(
                self.database_name,
                detect_types=sqlite3.PARSE_DECLTYPES
        )
        self.cursor = self.connector.cursor()

    def closeDataBaseConnection(self):
        '''
        Closes the connection to the database
        '''
        self.cursor.close()
        self.connector.close()

    def createTable(self):
        '''
        Creates a table, FVData, in the database with columns
        for the Force Volume and topography data
        '''
        c = self.connector.cursor()
        sql_command = """
        CREATE TABLE IF NOT EXISTS FVData (
        id INTEGER,
        NX INTEGER,
        NY INTEGER,
        ForceForward array,
        ForceBackward array,
        Height REAL,
        PRIMARY KEY (id));
        """
        c.executescript(sql_command)
        self.connector.commit()

    def populateFVTable(self):
        '''
        Populates the table FVData with Force Volume and topography data
        '''
        for i in range(self.numberOfMapRows):
            for j in range(self.numberOfMapColumns):
                self.cursor.execute(
                        """INSERT INTO FVData 
                           (NX, NY, ForceForward, ForceBackward, Height) 
                           values (?, ?, ?, ?, ?)""",
                        (i, j, self.FVDataArray[i, j, 0, :],
                         self.FVDataArray[i, j, 1, :],
                         self.topographyArray[i, j])
                        )
        self.connector.commit()


###############################################################################
# Run if this is the main program
###############################################################################
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True,
                    help="path to input force volume file")
    ap.add_argument("-o", "--output", required=True,
                    help="path to output database")
    args = vars(ap.parse_args())
    sqlite3.register_adapter(np.ndarray, adapt_array)
    sqlite3.register_converter("array", convert_array)
    NanoscopeForceVolumeFileToDataBase(args['input'], args['output'])
