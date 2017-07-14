setMode -bscan
setCable -p auto
# setCableSpeed -speed 6000000
addDevice -p 1 -file build/pdq_3ch.bit
readIdCode -p 1
program -p 1
quit
