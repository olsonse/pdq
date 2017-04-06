setMode -bscan
setCable -p auto
addDevice -p 1 -file build/pdq2_3ch.bit
readIdCode -p 1
program -p 1
quit
