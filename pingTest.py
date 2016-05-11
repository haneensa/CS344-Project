#!/usr/bin/python
"""
This script creats a linear topology of N hosts and N-1 switches, connected as follows:
h1 <-> s1 <-> s2 .. sN-1
       |       |    |
       h2      h3   hN
- creating a custom topology, LinearTestTopo
- using the ping() test from Mininet()
"""
from mininet.net import Mininet
from mininet.node import UserSwitch, OVSKernelSwitch
from mininet.topo import Topo
from mininet.log import lg
from mininet.util import irange
from mininet.node import RemoteController   
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.cli import CLI
import time
import pylab
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

class LinearTestTopo( Topo ):
    "Topology for a string of N hosts and N-1 switches."

    def __init__( self, N, **params ):

        # Initialize topology
        Topo.__init__( self, **params )

        # Create switches and hosts
        hosts = [ self.addHost( 'h%s' % h )
                  for h in irange( 1, N ) ]
        switches = [ self.addSwitch( 's%s' % s )
                     for s in irange( 1, N - 1 ) ]

        # Wire up switches
        last = None
        for switch in switches:
            if last:
                self.addLink( last, switch )
            last = switch

        # Wire up hosts
        self.addLink( hosts[ 0 ], switches[ 0 ] )
        for host, switch in zip( hosts[ 1: ], switches ):
            self.addLink( host, switch )


def linearBandwidthTest( s ):
    "Check bandwidth at various lengths along a switch chain."
    #lambd = 2
    switchCount = s
    hostCount = switchCount + 1

    topo = LinearTestTopo( hostCount )

    results= []
    outfiles, errfiles = {}, {}
    net = Mininet( topo=topo, switch=OVSKernelSwitch )
    #net = Mininet( topo=topo, switch=UserSwitch )
    net = Mininet(topo=topo, switch=OVSKernelSwitch, controller=lambda name: RemoteController( 'c0', '192.168.56.101' ), host=CPULimitedHost, link=TCLink) 
    #net = Mininet(topo=topo, switch=OVSKernelSwitch, host=CPULimitedHost, link=TCLink) 
    net.start()
    host = net.hosts
    print "Number of hosts"
    print len(host)
    time.sleep(4)
    print "Start Flows"
    read_rand_vars = []
    # to determine how much time we need to wait before sending another flow
    # lambda in the inverse of the expected duration
    mean1 = 0.01
    lambd1 = 1.0 / mean1
    mean2 = 0.1
    lambd2 = 1.0 / mean2
    mean3 = 0.001
    lambd3 = 1.0 / mean3
    long_term = 1
    short_term = 0
    fixed = 0
    i = 0
    buckets = 0
    r = 3
    # to increase number of new traffic
    for  k in range(0, r):
        for src_idx in range(0, s):
            server = net.hosts[ src_idx ]
            for dst_idx in range(0, s):
                if (src_idx == dst_idx):
                    continue
                h = net.hosts[ dst_idx ]
                outfiles[ h ] = 'out/%s.out' % (h.name)
                errfiles[ h ] = 'out/%s.err' % (h.name)
                # Start pings
                h.cmdPrint('ping -c 1', server.IP(), '>>', outfiles[ h ], '2>>', errfiles[ h ], '&' )

                if (long_term == 1):
                    randx = random.expovariate(lambd3)
                elif (short_term == 1):
                    randx = random.expovariate(lambd2)
                elif (fixed == 1):
                    randx = 1
                elif (i%2 == 0):
                    randx = 0.5
                else:
                    randx = random.expovariate(lambd1)
                read_rand_vars.append( randx )
                time.sleep(randx)
                buckets = buckets + 1
            time.sleep(2)
            i = i + 1
    os.system('killall -9 ping')
        

    time.sleep(100)
    os.system('killall -9 ping')

    print "Random Variables:"
    print read_rand_vars
    # plot the interarival time to verify behaiviour
    pylab.hist(read_rand_vars, buckets)
    pylab.xlabel("Number range")
    pylab.ylabel("Count")
    pylab.savefig("fig.png")

    net.stop()
    os.system('killall -9 python2.7')
    print "Done. press ctl+C please"
    os.system('kill %d' % os.getpid())

if __name__ == '__main__':
    lg.setLogLevel( 'info' )
    size = 50
    print "*** Running linearBandwidthTest", size
    signal.signal(signal.SIGINT, signal_handler)
    linearBandwidthTest( size  )
