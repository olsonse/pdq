setMode -bscan
setCable -p auto
# setCableSpeed -speed 6000000
addDevice -p 1 -file build/pdq_3ch.bit
readIdCode -p 1
attachFlash -p 1 -spi AT45DB161D
assignfiletoattachedflash -p 1 -file build/pdq_3ch.mcs
program -e -v -p 1 -dataWidth 1 -spionly -loadfpga
quit

# With `xc3sprog` and `fxload2` and using the Xilinx Platform Cable USB II
# and the PDQ board can also be flashed::
#   $ fxload -t fx2 -I /opt/Xilinx/14.7/ISE_DS/ISE/bin/lin64/xusb_xp2.hex -D /dev/bus/usb/001/*`cat /sys/bus/usb/devices/1-3/devnum`
#   $ xc3sprog -c xpc -Ixc3s500e_godil.bit -v build/pdq_3ch.bit:W
