import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import argparse
import os
import sys
import json
from collections import OrderedDict


#####################################
# - Parsing
#####################################

# Data from the stat file is saved to dictionary
def parse_wrk_data(lines):
  return_dict = {}
  # Flag to indicate reading now custom output
  # All other info like DURATION, STATERR etc are also gathered
  # regardless "LATENCY" keyword should be used in beginning, or could change it in wrk script
  custom_read = False

  for line in lines:
    if (not custom_read):
      if (not line.startswith("LATENCY")):
        continue
      else:
        custom_read = True
    split = line.rstrip().split(',')

    if (len(split) > 1):
      return_dict[split[0]] = float(split[1])

  return return_dict

# CPU data from "top"
def parse_cpu_data(lines):
  return_dict = {}
  # List for each stat for CPU, such as usage percentage of user, kernel, interrupt etc.
  return_dict["CPU"] = [[] for i in range(7)]
  for line in lines:
    split = line.replace(',', '.').split(' ')
    if len(split) < 2: # Empty or malformed line
      continue
    items = [float(x) for x in split]

    for i, perc in enumerate(items):
      return_dict["CPU"][i].append(perc)

  # Calculate means of CPU stats
  return_dict["CPU-MEANS"] = []
  for cpu_statlist in return_dict["CPU"]:
    return_dict["CPU-MEANS"].append(sum(cpu_statlist) / len(cpu_statlist))

  return return_dict

# NPtcp output
def parse_netpipe_data(lines, graph_args):
  return_dict = {"NP-BYTES": [], "NP-THROUGHPUT": [], "NP-LATENCY": []}
  for line in lines:
    split = line.rstrip().split()
    return_dict["NP-BYTES"].append(int(split[0]))
    # Mbps
    tp = float(split[1])
    if "gbps" in graph_args:
      tp /= 1000
    return_dict["NP-THROUGHPUT"].append(tp)
    # Seconds converted to Milliseconds
    lat = float(split[2]) * 1000
    if "us" in graph_args:
      lat *= 1000
    return_dict["NP-LATENCY"].append(lat)
  return return_dict

# Infiniband perftest output
def parse_ib_perftest_data(lines, graph_args):
  return_dict = {"IB-BYTES": [], "MIN": [], "MAX": [], "TYPICAL": [], "MEAN": [], "STDEV": [], "99%": [], "99.9%": [], "BW-PEAK": [], "BW-AVG": [], "BW-MPPS": []}
  readflag = False
  for line in lines:
    if "#bytes" in line: # Keyword for where the data starts
      readflag = True
      continue
    elif readflag:
      split = line.rstrip().split()
      # We don't need more bytes than 1M test, stop at most 2M
      # Also skip empty lines or lines with dashes
      if split[0] == "" or "-" in split[0] or int(split[0]) > 2000000:
        continue
      if "latency" in graph_args:
        # TODO check latency or bandwidth mode here. Append to the arrays accordingly, create all dem arrays anyway at the top there.
        # For latency e.g. ib_send_lat:
        # #bytes #iterations    t_min[usec]    t_max[usec]  t_typical[usec]    t_avg[usec]    t_stdev[usec]   99% percentile[usec]   99.9% percentile[usec]
        ms_modifier = 1
        if "us" not in graph_args:
          ms_modifier = 1000
        return_dict["IB-BYTES"].append(int(split[0]))
        return_dict["MIN"].append(float(split[2]) / ms_modifier)
        return_dict["MAX"].append(float(split[3]) / ms_modifier)
        return_dict["TYPICAL"].append(float(split[4]) / ms_modifier)
        return_dict["MEAN"].append(float(split[5]) / ms_modifier)
        return_dict["STDEV"].append(float(split[6]) / ms_modifier)
        return_dict["99%"].append(float(split[7]) / ms_modifier)
        return_dict["99.9%"].append(float(split[8]) / ms_modifier)
      elif "throughput" in graph_args:
        # Bandwidth e.g. ib_send_bw -a
        # #bytes     #iterations    BW peak[MB/sec]    BW average[MB/sec]   MsgRate[Mpps]
        return_dict["IB-BYTES"].append(int(split[0]))
        gbps_modifier = 1
        if "gbps" in graph_args:
          gbps_modifier = 1000
        # Convert to bits per s
        return_dict["BW-PEAK"].append(float(split[2]) * 8 / gbps_modifier)
        return_dict["BW-AVG"].append(float(split[3]) * 8 / gbps_modifier)
        return_dict["BW-MPPS"].append(float(split[4]))
      else:
        print("ERROR: No argument 'latency' or 'throughput' specified for IB perftest parsing")
        exit(1)
  return return_dict

# Sockperf output parsing, tailored for it
def parse_sockperf_data(lines, graph_args):
  return_dict = {}
  phase = 0 # Read the file in phases, ignoring keywords before their time comes
  for line in lines:
    if "latency" in graph_args:
      if "avg-latency" in line and phase==0:
        split = line.rstrip().split()
        return_dict["MEAN"] = float(split[2].split('=')[1])
        return_dict["STDEV"] = float(split[3].split('=')[1].split(')')[0])
        phase += 1
      elif "MAX" in line and phase == 1:
        return_dict["MAX"] = float(line.split('=')[1].lstrip().rstrip())
        phase += 1
      elif phase > 1:
        if "percentile" in line:
          percentile = line.split()[3]
          percentile = percentile.rstrip('0')
          if percentile.endswith('.'):
            percentile = percentile.rstrip('.')
          return_dict[percentile+"%"] = float(line.split('=')[1].strip())
        elif "MIN" in line:
          return_dict["MIN"] = float(line.split('=')[1].strip())
          phase = -1
    elif "throughput" in graph_args:
      if "Summary:" in line and phase==0:
        return_dict["MSGRATE"] = int(line.split("[msg/sec]")[0].split()[-1].strip())
        phase += 1
      elif phase > 0:
        return_dict["THROUGHPUT"] = float(line.split()[-2].strip('('))
    else:
      print("ERROR: No argument 'latency' or 'throughput' specified for sockperf parsing")
      exit(1)
  return return_dict

