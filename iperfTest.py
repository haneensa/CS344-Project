#!/usr/bin/python
"""
Test bandwidth (using iperf) on linear networks of varying size,
using both kernel and user datapaths.

We construct a network of N hosts and N-1 switches, connected as follows:

h1 <-> s1 <-> s2 .. sN-1
       |       |    |
       h2      h3   hN

WARNING: by default, the reference controller only supports 16
switches, so this test WILL NOT WORK unless you have recompiled
your controller to support 100 switches (or more.)

In addition to testing the bandwidth across varying numbers
of switches, this example demonstrates:

- creating a custom topology, LinearTestTopo
- using the ping() and iperf() tests from Mininet()
- testing both the kernel and user switches

"""
from mininet.net import Mininet
from mininet.node import UserSwitch, OVSKernelSwitch
from mininet.topo import Topo
from mininet.log import lg
from mininet.util import irange
from mininet.cli import CLI
import time
import psutil
import pylab
import random
import signal 
import sys
import os
import sys

flush = sys.stdout.flush
IPERF_PATH = '/usr/bin/iperf'
IPERF_PORT = 5001
IPERF_PORT_BASE = 5001

def signal_handler(signal, frame):
    print('You pressed Ctrl+C!')
    os.system('killall -9 ' + IPERF_PATH)
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
    f = open('out/lambd.out', 'a')
    switchCount = s
    hostCount = switchCount + 1

    topo = LinearTestTopo( hostCount )

    results= []
    outfiles, errfiles = {}, {}
    net = Mininet( topo=topo, switch=OVSKernelSwitch )
    net.start()
    host = net.hosts
    bandwidth = 0
    print "Number of hosts"
    print len(host)
    time.sleep(4)
    print "Test Connectivity with Ping"
    #net.pingAll()
    time.sleep(3)
    print "Start Flows"
    buckets = 0
    port_count = 0
    read_rand_vars = []
    # to determine how much time we need to wait before sending another flow
    # lambda in the inverse of the expected duration
    mean1 = 0.001
    lambd1 = 1.0 / mean1
    mean2 = 2
    lambd2 = 1.0 / mean2
    mean3 = 0.01
    lambd3 = 1.0 / mean3
    long_term = 0
    short_term = 0
    i = 0
    for src_idx in range(0, 1):
        S = net.hosts[ src_idx ]
        for dst_idx in range(0, s):
            #print "Iperf %d -> %d" % (src, dst)
            if (src_idx == dst_idx):
                continue
            buckets = buckets + 1
            # start server iperf
            d = net.hosts[ dst_idx ]
            port = IPERF_PORT_BASE + port_count
            S.cmd('iperf -s -p ', port, '&')
            outfiles[ dst_idx ] = 'out/perf%s.txt' % d.name
            errfiles[ dst_idx ] = 'out/perf%s.txt' % d.name
            d.cmd( 'echo >', outfiles[ dst_idx ])
            d.cmd('iperf -c', S.IP(), ' -p ', port, '-t 5 >', outfiles[ dst_idx ], '2>', errfiles[ dst_idx ], '&')
            #f.write( str(randx) )
            #f.write('\n')
            if (long_term == 1):
                randx = random.expovariate(lambd3)
            elif (short_term == 1):
                randx = random.expovariate(lambd2)
            elif (i%2 == 0):
                #randx = 0.00#01 # short interval
                randx = random.expovariate(lambd1)
            else:
                #randx = 3      # long inteval for the spike
                randx = random.expovariate(lambd2)
            read_rand_vars.append( randx )
            #time.sleep(randx/1000)
            time.sleep(randx)
            port_count += 1
        i = i + 1

    time.sleep(100)
    os.system('killall -9 ' + IPERF_PATH)

    print "Random Variables:"
    print read_rand_vars
    # plot the interarival time to verify behaiviour
    pylab.hist(read_rand_vars, buckets)
    pylab.xlabel("Number range")
    pylab.ylabel("Count")
    pylab.savefig("fig.png")

    net.stop()
    print "Done. quit() please"
    os.system('kill %d' % os.getpid())

if __name__ == '__main__':
    lg.setLogLevel( 'info' )
    size = 50
    print "*** Running linearBandwidthTest", size
    signal.signal(signal.SIGINT, signal_handler)
    linearBandwidthTest( size  )
