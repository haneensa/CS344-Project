#!/bin/bash

rm -rf out
mkdir -p out
sudo mn -c
sudo killall python2.7
sudo fuser -k 6633/tcp
#sudo ./pingTest.py &
sudo ./treeping64.py

# UNCOMENT IF BOTH TOPO and CONTROLLER ON THE SAME MACINE
#export PYTHONPATH=`pwd`
#POX=~/pox/pox.py
#sudo fuser -k 6633/tcp
#$POX forwarding.controller_stat openflow.spanning_tree --no-flood --hold-down
#$POX  openflow.nicira --convert-packet-in forwarding.prediction