# parse wrk and CPU files in their data functions
def parse_files(graph_options, stats_dict):
  filedir = ""
  # Can specify another directory relative to current one for stat files
  if graph_options["FILEDIR"] is not None:
    filedir = graph_options["FILEDIR"] + "/"

  for row in graph_options["SUBPLOTS"]:
    for graphopt in row:
      # Each graph gets its own ordered dict
      graphopt["STATS"] = OrderedDict()
      # If another directory specified. This directory is then used for all future files until specified again
      if "FILEDIR" in graphopt:
        filedir = graphopt["FILEDIR"] + "/"
      for f in graphopt["STATFILES"]:#list(files):
        with open("./" + filedir + f, "r") as statfile:
          # Now parse the files based on the keyword in their file name
          # Stat dictionary key is the file name
          if "iperf" in f: # graphopt["ARGS"]:
            # Put everything in iperf JSON to dict
            graphopt["STATS"][f] = json.load(statfile)
          else:
            lines = statfile.readlines() # Interferes with "json.load(statfile)" so done here
            if "netpipe" in f:
              graphopt["STATS"][f] = parse_netpipe_data(lines, graphopt["ARGS"])
            elif "sockperf" in f:
              graphopt["STATS"][f] = parse_sockperf_data(lines, graphopt["ARGS"])
            elif "ib" in graphopt["ARGS"]:
              graphopt["STATS"][f] = parse_ib_perftest_data(lines, graphopt["ARGS"])
              # Use the array of bytes transferred as x-axis
              if not "XAXIS" in graphopt:
                print("Using bytes transferred from IB test as XAXIS, assuming same values for all")
                graphopt["XAXIS"] = graphopt["STATS"][f]["IB-BYTES"]
            else: # Default: wrk benchmark data
              graphopt["STATS"][f] = parse_wrk_data(lines)

      # Find CPU stat files based on the actual statfiles if not given (if no CPUFILES given but ARG cpu is)
      # The CPU file name has to be same as the stat file with "-CPU" (and "-client" for example)
      if len(graphopt["CPUFILES"]) == 0 and "cpu" in graphopt["ARGS"]:
        print("Finding matching CPU stat files")
        files = os.listdir("./" + filedir)
        for statfile in graphopt["STATFILES"]:
          for f in files:
            if f.startswith(statfile) and statfile+"-CPU" in f and not ".png" in f:
              print("Found CPU file", f)
              graphopt["CPUFILES"].append(f)

      for f in graphopt["CPUFILES"]:
        with open("./" + filedir + f, "r") as statfile:
          lines = statfile.readlines()
          graphopt["STATS"][f] = parse_cpu_data(lines)

  return 0


