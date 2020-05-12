###############################################################################
# Import of neccesary packages
###############################################################################
import re
import numpy as np
import argparse
import sqlite3
import io
import matplotlib.pyplot as plt

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
        checkTableExists()
        closeDataBaseConnection()
        createTables()
        populateTables()
        testFunction()
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
        # Name of the Force Volume file to be used in the database
        # SQLite does not like dots...
        self.file_name2 = file_name.replace('.', '_')

        # Name of the database
        self.database_name = database_name

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

    def checkTableExists(self):
        '''
        Checks if a table with name equalt to that of input
        force volume name already exists in the database. If so,
        asks the user if it should proceed. If so,it will drop
        the already existing table
        '''
        sql_command = f"""
        SELECT count(name) FROM sqlite_master
        WHERE type='table' AND name='{self.file_name2}';
        """
        self.cursor.execute(sql_command)

        if self.cursor.fetchone()[0] == 1:
            string_input = """
            A table with the file name already exists in the database.
            If you choose to countinue, that table will be deleted.
            If you want to continue press [y], if not, press any other
            key, then Enter:

            """
            x = str(input(string_input))
            if x == 'y' or x == 'Y':
                pass
            else:
                raise

    def createTables(self):
        '''
        Creates 2 tables in the database.
        1- ExperimentsTable: a row for each force volume experiment
        with columns associated with experimental parameters of relevance.
        It is created only if it does not exists already.
        2- A table named as the input file with columns for the Force
        Volume and topography data of the specific loaded experiment. If
        a table with the same name existed, the old one is previously
        deleted.
        '''
        self.checkTableExists()
        sql_command1 = """
        CREATE TABLE IF NOT EXISTS ExperimentsTable (
        id INTEGER,
        ExperimentName TEXT NOT NULL UNIQUE,
        nRows INTEGER,
        nColumns INTEGER,
        nRampPoints INTEGER,
        mapLength REAL,
        rampLength REAL,
        photodiodeSensitivity REAL DEFAULT 1,
        forceConstant REAL DEFAULT 1,
        probeRadius REAL DEFAULT 1,
        PRIMARY KEY (id)
        );
        """
        sql_command2 = f"""
        DROP TABLE IF EXISTS {self.file_name2}
        """
        sql_command3 = f"""
        CREATE TABLE IF NOT EXISTS {self.file_name2} (
        id INTEGER,
        ExperimentID INTEGER NOT NULL,
        NX INTEGER,
        NY INTEGER,
        ForceForward array,
        ForceBackward array,
        Height REAL,
        PRIMARY KEY (id),
        FOREIGN KEY (ExperimentID) REFERENCES ExperimentsTable(id)
        );
        """
        self.cursor.execute(sql_command1)
        self.cursor.execute(sql_command2)
        self.connector.commit()
        self.cursor.execute(sql_command3)
        self.connector.commit()

    def populateTables(self):
        '''
        Populates the tables ExperimentsTable and the one named as
        the input file.
        If an entry with a similar ExperimentName already exists in
        ExperimentsTable, thant entry is replaced.
        '''
        sql_command = """
        INSERT OR REPLACE INTO ExperimentsTable
        (ExperimentName, nRows, nColumns,
        nRampPoints, mapLength, rampLength) values
        (?, ?, ?, ?, ?, ?)
        """
        self.cursor.execute(sql_command, (
            self.file_name2,
            self.numberOfMapRows,
            self.numberOfMapColumns,
            self.numberOfRampPoints,
            self.mapLength,
            self.rampLength
        ))

        sql_command2 = f"""
        SELECT id FROM ExperimentsTable
        WHERE ExperimentName='{self.file_name2}';
        """
        self.cursor.execute(sql_command2)

        ExperimentID = self.cursor.fetchone()[0]

        for i in range(self.numberOfMapRows):
            for j in range(self.numberOfMapColumns):
                self.cursor.execute(
                        f"""INSERT INTO {self.file_name2}
                           (ExperimentID, NX, NY,
                           ForceForward, ForceBackward, Height)
                           values (?, ?, ?, ?, ?, ?)""",
                        (ExperimentID, i, j, self.FVDataArray[i, j, 0, :],
                         self.FVDataArray[i, j, 1, :],
                         self.topographyArray[i, j])
                        )
        self.connector.commit()

    def testFunction(self):
        '''
        General method for testing during development
        '''
        sql_command = f"""
                      SELECT ForceForward, ForceBackward, Height
                      FROM {self.file_name2}
                      WHERE id = 1;
                      """
        self.cursor.execute(sql_command)
        data = self.cursor.fetchall()
        for d in data[0]:
            print(d)
            plt.plot(d)
            plt.show()


###############################################################################
# Run if this is the main program
###############################################################################
if __name__ == "__main__":
    # Load parsed input force volume file and output database
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=True,
                    help="path to input force volume file")
    ap.add_argument("-o", "--output", required=True,
                    help="path to output database")
    args = vars(ap.parse_args())

    # Register adapter and converter for
    # sqlite3 numpy array to bytes conversions
    sqlite3.register_adapter(np.ndarray, adapt_array)
    sqlite3.register_converter("array", convert_array)

    # Create an object of the NanoscopeForceVolumeFileToDataBase class
    fvObject = NanoscopeForceVolumeFileToDataBase(
        args['input'],
        args['output']
    )

    # Reads the header of file_name, and populates
    # the headerParameters dictionary
    fvObject.readHeader()

    # Finds meaningful parameters from the key values in headerParameters
    fvObject.headerToParameters()

    # Reads Topography (binary) data from file_name
    fvObject.readTopography()

    # Reads Force Volume (FV) data from file_name
    fvObject.readFV()

    # Connects to the database
    fvObject.connectToDataBase()

    # Creates a table in the database
    fvObject.createTables()

    # Inserts FV and Tpography data into the table
    fvObject.populateTables()

    # Closes the connection to the database
    fvObject.closeDataBaseConnection()
