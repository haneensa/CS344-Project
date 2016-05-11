# Install matplotlib
1. sudo apt-get install python-pip
2. sudo pip install matplotlib

# Install psutil
1. $ pip install psutil

# Run the simulation
1. Move controller_stat.py and controller_pro.py and prediction.py to ~/pox/pox/forwarding/
$ mv controller_stat.py controller_pro.py prediction.py ~/pox/pox/forwarding/
2. Change the IP address of the controller in the simulation.py file 
2. Open two VMs and run the following on one machine: 
$ sh run.sh
3. Run controller in another machine:
$ sh controller.sh

# Data Output
The output will be stored in a file with the name "out"