# Read the mandatory options file
def parse_graph_options(file):
  # Dictionary stores all options
  return_dict = {}
  return_dict["TITLE"] = ""
  # Different subplots are stored in this array of arrays, the inside arrays containing columns and outer the rows
  # Argument COLUMNS to determine the width of SUBPLOTS:
  # The graph options are then parsed in the order left to right, top to bottom subplots, basic reading system
  # Keyword SUBPLOT separates the plots. When this keyword comes, we move to the next column, appending to the inner array.
  # unless if we are at last column,
  # in which case we move to the next row. Creating (appending) another array in outer SUBPLOTS array.
  return_dict["SUBPLOTS"] = [[{}]]
  # each of the SUBPLOTS array elements contain a dictionary for a graph!
  columns = 1 # This is changed only once when the keyword COLUMNS comes. and checked only when the keyword: SUBPLOT comes.
  cur_col = 0 # This is changed back to 1 when we have parsed ==columns when keyword SUBPLOT comes.
  cur_row = 0 # We need this for indexing

  return_dict["SUBPLOTS"][0][0]["STATFILES"] = []
  return_dict["SUBPLOTS"][0][0]["CPUFILES"] = []
  return_dict["SUBPLOTS"][0][0]["ARGS"] = []
  # Global FILEDIR option - the SUBPLOTS can also contain FILEDIR options, to change the directory for a plot's files. The newest FILEDIR is used for all files until another FILEDIR
  return_dict["FILEDIR"] = None # If stat files in different directory
  return_dict["SHAREY"] = False # If we want same scale y axis on all graphs

  read_filenames = False
  read_cpu_filenames = False
  with open("./" + file, "r") as statfile:
    lines = statfile.readlines()
    for line in lines:
      if not read_filenames and not read_cpu_filenames:
        # Split first word
        split = line.split(' ', 1)
        # Read statfile names last. Can start with either of these
        if split[0].startswith("FILES"):
          read_filenames = True
          continue
        elif split[0].startswith("CPUFILES"):
          read_cpu_filenames = True
          continue
        # Share same y axis scale
        elif split[0].startswith("SHAREY"):
          return_dict["SHAREY"] = True
        # Program arguments in file, that specify additional information
        elif split[0] == "ARG":
          # Percentiles to get, possibilities 50, 90, 99, 99.999
          if split[1].startswith("percentile"):
            return_dict["SUBPLOTS"][cur_row][cur_col]["ARGS"].append("percentiles")
            return_dict["SUBPLOTS"][cur_row][cur_col]["PERCENTILES"] = split[1].rstrip().split(' ')[1:]
          # CPU info arguments
          elif split[1].startswith("cpu"):
            return_dict["SUBPLOTS"][cur_row][cur_col]["ARGS"].append("cpu")
            if split[1].startswith("cpu-mean"):
              return_dict["SUBPLOTS"][cur_row][cur_col]["ARGS"].append("cpu-mean")
            # If there are metric specification arguments
            if len(split[1].split(' ')) > 1:
              return_dict["SUBPLOTS"][cur_row][cur_col]["CPU-METRICS"] = split[1].rstrip().split(' ')[1:]
          # Optional title for the subplot
          elif split[1].startswith("title"):
            return_dict["SUBPLOTS"][cur_row][cur_col]["AXTITLE"] = split[1].rstrip().split('title')[1].lstrip()
          # If some other single argument defined using ARG
          else:
            return_dict["SUBPLOTS"][cur_row][cur_col]["ARGS"].append(split[1].rstrip())
        # Any additional arguments that only need a single word
        elif split[0] == "ARGS":
          return_dict["SUBPLOTS"][cur_row][cur_col]["ARGS"].extend(split[1].rstrip().split(' '))
        # Graph information and file name, possible stat file directory
        elif split[0] in ["TITLE", "TITLE2", "FILENAME", "FILEDIR"]:
          return_dict[split[0]] = split[1].rstrip()
        # Axes and labels
        elif split[0] in ["AXES", "XAXIS", "LABELS", "COMPARE", "ANNOTATE"]:
          return_dict["SUBPLOTS"][cur_row][cur_col][split[0]] = split[1].rstrip().split(',')
        # The amount of columns if multiple subplots
        elif split[0] == "COLUMNS":
          columns = int(split[1].rstrip())
      else:
        # Switch to another plot with the keyword SUBPLOT, and read stats for that.
        if line.startswith("SUBPLOT"):
          read_cpu_filenames = False
          read_filenames = False
          # Give "XAXIS-N" (numeric indexes for xaxis elements) to each subplot
          if "XAXIS" in return_dict["SUBPLOTS"][cur_row][cur_col]:
            return_dict["SUBPLOTS"][cur_row][cur_col]["XAXIS-N"] = np.arange(len(return_dict["SUBPLOTS"][cur_row][cur_col]["XAXIS"])) # Used to move the possible CPU bars slightly
          if cur_col < columns-1: # New dict for a column element in the same row
            cur_col += 1
            return_dict["SUBPLOTS"][cur_row].append({})
          else: # New row
            cur_col = 0
            cur_row += 1
            return_dict["SUBPLOTS"].append([{}])
          return_dict["SUBPLOTS"][cur_row][cur_col]["STATFILES"] = []
          return_dict["SUBPLOTS"][cur_row][cur_col]["CPUFILES"] = []
          return_dict["SUBPLOTS"][cur_row][cur_col]["ARGS"] = []
        # The keyword FILEDIR can be used again (or instead of global) after the keywords FILES or CPUFILES, to again specify a directory
        # This directory will be used for all files until the keyword is used again
        elif line.startswith("FILEDIR"):
          split = line.split(' ', 1)
          return_dict["SUBPLOTS"][cur_row][cur_col]["FILEDIR"] = split[1].rstrip()
        # Filename read mode last per plot. Switch to another file mode with a keyword
        elif read_filenames:
          if line.rstrip() == "": # Skip empty line
            continue
          if line.startswith("CPUFILES"):
            read_cpu_filenames = True
            read_filenames = False
            continue
          return_dict["SUBPLOTS"][cur_row][cur_col]["STATFILES"].append(line.rstrip())
        elif read_cpu_filenames:
          if line.rstrip() == "": # Skip empty line
            continue
          if line.startswith("FILES"):
            read_cpu_filenames = False
            read_filenames = True
            continue
          return_dict["SUBPLOTS"][cur_row][cur_col]["CPUFILES"].append(line.rstrip())

  # Give XAXIS-N (numeric indexes for xaxis elements) to final subplot
  if "XAXIS" in return_dict["SUBPLOTS"][cur_row][cur_col]:
    return_dict["SUBPLOTS"][cur_row][cur_col]["XAXIS-N"] = np.arange(len(return_dict["SUBPLOTS"][cur_row][cur_col]["XAXIS"])) # Used to move the possible CPU bars slightly
  return return_dict


#####################################
# - Plotting functions
#####################################


