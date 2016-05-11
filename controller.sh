#!/bin/bash

export PYTHONPATH=`pwd`
POX=~/pox/pox.py

rm -rf out
mkdir -p out
sudo mn -c
sudo killall python2.7
sudo fuser -k 6633/tcp
#$POX forwarding.controller_stat
#$POX forwarding.l2_learning openflow.spanning_tree --no-flood --hold-down
$POX  openflow.nicira --convert-packet-in forwarding.controller_stat

