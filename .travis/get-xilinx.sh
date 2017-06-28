#!/bin/sh

cd cache
wget -N http://m-labs.hk/build/xilinx_ise_14.7_s3_s6.tar.gz.gpg
wget -N http://m-labs.hk/build/xilinx_webpack.lic.gpg

cd ..
echo "$secret" \
	| gpg --passphrase-fd 0 -d cache/xilinx_ise_14.7_s3_s6.tar.gz.gpg \
	| tar xz
mkdir ~/.Xilinx
echo "$secret" \
	| gpg --passphrase-fd 0 -d cache/xilinx_webpack.lic.gpg \
	> ~/.Xilinx/Xilinx.lic