def plot_latencies_maxminmean(ax, stats_dict, graph_options):
  labels_arr = [""]
  idx = 0
  max_arr = [[]]
  min_arr = [[]]
  # Mean with standard deviation
  mean_arr = [[]]
  stdev_arr = [[]]
  if "COMPARE" in graph_options:
    labels_arr[0] = graph_options["COMPARE"][0]
    for i in range(len(graph_options["COMPARE"])-1):
      max_arr.append([])
      min_arr.append([])
      mean_arr.append([])
      stdev_arr.append([])
      labels_arr.append(graph_options["COMPARE"][i+1])

  for key, value in stats_dict.items():
    if "CPU" in key: # Don't go through CPU stat files
        continue
    # NEW THING: Compare runs by keywords, determine with e.g. COMPARE wrk-run1,wrk-run2, where wrk-run1 and wrk-run2 can be found in group's file names. Match first
    if "COMPARE" in graph_options:
      for i, c in enumerate(graph_options["COMPARE"]):
        if c in key:
          idx = i
          break
    mean = value["MEAN"]
    stdev = value["STDEV"]
    min = value["MIN"]
    max = value["MAX"]
    # Microseconds specifier check
    if "us" not in graph_options["ARGS"]:
      mean /= 1000
      stdev /= 1000
      max /= 1000
      min /= 1000
    max_arr[idx].append(max)
    min_arr[idx].append(min)
    mean_arr[idx].append(mean)
    stdev_arr[idx].append(stdev)

  for i, l in enumerate(labels_arr):
    if "LABELS" in graph_options and len(graph_options["LABELS"]) == len(labels_arr):
      l = graph_options["LABELS"][i]

    if "max" in graph_options["ARGS"]:
      ax.plot(graph_options["XAXIS"], max_arr[i], label=l+" Max")
    if "min" in graph_options["ARGS"]:
      ax.plot(graph_options["XAXIS"], min_arr[i], label=l+" Min")
    if "mean" in graph_options["ARGS"]:
      if len(labels_arr) == 1:
        ax.errorbar(graph_options["XAXIS"], mean_arr[i], yerr=stdev_arr[i], capsize=6, color="darkslategray", label=l+" Mean")
      else:
        ax.plot(graph_options["XAXIS"], mean_arr[i], label=l+" Mean")

    # Annotation filter
    if "ANNOTATE" not in graph_options or ("ANNOTATE" in graph_options and l in graph_options["ANNOTATE"]):
      if "mean" in graph_options["ARGS"]:
        for j, value in enumerate(mean_arr[i]):
          ax.annotate(round(value, 2), (graph_options["XAXIS"][j], mean_arr[i][j]))
      if "min" in graph_options["ARGS"]:
        for j, value in enumerate(min_arr[i]):
          ax.annotate(round(value, 2), (graph_options["XAXIS"][j], min_arr[i][j]))
      # Annotate max if no 99.999th percentile graph
      if "max" in graph_options["ARGS"] and (not "percentiles" in graph_options["ARGS"] or not "99.999" in graph_options["PERCENTILES"]):
        for j, value in enumerate(max_arr[i]):
          ax.annotate(round(value, 2), (graph_options["XAXIS"][j], max_arr[i][j]))


def plot_percentiles(ax, stats_dict, graph_options):
  labels_arr = [""]
  percentile_dicts = [{}]
  idx = 0
  #for perc in graph_options["PERCENTILES"]: # Wanha: looppas tästä ensin, nyt toisi päi
  #  percentile_dict[perc + "%"] = []
  if "COMPARE" in graph_options:
    labels_arr[0] = graph_options["COMPARE"][0]
    for i in range(len(graph_options["COMPARE"])-1):
      percentile_dicts.append({})
      labels_arr.append(graph_options["COMPARE"][i+1])
  for key, value in stats_dict.items():
    if "CPU" in key: # Don't go through CPU stat files
      continue
    # NEW THING: Compare runs by keywords, determine with e.g. COMPARE wrk-run1,wrk-run2, where wrk-run1 and wrk-run2 can be found in group's file names
    if "COMPARE" in graph_options:
      for i, c in enumerate(graph_options["COMPARE"]):
        if c in key:
          idx = i
          break
    for perc in graph_options["PERCENTILES"]:
      if perc+"%" not in value:
        print("ERROR: percentile", perc+"%", "is not found in data for", key)
        return
      if perc+"%" not in percentile_dicts[idx]:
        percentile_dicts[idx][perc + "%"] = []
      latency_val = value[perc + "%"]
      # Convert to milliseconds
      if "us" not in graph_options["ARGS"]:
        latency_val /= 1000
      percentile_dicts[idx][perc + "%"].append(latency_val)

  for i, l in enumerate(labels_arr):
    if "LABELS" in graph_options and len(graph_options["LABELS"]) == len(labels_arr):
      l = graph_options["LABELS"][i]
    for key, value in percentile_dicts[i].items():
      ax.plot(graph_options["XAXIS"], value, label=l+" "+key)

      # Annotation filter
      if "ANNOTATE" not in graph_options or ("ANNOTATE" in graph_options and l in graph_options["ANNOTATE"]):
        for j, val in enumerate(value):
          ax.annotate(round(val, 2), (graph_options["XAXIS"][j], value[j]))


def plot_throughput(ax, ax2, stats_dict, graph_options):
  #graph_dict = {}
  #graph_dict["Throughput"] = []
  #graph_dict["Requests"] = []
  throughput_arr = [[]]
  #requests_arr = [[]]
  msgrate_arr = [[]] # Messages per second
  labels_arr = [""] # get these from COMPARE
  idx = 0
  print("Msgrate = Mega-messages-per-second!")
  if "COMPARE" in graph_options:
    labels_arr[0] = graph_options["COMPARE"][0]
    for i in range(len(graph_options["COMPARE"])-1):
      throughput_arr.append([])
      msgrate_arr.append([])
      labels_arr.append(graph_options["COMPARE"][i+1])
  for key, value in stats_dict.items():
    # NEW THING: Compare runs by keywords, determine with e.g. COMPARE wrk-run1,wrk-run2, where wrk-run1 and wrk-run2 can be found in group's file names
    if "COMPARE" in graph_options:
      for i, c in enumerate(graph_options["COMPARE"]):
        if c in key:
          idx = i
          break
    if "wrk" in key:
      throughput = value["BYTES"] * 8 / value["DURATION"] # Mb / s (1 / micro = Mega)
      if "gbps" in graph_options["ARGS"]:
        throughput /= 1000
      print(throughput)
      print(value["REQUESTS"], "/", value["DURATION"])
      throughput_arr[idx].append(throughput) # toka / 1000000 Mbps?
      msgrate_arr[idx].append(value["REQUESTS"] / value["DURATION"]) # mega-messages-per-sec
    elif "sockperf" in key:
      throughput = value["THROUGHPUT"]
      if "gbps" in graph_options["ARGS"]:
        throughput /= 1000
      throughput_arr[idx].append(throughput)
      msgrate_arr[idx].append(value["MSGRATE"] / 1000000) # Mega-messages-per-second
    #throughput_arr.append(value["BYTES"])
    #requests_arr.append(value["REQUESTS"])
    # done Mbps. We want (MB/s) value, modify accordingly: BYTES / DURATION / 1000000
    # Achsually we want Mbps / Gbps
    # Delete requests and second axis
  for i, l in enumerate(labels_arr):
    if "LABELS" in graph_options and len(graph_options["LABELS"]) == len(labels_arr):
      l = graph_options["LABELS"][i]
    try:
      ax.plot(graph_options["XAXIS"], throughput_arr[i], label=l+" TP")
      ax2.plot(graph_options["XAXIS"], msgrate_arr[i], linestyle="dashed", label=l+" Msgrate")
    except ValueError:
      print("Value ERROR", i, l, graph_options["XAXIS"], throughput_arr[i], msgrate_arr[i])
      exit(1)

    for j, val in enumerate(throughput_arr[i]):
      ax.annotate(round(val, 2), (graph_options["XAXIS"][j], throughput_arr[i][j]))
  #for i, val in enumerate(requests_arr):
  #  ax2.annotate(val, (graph_options["XAXIS"][i], requests_arr[i]))



