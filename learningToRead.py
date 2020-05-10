import re

file_name = 'MucinRh0Hour3.004'

searchString=[]

searchString.append(r'\@Sens. Zsens:')
searchString.append(r'\@2:Z scale:')
searchString.append(r'\Samps/line:')
searchString.append(r'\Data offset')
searchString.append(r'\Scan Size:')
searchString.append(r'\@Z magnify:')
searchString.append(r'\@4:Ramp size:')
searchString.append(r'\Force Data Points:')
searchString.append(r'\Number of lines:')

valueCounter =[]
numberStrings = len(searchString)

def searchForHeaderEnd(_line, _string):
	#print(_line)
	if re.search(r'\*File list end',line):
		print('aqui fin of header')
		return 1
	else:
		return 0


def searchForStrings(_line, _searchString):
	
	for q in range(len(_searchString)):
		#print(q)
		if re.search(re.escape(_searchString[q]), _line):
			print(_line)
			numbers = re.findall(r'\d+\.?\d+', _line)
			print(numbers)
			print(numbers[-1])
		

for i in range(numberStrings):
	valueCounter.append(1)

header_end = 0
eof = 0

file = open(file_name, 'r', encoding='cp1252')

while (not header_end) and (not eof):
	for line in file:
		searchForStrings(line, searchString)
		if searchForHeaderEnd(line, r'\*File list end')==1:
			header_end=1
			break
			



	




file.close()

