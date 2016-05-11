# Copyright 2012 James McCauley
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Original l2_nx.py controller desciption:
A quick-and-dirty learning switch for Open vSwitch

This learning switch requires Nicira extensions as found in Open vSwitch.
Run with something like:
./pox.py openflow.nicira --convert-packet-in forwarding.l2_nx

This forwards based on ethernet source and destination addresses.  Where
l2_pairs installs rules for each pair of source and destination address,
this component uses two tables on the switch -- one for source addresses
and one for destination addresses.  Specifically, we use tables 0 and 1
on the switch to implement the following logic:
0. Is this source address known?
NO: Send to controller (so we can learn it)
1. Is this destination address known?
YES:  Forward out correct port
NO: Flood

Note that unlike the other learning switches *we keep no state in the
controller*.  In truth, we could implement this whole thing using OVS's
learn action, but doing it something like is done here will still allow
us to implement access control or something at the controller.
"""

from pox.core import core
from pox.lib.addresses import EthAddr
import pox.openflow.libopenflow_01 as of
import pox.openflow.nicira as nx
from pox.lib.revent import EventRemove
from pox.lib.recoco import Timer
from datetime import datetime
from pox.openflow.of_json import *
import threading
import psutil
import time

# Even a simple usage of the logger is much nicer than print!
log = core.getLogger()

########  some global variables ##########
# flow counting within interval
flow_count = 0
# total flows through duration
total_flows = 0
# CPU load through duration
load_sum = 0.0
utilization = 0.0
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
used_memory = 0
current_RAM = psutil.virtual_memory().used
old_RAM = current_RAM

# used buffer within interval
used_buffer = 0
current_buffer = psutil.virtual_memory().buffers
old_buffer = current_buffer

p = psutil.Process()

# prediction variables and arrays
# Learned prediction equation coefficients 
coef = [-0.0406863425229071, -0.0295177453561016, 0.254104692696994, 0.346778640858201, -0.773910646023645, 0.00385001315181577, -0.0667897034572235, -0.133757351111104, 0.0348236228672685]
# Store the observed statistics to perform the prediction on them 
observed = []
# Store the binary traffic prediciton results
prediction_results = []
# strore the actual traffic observation
actual_load_results = []
# lookahead interval length
lookahead_limit = 5
# track the lookahead interval
lookahead_counter = 0
# binary classification results
loaded = 0
# binary actual classification
currently_loaded = 1
# results of the prediction equation
prediction = 0
# variables to keep track of long term in two consecutive predictions
actual_observe = 0
actual_list = []
num_observation = 0
# counts the correct prediction
hits = 0
load_thresh = 80
lower_bound_thresh = 50

def _prediction(avg_inter_arrival, process_time_avg, utilization, sent_pkts_interval, recv_pkts_interval, used_buffer, used_memory, flow_count, total_flows):
  global coef
  global observed
  global lookahead_limit
  global lookahead_counter
  global loaded #long term load
  global prediction_results
  global actual_load_results
  global currently_loaded
  global prediction 
  global actual_observe
  global actual_list
  global num_observation
  global hits

  print "entered prediction ", lookahead_counter ,"  ", lookahead_limit, " \n\n"
  print "avg inter arrival time || avg Processing Time ||  CPU Load ||  sent bytes || recv bytes || used RAM || used buffers || flows || total Flows until now"
  print  avg_inter_arrival ,"\t", process_time_avg ,"\t", utilization , "\t", sent_pkts_interval ,"\t", recv_pkts_interval , "\t" ,used_buffer,"\t",used_memory,"\t", flow_count , "\t" , total_flows

  if (avg_inter_arrival > 0): #or utilization > 0 ??    
    if (lookahead_counter == 1):
      #store the observed stats. in the observed array with normalization
      observed.append((avg_inter_arrival-0.00465599570184450)/0.0101999316634820)
      observed.append((process_time_avg-0.000465111678301057)/0.000307722378725298)
      observed.append((utilization-53.8151736745874)/43.4530368313086) 
      observed.append((sent_pkts_interval-503.461913467387)/262.960787058142)
      observed.append((recv_pkts_interval-780.064594759274)/675.075548235130)
      observed.append((used_buffer-1592.47288238874)/3242.83460024379)
      observed.append((used_memory-208459.193174886)/388489.766926055)
      observed.append((flow_count-1067.70932358316)/1059.85299611904)
      observed.append((total_flows-574039.529555135)/346067.572402766)
      num_observation = num_observation + 1

      #get the dot product of the observed stats. and the coef list
      dot = sum([observed[n]*coef[n] for n in range(len(coef))])
      #compute the prediction formula: dot + p
      prediction = (dot/0.1224) - 1.9274
      #check if the predicted load is short or long
      if (prediction < 0):
        loaded = 0 # negative => short
      else:
        loaded = 1 # positive => long

    #we've reached the lookahead interval, so now we verify the prediction
    if (lookahead_counter == lookahead_limit):
      observed = []
      if (currently_loaded != 0):
        if (utilization >= load_thresh):
          currently_loaded = 1

      if (loaded == 0 and utilization < lower_bound_thresh):
          actual_list = []
    
      # binary array that represents the predicted load
      prediction_results.append(loaded)
      # binary array that represents the actual load
      actual_load_results.append(currently_loaded)
      actual_list.append(currently_loaded)
      #sum up the actual load so far 
      actual_observe = sum([actual_list[n] for n in range(len(actual_list))])
      lookahead_counter = 0
      currently_loaded = 1 #re-initialize

      print "\n\n=====================\nresult of prediction equation = ", prediction,"\n=====================\n"
      # print both the sum of the predicted load and the actual load to compare 
      print "\n\n=====================\nprediction = " , loaded ,"  actual_observe = ", actual_observe,"\n=====================\n" #print both the sum of the predicted load and the actual load to compare 
      
      if (loaded == 0 and actual_observe < 2):     #not loaded
          hits = hits + 1
      elif (loaded == 1 and actual_observe >= 1):    #loaded
          hits = hits + 1

      # print both the sum of the predicted load and the actual load to compare 
      print "\n\n=====================\n predition = " , hits ,"  observation = ", num_observation,"\n=====================\n"
      
    if (lookahead_counter < lookahead_limit):
      #if during the lookahead interval we find a drop in the load then it's not long term and not loaded
      if (utilization < load_thresh):
        currently_loaded = 0
      lookahead_counter = lookahead_counter + 1


def _timer_func ():
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
    global load_sum
    global utilization
    global coef
    global observed
    global predicted_load
    global lookahead_limit
    global lookahead_counter
    global loaded #long term load
    global prediction_results
    global actual_load_results

    utilization = p.cpu_percent(interval=None)
    # accumilative memory stats
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
    
    # amount of used RAM within interval
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
    #get averge CPU load
    
    if (flow_count == 0): 
        avg_inter_arrival = 0.0
        process_time_avg = 0.0
    
    else:
        avg_inter_arrival = inter_arrival_sum  /(flow_count * 1.0)
        process_time_avg = process_time_sum/(flow_count * 1.0)
    
    thread = threading.Thread(target= _prediction, args = (avg_inter_arrival, process_time_avg, utilization, sent_pkts_interval, recv_pkts_interval, used_buffer, used_memory, flow_count, total_flows,))
    thread.start()
   
    f = open('out/statistics.out', 'a')
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

def _handle_PacketIn (event):
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
 
    # reactive flow installation in table 0
    msg = nx.nx_flow_mod()
    if (actual_observe < 2):
        msg.match.of_eth_src = packet.dst
        msg.match.of_eth_dst = packet.src
        msg.idle_timeout = 4
        msg.flags = of.OFPFF_SEND_FLOW_REM
        msg.actions.append(of.ofp_action_output(port = event.port))
        core.openflow.sendToDPID(event.dpid, msg)
        
        #install entries in backup table (table 1) with long enough TTL
        msg = nx.nx_flow_mod()
        msg.match.of_eth_src = packet.dst
        msg.match.of_eth_dst = packet.src
        msg.table_id = 1
        msg.flags = of.OFPFF_SEND_FLOW_REM
        msg.actions.append(of.ofp_action_output(port = event.port))
        core.openflow.sendToDPID(event.dpid, msg)
    
    # if controller is loaded then resubmit from table 0 to table 1 (backup table)
    # Now flows will use table 1 only without communicating with the controller
    # to communicate with the controller again, we need to let the flows expire from table 1 after some time 
    # (decided based on how long time the CPU load needs to cool down)
    else:
        msg.actions.append(nx.nx_action_resubmit.resubmit_table(table = 1))
        core.openflow.sendToDPID(event.dpid, msg)
    
    # stop timing the controller processing time
    controller_end = time.time()
    process_time = controller_end - controller_start
    process_time_sum = process_time_sum + process_time

def _handle_ConnectionUp (event):
    # Set up this switch.
    # After setting up, we send a barrier and wait for the response
    # before starting to listen to packet_ins for this switch -- before
    # the switch is set up, the packet_ins may not be what we expect,
    # and our responses may not work!
    
    # Turn on Nicira packet_ins
    msg = nx.nx_packet_in_format()
    event.connection.send(msg)
    
    # Turn on ability to specify table in flow_mods
    msg = nx.nx_flow_mod_table_id()
    event.connection.send(msg)
    
    # Clear second table
    msg = nx.nx_flow_mod(command=of.OFPFC_DELETE, table_id = 1)
    event.connection.send(msg)
    
    # Fallthrough rule for table 0: flood and send to controller
    msg = nx.nx_flow_mod()
    msg.priority = 1 # Low priority
    
    
    msg.actions.append(of.ofp_action_output(port = of.OFPP_CONTROLLER))
    msg.actions.append(nx.nx_action_resubmit.resubmit_table(table = 1))
    event.connection.send(msg)
    
    # Fallthrough rule for table 1: flood
    msg = nx.nx_flow_mod()
    msg.table_id = 1
    msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
    event.connection.send(msg)
    
    def ready (event):
        if event.ofp.xid != 0x80000000:
            # Not the right barrier
            return
        log.info("%s ready", event.connection)
        event.connection.addListenerByName("PacketIn", _handle_PacketIn)
        return EventRemove
    
    event.connection.send(of.ofp_barrier_request(xid=0x80000000))
    event.connection.addListenerByName("BarrierIn", ready)


def launch ():
    assert core.NX, "Nicira extensions required"
    assert core.NX.convert_packet_in, "PacketIn conversion required"
    
    core.openflow.addListenerByName("ConnectionUp", _handle_ConnectionUp)
    thread = threading.Thread(target=Collect, args = ())
    thread.start()
    log.info("Simple NX switch running.")