def plot_cpu_usage(ax, ax2, stats_dict, graph_options):
  #TODO: if ax2 is not none , use the mean cpu values !
  #index = 0
  # indexes:
  # 0 us=userspace 1 sy=system/kernel (skip ni=niced-user/userdefinedprio)
  # 2 id=idleops 3 wa=waitdisk/peripheral 4 hi=hardwareint 5 si=softwareint
  # 6 st=steal,involuntaryvirtual-cpuwait (hypervisor servicing another processor)

  # float("2,5".replace(',', '.'))

  # TODO eli mean cpu usaget:
  # Joka filulle, käy läpi kaikki labelit ja kokoa ne keskiarvotaulukkoihin.
  # Lopussa, for loopin jälkeen, suorita vasta ax2.plot joka plottaa ne kaikki bar graafeihin. Tän homman voi käydä samassa loopissa, mutta lopuks tarvii tehä toi plot.
  labeled_means = {}
  unpaired_keys = [] # List for matching client and server information for a run
  # TODO unused ^
  labels=["user", "kernel", "idle", "peripheral", "hw-int", "sw-int", "steal"]
  #colors = [red,  purple, green, blue, orange, brown, cyan]
  colors = {"user": "m", "kernel": "y", "idle": "g", "peripheral": "b", "hw": "r", "hw-int": "r", "sw": "c", "sw-int": "c", "steal": "tab:brown"}

  for key, value in stats_dict.items():
    if not "CPU" in key: # TODO softan ohjeisiin että cpu filuissa pitää sisältyä toi keyword
      continue
    run_key = key.split("CPU")[0]
    if run_key not in unpaired_keys: # TODO unused
      unpaired_keys.append(run_key)
    
    for i, lbl in enumerate(labels):
      # Skip labels according to what requested by user
      if "CPU-METRICS" in graph_options:
        if lbl not in graph_options["CPU-METRICS"]:
          continue
      elif lbl == "idle": # Skip idle cpu usage by default
        continue
      # CPU mean bar plot mode
      if ax2 is not None or "cpu-mean" in graph_options["ARGS"]:
        categorized_label = lbl + key.split("CPU")[1] # Add client or server label. TODO except indexerror?
        if categorized_label not in labeled_means:
          labeled_means[categorized_label] = []
        labeled_means[categorized_label].append(value["CPU-MEANS"][i])
        continue

      # Full CPU usage plot if no means wanted
      # 1 second between measurements
      timevalues = list(range(1, len(value["CPU"][0]) + 1))
      #timevalues = [v * 15 for v in timevalues] # 15 seconds
      ax.plot(timevalues, value["CPU"][i], label=lbl)

    #for i, val in enumerate(value["CPU"]):
    #  ax.annotate(val, (timevalues[i], value["CPU"][i]))
    #index += 1

  # Plot means
  if ax2 is None and "cpu-mean" not in graph_options["ARGS"]:
    return
  prev_val = None
  prev_client_val = None
  prev_server_val = None
  for key, value in labeled_means.items():
    #color = colors[labels.index(key.split("-")[0])]
    # Plot mean values to second y axis
    if ax2 is not None:
      width=0.08
      if "client" in key:
        ax2.bar(graph_options["XAXIS-N"]-width/2, value, width, bottom=prev_client_val,
                label=key, color=colors[key.split("-")[0]], alpha=0.5)
        prev_client_val = (value if prev_client_val is None else np.add(prev_client_val, value))
      elif "server" in key:
        ax2.bar(graph_options["XAXIS-N"]+width/2, value, width, bottom=prev_server_val,
                label=key, color=colors[key.split("-")[0]], alpha=0.5)
        prev_server_val = (value if prev_server_val is None else np.add(prev_server_val, value))
      else:
        ax2.bar(graph_options["XAXIS"], value, width, bottom=prev_val,
                label=key, color=colors[key.split("-")[0]], alpha=0.5)
    # Or to the first y axis if cpu-mean arg defined
    elif "cpu-mean" in graph_options["ARGS"]:
      width=0.2
      if "client" in key:
        ax.bar(graph_options["XAXIS-N"]-width/2, value, width, bottom=prev_client_val,
                label=key, color=colors[key.split("-")[0]])
        prev_client_val = (value if prev_client_val is None else np.add(prev_client_val, value))
      elif "server" in key:
        ax.bar(graph_options["XAXIS-N"]+width/2, value, width, bottom=prev_server_val,
                label=key, color=colors[key.split("-")[0]])
        prev_server_val = (value if prev_server_val is None else np.add(prev_server_val, value))
      else:
        ax.bar(graph_options["XAXIS"], value, width, bottom=prev_val, label=key)
    prev_val = (value if prev_val is None else np.add(prev_val, value))


