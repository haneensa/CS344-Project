# Copyright 2011 James McCauley
#
# This file is part of POX.
#
# POX is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# POX is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.  If not, see <http://www.gnu.org/licenses/>.

"""
An L2 learning switch.

It is derived from one written live for an SDN crash course.
It is somwhat similar to NOX's pyswitch in that it installs
exact-match rules for each flow.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.util import str_to_bool
import time
import psutil
from pox.lib.util import dpidToStr
import threading
from pox.lib.recoco import Timer
from datetime import datetime
from pox.openflow.of_json import *


log = core.getLogger()

##### Global Variables #####

# flow counting within interval
flow_count = 0

# total flows through duration
total_flows = 0

# inter arrival time of flows
inter_arrival_sum = 0.0
old_arrival = 0.0
avg_inter_arrival = 0.0
inter_arrival_time = 0.0

# controller processing time
process_time = 0.0
process_time_sum = 0.0
process_time_avg = 0.0

# sent and received packets within interval
current_sent_pkts = psutil.net_io_counters().packets_sent
old_sent_pkts = current_sent_pkts

current_recv_pkts = psutil.net_io_counters().packets_recv
old_recv_pkts = current_recv_pkts

sent_pkts_interval = 0
recv_pkts_interval = 0

# used RAM within interval
# according to psutil documentation =>  used: memory used, calculated differently depending on the platform and designed for informational purposes only.
used_memory = 0
current_RAM = psutil.virtual_memory().used
old_RAM = current_RAM

# used buffer within interval
# according to psutil documentation => buffers: cache for things like file system metadata.
used_buffer = 0
current_buffer = psutil.virtual_memory().buffers
old_buffer = current_buffer

#################### Start  ######################################
p = psutil.Process()

#prediction variables and arrays
coef = [4.69194853322540, 0.00549101525945197, 0.238259303026391, 37.9994048503240, -38.1665306305368, 0.0130922149127113, -0.0223583917166204, -0.287667885571649, 0.148723719998266]
observed=[]
prediction_results=[]
actual_load_results=[]

predicted_load=0 # 0=>short   1=>long

lookahead_limit = 3
lookahead_counter = 0
loaded = 0
currently_loaded = 0
prediction = 0

def _prediction(avg_inter_arrival, process_time_avg, utilization, sent_pkts_interval, recv_pkts_interval, used_buffer, used_memory, flow_count, total_flows):
  global coef
  global observed
  global predicted_load
  global lookahead_limit
  global lookahead_counter
  global loaded #long term load
  global prediction_results
  global actual_load_results
  global currently_loaded
  global prediction 

  print "entered prediction ", lookahead_counter ,"  ", lookahead_limit, " \n\n"
  print "avg inter arrival time || avg Processing Time ||  CPU Load ||  sent bytes || recv bytes || used RAM || used buffers || flows || total Flows until now"
  print  avg_inter_arrival ,"\t", process_time_avg ,"\t", utilization , "\t", sent_pkts_interval ,"\t", recv_pkts_interval , "\t" ,used_buffer,"\t",used_memory,"\t", flow_count , "\t" , total_flows

  if (avg_inter_arrival > 0): #or utilization > 0 ??
    if (lookahead_counter == 1):
#      print "counter = ZERO ++++++++++++++++ \n"
      #store the observed stats. in the observed array with normalization
      observed.append((avg_inter_arrival-0.00394508655019419)/0.00947017182901597)
      observed.append((process_time_avg-0.000430127279150158)/0.000187333951489667)
      observed.append((utilization-24.7581469648553)/20.7967100481943) 
      observed.append((sent_pkts_interval-5209.09531416382)/34480.2081489917)
      observed.append((recv_pkts_interval-5260.31842385498)/34918.8221135128)
      observed.append((used_buffer-1873.51650692219)/4051.11941362582)
      observed.append((used_memory-1338072.46858355)/3456214.83717252)
      observed.append((flow_count-788.938764643209)/981.294321018642)
      observed.append((total_flows-633386.986155463)/360758.177926818)

      #get the dot product of the observed stats. and the coef list
      dot = sum([observed[n]*coef[n] for n in range(len(coef))])

      #compute the prediction formula: dot + p
      #% Compute decision function
      #output = ((X * Beta) / Scale) + Bias
      prediction = (dot/0.178438514776333) + 10.630066567283565
      #print "\n\n=====================\nresult of prediction equation = ",prediction,"\n=====================\n"
      #check if the predicted load is short or long

      if (prediction < 0):
        loaded = 1 # negative => long
      else:
        loaded = 0 # positive => short

      #we've reached the lookahead interval, so now we verify the prediction
    if (lookahead_counter == lookahead_limit):
 #     print "counter == LIMIT ^^^^^^^^^^^ \n"
      observed = []
      if (utilization >= 50):
        currently_loaded = 1
      else:
        currently_loaded = 0
      prediction_results.append(loaded)#binary array that represents the predicted load
      actual_load_results.append(currently_loaded)#binary array that represents the actual load
      prediction_sum = sum([prediction_results[n] for n in range(len(prediction_results))])#sum up the predicted load so far
      actual_sum = sum([actual_load_results[n] for n in range(len(actual_load_results))])#sum up the actual load so far 
      lookahead_counter = 0
      print "\n\n=====================\nresult of prediction equation = ",prediction,"\n=====================\n"
      print "\n\n=====================\npredicted sum = " , prediction_sum ,"  actual sum = ", actual_sum,"\n=====================\n" #print both the sum of the predicted load and the actual load to compare 

    if (lookahead_counter < lookahead_limit):
      lookahead_counter = lookahead_counter + 1

  #    print "counter < limit -------------------\n\n"

def _timer_func ():
    # write those information in a file
    # for connection in core.openflow._connections.values():
        #connection.send(of.ofp_stats_request(body=of.ofp_flow_stats_request()))
    # log.info("Sent %i flow stats request(s)", len(core.openflow._connections))
    global avg_inter_arrival
    global inter_arrival_time
    global inter_arrival_sum
    global process_time
    global process_time_sum
    global old_sent_pkts
    global old_recv_pkts
    global sent_pkts_interval
    global recv_pkts_interval
    global process_time_avg
    global flow_count   
    global total_flows
    global used_memory
    global used_buffer
    global current_RAM
    global old_RAM
    global current_buffer
    global old_buffer

    #CPU load    

    utilization = p.cpu_percent(interval=None)
 
    #accumilative memory stats 

    mem =  psutil.virtual_memory().buffers
    net_recv = psutil.net_io_counters().packets_recv
    net_sent = psutil.net_io_counters().packets_sent


    #sent and recieved packets within time interval 

    current_recv_pkts = psutil.net_io_counters().packets_recv
    current_sent_pkts = psutil.net_io_counters().packets_sent
 
    #to avoid the negative readings
    if (current_sent_pkts >= old_sent_pkts):
      sent_pkts_interval = current_sent_pkts - old_sent_pkts
    else:
      sent_pkts_interval = old_sent_pkts - current_sent_pkts

    if (current_recv_pkts >= old_recv_pkts): 
      recv_pkts_interval = current_recv_pkts - old_recv_pkts
    else:
      recv_pkts_interval = old_recv_pkts - current_recv_pkts


    #amount of used RAM within interval

    current_RAM = psutil.virtual_memory().used
    
    if (current_RAM >= old_RAM):
      used_memory = current_RAM - old_RAM
    else:
      used_memory = old_RAM - current_RAM

    #amount of used buffers

    current_buffer = psutil.virtual_memory().buffers

    if (current_buffer >= old_buffer):
      used_buffer = current_buffer - old_buffer
    else:
      used_buffer = old_buffer - current_buffer

   #get average inter-arrival time of all of the flows within the interval

    if (flow_count == 0):
      avg_inter_arrival = 0.0
      process_time_avg = 0.0
    else:
      avg_inter_arrival = inter_arrival_sum  /(flow_count * 1.0)
      process_time_avg = process_time_sum/(flow_count * 1.0)

    f = open('out/statistics.out', 'a')
    # "avg inter arrival time || avg Processing Time ||  CPU Load ||  sent bytes || recv bytes || used RAM || used buffers || flows || total Flows until now"
    f.write(str(avg_inter_arrival))
    f.write(",")
    f.write(str(process_time_avg))
    f.write(",")
    f.write(str(utilization))
    f.write(",")
    f.write(str(sent_pkts_interval))
    f.write(",")
    f.write(str(recv_pkts_interval))
    f.write(",")
    f.write(str(used_buffer))
    f.write(",")
    f.write(str(used_memory))
    f.write(",")
    f.write(str(flow_count))
    f.write(",")
    f.write(str(total_flows))
    f.write("\n")

    #print "avg inter arrival time || avg Processing Time ||  CPU Load ||  sent bytes || recv bytes || used RAM || used buffers || flows || total Flows until now"

    #print  avg_inter_arrival ,"\t", process_time_avg ,"\t", utilization , "\t", sent_pkts_interval ,"\t", recv_pkts_interval , "\t" ,used_buffer,"\t",used_memory,"\t", flow_count , "\t" , total_flows

    thread = threading.Thread(target= _prediction, args = (avg_inter_arrival, process_time_avg, utilization, sent_pkts_interval, recv_pkts_interval, used_buffer, used_memory, flow_count, total_flows,))

    thread.start()


    #re-intialize for the next interval calculations 

    flow_count = 0
    process_time_avg = 0.0

    sent_pkts_interval = 0
    recv_pkts_interval = 0

    old_sent_pkts = current_sent_pkts
    old_recv_pkts = current_recv_pkts

    old_buffer = current_buffer

    old_RAM = current_RAM

    inter_arrival_sum = 0.0

    process_time_sum = 0.0


def Collect ():
    Timer(1, _timer_func, recurring=True)



# We don't want to flood immediately when a switch connects.
# Can be overriden on commandline.
_flood_delay = 0

class LearningSwitch (object):
  """
  The learning switch "brain" associated with a single OpenFlow switch.

  When we see a packet, we'd like to output it on a port which will
  eventually lead to the destination.  To accomplish this, we build a
  table that maps addresses to ports.

  We populate the table by observing traffic.  When we see a packet
  from some source coming from some port, we know that source is out
  that port.

  When we want to forward traffic, we look up the desintation in our
  table.  If we don't know the port, we simply send the message out
  all ports except the one it came in on.  (In the presence of loops,
  this is bad!).

  In short, our algorithm looks like this:

  For each packet from the switch:
  1) Use source address and switch port to update address/port table
  2) Is transparent = False and either Ethertype is LLDP or the packet's
     destination address is a Bridge Filtered address?
     Yes:
        2a) Drop packet -- don't forward link-local traffic (LLDP, 802.1x)
            DONE
  3) Is destination multicast?
     Yes:
        3a) Flood the packet
            DONE
  4) Port for destination address in our address/port table?
     No:
        4a) Flood the packet
            DONE
  5) Is output port the same as input port?
     Yes:
        5a) Drop packet and similar ones for a while
  6) Install flow table entry in the switch so that this
     flow goes out the appopriate port
     6a) Send the packet out appropriate port
  """
  def __init__ (self, connection, transparent):
    # Switch we'll be adding L2 learning switch capabilities to
    self.connection = connection
    self.transparent = transparent

    # Our table
    self.macToPort = {}

    # We want to hear PacketIn messages, so we listen
    # to the connection
    connection.addListeners(self)

    # We just use this to know when to log a helpful message
    self.hold_down_expired = _flood_delay == 0

    #log.debug("Initializing LearningSwitch, transparent=%s",
    #          str(self.transparent))

  def _handle_PacketIn (self, event):
    """
    Handle packet in messages from the switch to implement above algorithm.
    """
    global inter_arrival_sum
    global flow_count
    global old_arrival
    global avg_inter_arrival_time
    global inter_arrival_time
    global avg_inter_arrival
    global process_time_sum
    global process_time_avg
    global total_flows

    #start timing the controller processing 

    controller_start = time.time()

    #count the incoming flows within an interval. it will get re-initialized every interval
  
    flow_count= flow_count + 1

    #keep track of the total number of flows

    total_flows = total_flows + 1

    #get the flow arrival time

    current_arrival = time.time()

    #calculate the inter-arrival time

    inter_arrival_time = current_arrival - old_arrival

    #get the average 

    inter_arrival_sum = inter_arrival_sum + inter_arrival_time


    old_arrival = current_arrival


    packet = event.parsed

    def flood (message = None):
      """ Floods the packet """
      msg = of.ofp_packet_out()
      if time.time() - self.connection.connect_time >= _flood_delay:
        # Only flood if we've been connected for a little while...

        if self.hold_down_expired is False:
          # Oh yes it is!
          self.hold_down_expired = True
          log.info("%s: Flood hold-down expired -- flooding",
              dpid_to_str(event.dpid))

        if message is not None: log.debug(message)
        #log.debug("%i: flood %s -> %s", event.dpid,packet.src,packet.dst)
        # OFPP_FLOOD is optional; on some switches you may need to change
        # this to OFPP_ALL.
        msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
      else:
        pass
        #log.info("Holding down flood for %s", dpid_to_str(event.dpid))
      msg.data = event.ofp
      msg.in_port = event.port
      self.connection.send(msg)

    def drop (duration = None):
      """
      Drops this packet and optionally installs a flow to continue
      dropping similar ones for a while
      """
      if duration is not None:
        if not isinstance(duration, tuple):
          duration = (duration,duration)
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet)
        msg.idle_timeout = duration[0]
        msg.hard_timeout = duration[1]
        msg.buffer_id = event.ofp.buffer_id
        self.connection.send(msg)
      elif event.ofp.buffer_id is not None:
        msg = of.ofp_packet_out()
        msg.buffer_id = event.ofp.buffer_id
        msg.in_port = event.port
        self.connection.send(msg)

    self.macToPort[packet.src] = event.port # 1

    if not self.transparent: # 2
      if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered():
        drop() # 2a
        return

    if packet.dst.is_multicast:
      flood() # 3a
    else:
      if packet.dst not in self.macToPort: # 4
        flood("Port for %s unknown -- flooding" % (packet.dst,)) # 4a
      else:
        port = self.macToPort[packet.dst]
        if port == event.port: # 5
          # 5a
          log.warning("Same port for packet from %s -> %s on %s.%s.  Drop."
              % (packet.src, packet.dst, dpid_to_str(event.dpid), port))
          drop(10)
          return
        # 6
        log.debug("installing flow for %s.%i -> %s.%i" %
                  (packet.src, event.port, packet.dst, port))
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet, event.port)
        msg.idle_timeout = 1
        msg.hard_timeout = 1
        msg.actions.append(of.ofp_action_output(port = port))
        msg.data = event.ofp # 6a
        self.connection.send(msg)


    # stop timing the controller processing time 

    controller_end = time.time()

    process_time = controller_end - controller_start
 
    process_time_sum = process_time_sum + process_time
   


class l2_learning (object):
  """
  Waits for OpenFlow switches to connect and makes them learning switches.
  """
  def __init__ (self, transparent):
    core.openflow.addListeners(self)
    self.transparent = transparent

  def _handle_ConnectionUp (self, event):
    log.debug("Connection %s" % (event.connection,))
    LearningSwitch(event.connection, self.transparent)


def launch (transparent=False, hold_down=_flood_delay):
  """
  Starts an L2 learning switch.
  """
  try:
    global _flood_delay
    _flood_delay = int(str(hold_down), 10)
    assert _flood_delay >= 0
  except:
    raise RuntimeError("Expected hold-down to be a number")

  core.registerNew(l2_learning, str_to_bool(transparent))
 #################### Start  ######################################
  #core.openflow.addListenerByName("FlowStatsReceived", _handle_flowstats_received)
  thread = threading.Thread(target=Collect, args = ())
  thread.start()
  #################### End  ######################################
