#!/bin/sh

mkdir -p xilinx
cd xilinx
wget -N http://m-labs.hk/build/xilinx_ise_14.7_s3_s6.tar.gz.gpg
echo "$secret" | gpg --passphrase-fd 0 xilinx_ise_14.7_s3_s6.tar.gz.gpg
tar -xzf xilinx_ise_14.7_s3_s6.tar.gz
wget -N http://m-labs.hk/build/xilinx_webpack.lic.gpg
echo "$secret" | gpg --passphrase-fd 0 xilinx_webpack.lic.gpg
mkdir ~/.Xilinx
mv xilinx_webpack.lic ~/.Xilinx/Xilinx.lic