# Iperfille max,min,mean plotterit per runi ja tämä olisi plot_full_iperf? Well, this has everything now
def plot_iperf(ax, stats_dict, graph_options):
  # TODO If stats_dict files has multiple files, then do something else. First, just plot one test
  # Loop through "intervals" list, get "streams" first list item
  # - get bits per sec and RTT and add to list in dict
  # Key "end": get mean, max, min RTT

  # TODO Uus:
  # Voidaan käydä läpi kaikki ne sekunnin välein olevat JSON setit, ja laskea niistä ite keskiarvo. Ellei sitä tietysti lue suoraan jossain JSONissa.
  # Standardisoisko vaikka kaikki bandwidthit bittiä sekunnissa? Kun me tiedetään että linkki max on 25Gbps. Voidaan parametrillä laittaa MB/s halutessa.
  labels_arr = [""] # get these from COMPARE
  throughput_arr = [[]]
  max_rtt_arr = [[]]
  mean_rtt_arr = [[]]
  min_rtt_arr = [[]]
  index = 0

  if "COMPARE" in graph_options and not "timeline" in graph_options["ARGS"]:
    labels_arr[0] = graph_options["COMPARE"][0]
    for i in range(len(graph_options["COMPARE"])-1):
      throughput_arr.append([])
      max_rtt_arr.append([])
      mean_rtt_arr.append([])
      min_rtt_arr.append([])
      labels_arr.append(graph_options["COMPARE"][i+1])

  for key, value in stats_dict.items():
    # timeline arg: plot the throughput seen each second during the test: X-axis e.g. 1-10 seconds. Making a graph for one run each
    if "timeline" in graph_options["ARGS"]:
      interval_arr = []
      for interval in value["intervals"]:
        if "latency" in graph_options["ARGS"]:
          rtt = interval["streams"][0]["rtt"]
          if "us" not in graph_options["ARGS"]:
            rtt /= 1000
          interval_arr.append(rtt)
        else:
          # Megabits ps
          throughput = interval["streams"][0]["bits_per_second"] / 1000000
          if "gbps" in graph_options["ARGS"]:
            throughput = throughput / 1000
          interval_arr.append(throughput)
      #value["end"]
    
      lbl = key
      if "LABELS" in graph_options:
        lbl = graph_options["LABELS"][index]
      #for i, value in enumerate(interval_arr):
      ax.plot(list(range(1, len(interval_arr)+1)), interval_arr, label=lbl)#graph_options["XAXIS"], interval_arr, label=key)

      for i, val in enumerate(interval_arr):
        ax.annotate(round(val, 2), (i+1, val))#(graph_options["XAXIS"][i], val))
      
      index += 1
    else:
      if "COMPARE" in graph_options:
        for i, c in enumerate(graph_options["COMPARE"]):
          if c in key:
            index = i
            break
      # Plot the throughput according to the end values of each run, making a graph made of different runs
      # Megabits ps
      throughput = value["end"]["streams"][0]["sender"]["bits_per_second"] / 1000000
      if "gbps" in graph_options["ARGS"]:
        throughput = throughput / 1000
      throughput_arr[index].append(throughput)
      us_modifier = 1000
      if "us" in graph_options["ARGS"]:
        us_modifier = 1
      max_rtt_arr[index].append(value["end"]["streams"][0]["sender"]["max_rtt"] / us_modifier)
      mean_rtt_arr[index].append(value["end"]["streams"][0]["sender"]["mean_rtt"] / us_modifier)
      min_rtt_arr[index].append(value["end"]["streams"][0]["sender"]["min_rtt"] / us_modifier)

  # TODO -- Graph the different iperf runs!
  # How to COMPARE? How did it work? Do we need nested arrays? MAyyyybe (unou min rtt arr jne joka comparoitavalle asialle)
  if not "timeline" in graph_options["ARGS"]:
    for i, lbl in enumerate(labels_arr):
      if "LABELS" in graph_options and len(graph_options["LABELS"]) == len(labels_arr):
        lbl = graph_options["LABELS"][i]
      if "latency" in graph_options["ARGS"]:
        if "min" in graph_options["ARGS"]:
          ax.plot(graph_options["XAXIS"], min_rtt_arr[i], label=lbl+" Min")
        if "max" in graph_options["ARGS"]:
          ax.plot(graph_options["XAXIS"], max_rtt_arr[i], label=lbl+" Max")
        if "mean" in graph_options["ARGS"]:
          ax.plot(graph_options["XAXIS"], mean_rtt_arr[i], label=lbl+" Mean")
        for j, val in enumerate(mean_rtt_arr[i]):
          ax.annotate(round(val, 2), (graph_options["XAXIS"][j], mean_rtt_arr[i][j]))
      else:
        ax.plot(graph_options["XAXIS"], throughput_arr[i], label=lbl)
        for j, val in enumerate(throughput_arr[i]):
          ax.annotate(round(val, 2), (graph_options["XAXIS"][j], throughput_arr[i][j]))

