#!/usr/bin/python
"Create a 64-node tree network, and test connectivity using ping."
from mininet.net import Mininet
from mininet.topolib import TreeTopo
from mininet.log import setLogLevel
from mininet.node import UserSwitch, OVSKernelSwitch  # , KernelSwitch
from mininet.topolib import TreeNet
from mininet.node import RemoteController   
from mininet.node import CPULimitedHost
from mininet.link import TCLink
# extra
import time
import random
import signal 
import sys
import os

flush = sys.stdout.flush
PING_PATH = '/usr/bin/ping'

def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    os.system('killall -9 ping')
    #net.stop()
    sys.exit(0)

def treePing64():
    "Run ping test on 64-node tree networks."

    results = {}
    outfiles, errfiles = {}, {}
    #s = UserSwitch
    s = OVSKernelSwitch
    topo = TreeTopo( depth=2, fanout=8)

    net = Mininet(topo=topo, switch=s, controller=lambda name: RemoteController( 'c0', '192.168.56.101' ), host=CPULimitedHost, link=TCLink) 
    #net = Mininet(topo=topo, switch=s, host=CPULimitedHost, link=TCLink) 
    net.start()

    time.sleep(4)
    print "Start Flows"
    read_rand_vars = []
    # to determine how much time we need to wait before sending another flow
    # lambda in the inverse of the expected duration
    mean1 = 0.01
    lambd1 = 1.0 / mean1
    mean2 = 0.2
    lambd2 = 1.0 / mean2
    mean3 = 0.001
    lambd3 = 1.0 / mean3
    long_term = 1
    short_ter = 0
    fixed = 0
    i = 0
    r = 15
    #net.pingAll()
    a = 64
    flag = 0
    # to increase number of new traffic
    v = 0.5
    for  k in range(0, r):
        for src_idx in range(0, a):
            server = net.hosts[ src_idx ]
            for dst_idx in range(0, a):
                if (src_idx == dst_idx):
                    continue
                h = net.hosts[ dst_idx ]
                outfiles[ h ] = 'out/%s.out' % (h.name)
                errfiles[ h ] = 'out/%s.err' % (h.name)
                # Start pings
                h.cmdPrint('ping -c 5', server.IP(), '>>', outfiles[ h ], '2>>', errfiles[ h ], '&' )

                if (long_term == 1):
                    randx = random.expovariate(lambd3)
                elif (short_term == 1):
                    randx = random.expovariate(lambd2)
                elif (fixed == 1):
                    randx = 0.5
                #elif (flag < 2):
                #    print "1) less load"
                #    randx = random.expovariate(lambd2)
                #elif (flag >= 2):
                #    print "2) high load"
                #    randx = random.expovariate(lambd3)
                elif (flag < 3):#2 rounds
                    print "1) less load"
                    randx = random.expovariate(lambd2)
                elif (flag >= 3 and flag < 7):#4
                    print "2) high load"
                    randx = random.expovariate(lambd3)
                elif (flag >= 7 and flag <= 8):#2
                    print "3) less load"
                    randx = random.expovariate(lambd2)
                elif (flag > 8 and flag <= 45):#?
                    print "4) high load"
                    randx = random.expovariate(lambd3)

                read_rand_vars.append( randx )
                time.sleep(randx)
            #time.sleep(0.5)
            i = i + 1
            # 0 ----0.2--- 3 -----0.001---- 7 ----0.2---- 8 ----- 0.01 ---- 45
            flag = flag + 1
            #if (flag > 5):
            if (flag > 45):
                flag = 0
    os.system('killall -9 ping')
        

    time.sleep(100)
    os.system('killall -9 ping')
    # if you want to check the inter arrival times
    # print read_rand_vars

    net.stop()

if __name__ == '__main__':
    setLogLevel( 'info' )
    treePing64()
