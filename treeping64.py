#!/usr/bin/python
''' 
This script simulates a 64-node tree network,
and generate the traffic to overwhelm the controller
'''
from mininet.net import Mininet
from mininet.topolib import TreeTopo
from mininet.log import setLogLevel
from mininet.node import UserSwitch, OVSKernelSwitch  # , KernelSwitch
from mininet.topolib import TreeNet
from mininet.node import RemoteController   
from mininet.node import CPULimitedHost
from mininet.link import TCLink
import time
import random
import signal 
import sys
import os

flush = sys.stdout.flush
PING_PATH = '/usr/bin/ping'

# gracefully stop the simulation
def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    os.system('killall -9 ping')
    sys.exit(0)

# creat the topology and generate traffic
def treePing64():
    results = {}
    outfiles, errfiles = {}, {}
    s = OVSKernelSwitch
    topo = TreeTopo( depth=2, fanout=8)
    IP = '192.168.56.101'
    net = Mininet(topo=topo, switch=s, controller=lambda name: RemoteController( 'c0', IP ), host=CPULimitedHost, link=TCLink) 
    net.start()
    time.sleep(4)
    print "Start Flows"
    # store the inter arrival times of flows
    read_rand_vars = []
    # to determine how much time we need to wait before sending another flow
    # lambda in the inverse of the expected duration
    mean1 = 0.01
    lambd1 = 1.0 / mean1
    mean2 = 0.2
    lambd2 = 1.0 / mean2
    mean3 = 0.001
    lambd3 = 1.0 / mean3
    # flags to set to test different traffic behaviours
    long_term = 1
    low_lod = 0
    fixed = 0
    spike = 0
    mixed = 0
    # local variables
    i = 0
    r = 15
    n_hosts = 64
    # flag used to vary the duration of different load behaviours 
    flag = 0
    for  k in range(0, r):
        for src_idx in range(0, n_hosts):
            server = net.hosts[ src_idx ]
            for dst_idx in range(0, n_hosts):
                if (src_idx == dst_idx):
                    continue
                h = net.hosts[ dst_idx ]
                outfiles[ h ] = 'out/%s.out' % (h.name)
                errfiles[ h ] = 'out/%s.err' % (h.name)
                # Start pings
                h.cmdPrint('ping -c 5', server.IP(), '>>', outfiles[ h ], '2>>', errfiles[ h ], '&' )

                if (long_term == 1):
                    randx = random.expovariate(lambd3)
                elif (low_load == 1):
                    randx = random.expovariate(lambd2)
                elif (fixed == 1):
                    randx = 0.5
                elif (spike == 1):
                    if (flag < 2):
                        print "1) less load"
                        randx = random.expovariate(lambd2)
                    elif (flag >= 2):
                        print "2) high load"
                        randx = random.expovariate(lambd3)
                elif (mixed == 1):
                    # 0 ----0.2--- 3 -----0.001---- 7 ----0.2---- 8 ----- 0.01 ---- 45
                    if (flag < 3):
                        print "1) less load"
                        randx = random.expovariate(lambd2)
                    elif (flag >= 3 and flag < 7):
                        print "2) high load"
                        randx = random.expovariate(lambd3)
                    elif (flag >= 7 and flag <= 8):
                        print "3) less load"
                        randx = random.expovariate(lambd2)
                    elif (flag > 8 and flag <= 45):
                        print "4) high load"
                        randx = random.expovariate(lambd3)
                # end if 
                read_rand_vars.append( randx )
                time.sleep(randx)
            # end if
            i = i + 1
            flag = flag + 1
            if (mixed == 45):
                thresh = 5
            else
                thresh = 5
            if (flag > thresh):
                flag = 0
    # end if
    os.system('killall -9 ping')

    time.sleep(100)
    os.system('killall -9 ping')
    # if you want to check the inter arrival times
    # print read_rand_vars
    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    treePing64()