def plot_netpipe(ax, stats_dict, graph_options):
  index = 0
  for key, value in stats_dict.items():
    #for i,b in enumerate(value["NP-BYTES"]):
    #  print(b, value["NP-LATENCY"][i], value["NP-THROUGHPUT"][i])
    lbl = key
    if "LABELS" in graph_options:
      lbl = graph_options["LABELS"][index]
    if "latency" in graph_options["ARGS"]:
      ax.plot(value["NP-BYTES"], value["NP-LATENCY"], label=lbl) # usec or ms determined in parsing
    elif "throughput" in graph_options["ARGS"]:
      ax.plot(value["NP-BYTES"], value["NP-THROUGHPUT"], label=lbl) # Mbps or Gbps determined in parsing
    else:
      print("ERROR: No argument 'latency' or 'throughput' specified for netpipe plotting")
      exit(1)

    if "ANNOTATE" not in graph_options or ("ANNOTATE" in graph_options and lbl in graph_options["ANNOTATE"]):
      annotate_these = [1, 4, 32, 64, 256, 2048, 8192, 32768, 131072, 524288, 1048576]
      for i, bytes in enumerate(value["NP-BYTES"]):
        if bytes in annotate_these:
          print(bytes)
          if "latency" in graph_options["ARGS"]:
            ax.annotate(round(value["NP-LATENCY"][i], 2), (bytes, value["NP-LATENCY"][i]))
          elif "throughput" in graph_options["ARGS"]:
            ax.annotate(round(value["NP-THROUGHPUT"][i], 2), (bytes, value["NP-THROUGHPUT"][i]))
    # No scientific notation
    ax.ticklabel_format(useOffset=False, style='plain')
    index += 1


def plot_ib_perftest(ax, ax2, stats_dict, graph_options):
  index = 0
  print("TODO: Infiniband graph shows microseconds always")
  for key, value in stats_dict.items():
    if "CPU" in key:
      print("ERROR: CPU file spotted, CPU means cannot be integrated to IB graph")
      return
    lbl = ""
    if "LABELS" in graph_options:
      lbl = " " + graph_options["LABELS"][index]
    if "latency" in graph_options["ARGS"]:
      if "min" in graph_options["ARGS"]:
        ax.plot(value["IB-BYTES"], value["MIN"], label="Min"+lbl)
      if "max" in graph_options["ARGS"]:
        ax.plot(value["IB-BYTES"], value["MAX"], label="Max"+lbl)
      if "mean" in graph_options["ARGS"]:
        ax.errorbar(value["IB-BYTES"], value["MEAN"], yerr=value["STDEV"], capsize=5, label="Mean"+lbl)
      if "PERCENTILES" in graph_options and "99" in graph_options["PERCENTILES"]:
        ax.plot(value["IB-BYTES"], value["99%"], label="99%"+lbl)
      if "PERCENTILES" in graph_options and "99.9" in graph_options["PERCENTILES"]:
        ax.plot(value["IB-BYTES"], value["99.9%"], label="99.9%"+lbl)
    elif "throughput" in graph_options["ARGS"]:
      ax.plot(value["IB-BYTES"], value["BW-PEAK"], label="Peak"+lbl) # Mb/s or Gb/s
      ax.plot(value["IB-BYTES"], value["BW-AVG"], label="Avg"+lbl) # Mb/s or Gb/s
      ax2.plot(value["IB-BYTES"], value["BW-MPPS"], linestyle="dashed", label="Msg-rate"+lbl) #Mega packets per s

    annotate_these = [2, 4, 32, 64, 256, 2048, 8192, 32768, 131072, 524288, 1048576]
    for i, bytes in enumerate(value["IB-BYTES"]):
      if bytes in annotate_these:
        print(bytes)
        if "latency" in graph_options["ARGS"]:
          if "mean" in graph_options["ARGS"]:
            ax.annotate(round(value["MEAN"][i], 2), (bytes, value["MEAN"][i]))
        elif "throughput" in graph_options["ARGS"]:
          ax.annotate(round(value["BW-AVG"][i], 2), (bytes, value["BW-AVG"][i]))
    index += 1
  # No scientific notation
  #ax.ticklabel_format(useOffset=False, style='plain')

#####################################
# - Main
#####################################

def main():
  # Program arguments
  parser = argparse.ArgumentParser(description='Plot graphs from files')
  parser.add_argument('-f', type=str, dest="file", default="", required=True,
                      help="Graph options file to use. All settings for title, axes, stat files etc. should be given in this file according to readme")

  args = parser.parse_args()
  print(args)


  # Stats per file
  stats_dict = OrderedDict() # TODO this stats_dict no longer used
  graph_options = parse_graph_options(args.file)

  print("Graph options only:", graph_options)

  parse_files(graph_options, stats_dict)

  # Plotting
  # figsize change for multiple subplots
  plt.rcParams["figure.figsize"] = (10 * len(graph_options["SUBPLOTS"][0]), 6 * len(graph_options["SUBPLOTS"])) # 9, 6
  print("Subplot dimensions", len(graph_options["SUBPLOTS"]), len(graph_options["SUBPLOTS"][0]))
  # sharey: if we want to share the same y axis scale
  # Squeeze=False: always give us a 2D array for use here, even if only one graph
  fig, axes = plt.subplots(len(graph_options["SUBPLOTS"]), len(graph_options["SUBPLOTS"][0]), squeeze=False, sharey=graph_options["SHAREY"])#1,1)
  print("Remember to put 'wrk' or other type into an ARG to get percentiles etc also from wrk now!")

  for ri, row in enumerate(graph_options["SUBPLOTS"]):
    for ci, graph in enumerate(row):
      ax2 = None # For second y axis
      graphs = 0 # How many graphs drawn
      if "COMPARE" in graph:
        graphs += len(graph["COMPARE"])

      if "cpu" in graph["ARGS"] or "cpu-mean" in graph["ARGS"]: # DO NOT use with throughput ! it already creates ax2 twinx
        if len(graph["ARGS"]) > 2:# 2 as if more than ARGS cpu and cpu-mean # graphs > 0: # This already means that there are per-run graphs and we need mean CPU usage!
          ax2 = axes[ri][ci].twinx()
        plot_cpu_usage(axes[ri][ci], ax2, graph["STATS"], graph)
        graphs += 2
      if "iperf" in graph["ARGS"]: #args.iperf:
        graphs += len(graph["STATFILES"])
        plot_iperf(axes[ri][ci], graph["STATS"], graph)

      
      elif "netpipe" in graph["ARGS"]:
        graphs += 2
        #ax2 = axes[ri][ci].twinx() # maybe throughput to separate graph? Compare multiple netpipe results in one
        plot_netpipe(axes[ri][ci], graph["STATS"], graph)
      elif "ib" in graph["ARGS"]:
        if "throughput" in graph["ARGS"]:
          ax2 = axes[ri][ci].twinx()
        graphs += 2
        plot_ib_perftest(axes[ri][ci], ax2, graph["STATS"], graph)

      # Shared functions for different benchmarks
      elif len(list(set(["wrk", "sockperf"]) & set(graph["ARGS"]))) > 0:
        if len(list(set(["max", "min", "mean"]) & set(graph["ARGS"]))) > 0:
          graphs += 2
          plot_latencies_maxminmean(axes[ri][ci], graph["STATS"], graph)
        if "percentiles" in graph["ARGS"]:#len(args.percentiles):
          graphs += len(graph["PERCENTILES"]) #len(args.percentiles)
          #graph_options["PERCENTILES"] = args.percentiles #set in the file
          plot_percentiles(axes[ri][ci], graph["STATS"], graph)
        if "throughput" in graph["ARGS"]:
          graphs += 2
          ax2 = axes[ri][ci].twinx()
          plot_throughput(axes[ri][ci], ax2, graph["STATS"], graph)

      # Graph legends
      if graphs > 1:
        # Shrink the graph for legends
        # Shrink slightly more if only one column
        modifier = 0
        if len(row) > 1:
          modifier = 0.05
        box = axes[ri][ci].get_position()
        if not "floatlegend" in graph["ARGS"]:
          axes[ri][ci].set_position([box.x0, box.y0, box.width * (0.90+modifier), box.height])
        legend_title = ""
        if "cpu-mean" in graph["ARGS"]:
          legend_title = "CPU:\nclient&server"
        # Legend has a set position, option to float with "floatlegend"
        if "floatlegend" in graph["ARGS"]:
          axes[ri][ci].legend(title=legend_title)
        else:
          axes[ri][ci].legend(bbox_to_anchor=(1.035,1), title=legend_title)
        if ax2 is not None and "cpu" in graph["ARGS"]:
          if all(x in ["user", "kernel", "sw-int"] for x in graph["CPU-METRICS"]):
            # Custom legend for CPU
            legend_elements = [Line2D([0], [0], color='m', lw=4, alpha=0.5, label='User'),
                              Line2D([0], [0], color='y', lw=4, alpha=0.5, label='Kernel'),
                              Line2D([0], [0], color='c', lw=4, alpha=0.5, label='SW-int')]
            ax2.legend(title="CPU:\nclient&server", handles=legend_elements, bbox_to_anchor=(1.035,0.3))
          else:
            ax2.legend(title="CPU:\nclient&server")
          #handles, labels = ax2.get_legend_handles_labels()
          #ax2.legend(list(set(handles)), list(set(labels)), title="CPU usage,\nclient&server")
        elif ax2 is not None:
          ax2.legend(bbox_to_anchor=(1.035,0.3), loc="center left")
      if "XAXIS" in graph and "XAXIS-N" in graph:
        print("XAXIS in", ri, ci)
        print(graph["XAXIS"])
        print(graph["XAXIS-N"])
        plt.xticks(graph["XAXIS-N"], graph["XAXIS"]) # Numeric values to string values
      try:
        # Labeling
        axes[ri][ci].set_xlabel(graph["AXES"][0])
        axes[ri][ci].set_ylabel(graph["AXES"][1])
        if ax2 is not None:
          ax2.set_ylabel(graph["AXES"][2])
      except IndexError:
        print("Not enough axes defined with AXES! Use AXES x,y,y2")
        return 1
      # Logaritmic y axis in most cases
      if not "nology" in graph["ARGS"] and not "cpu-mean" in graph["ARGS"]:# and not "netpipe" in graph["ARGS"]:
        axes[ri][ci].set_yscale("log", nonpositive="clip") # Nonpositive to help larger stdev than mean to show, maybe not needed
      # Logarithmic x axis for the tests that have data points per byte sizes
      if not "nologx" in graph["ARGS"] and len(list(set(["ib", "netpipe"]) & set(graph["ARGS"]))) > 0:
        print("Netpipe and IB perftest uses log xaxis, Disable with 'nologx' arg")
        axes[ri][ci].set_xscale("log", nonpositive="clip")
      if "AXTITLE" in graph:
        axes[ri][ci].set_title(graph["AXTITLE"])

  if "TITLE" in graph_options:
    if "TITLE2" in graph_options:
      graph_options["TITLE"] += "\n" + graph_options["TITLE2"]
    fig.suptitle(graph_options["TITLE"])
  # Either show or save fig
  #plt.show()
  plt.savefig(graph_options["FILENAME"])
  #print("Saved", graph_options["FILENAME"])

if (__name__ == '__main__'):
  main()