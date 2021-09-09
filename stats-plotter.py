import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import argparse
import os
import sys
import json
from collections import OrderedDict


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

def parse_cpu_data(lines):
  return_dict = {}
  # List for each stat for CPU, such as usage percentage of user, kernel, interrupt etc.
  return_dict["CPU"] = [[] for i in range(7)]
  for line in lines:
    items = [float(x) for x in line.replace(',', '.').split(' ')]
    for i, perc in enumerate(items):
      return_dict["CPU"][i].append(perc)

  # Calculate means of CPU stats
  return_dict["CPU-MEANS"] = []
  for cpu_statlist in return_dict["CPU"]:
    return_dict["CPU-MEANS"].append(sum(cpu_statlist) / len(cpu_statlist))

  return return_dict

# parse wrk and CPU files in their data functions
def parse_files(graph_options, stats_dict):
  filedir = ""
  # Can specify another directory relative to current one for stat files
  if graph_options["FILEDIR"] is not None:
    filedir = graph_options["FILEDIR"] + "/"
  # done: go through every subplot row element in for loop and column element in a nested for
  # It shouldn't be too bad. After this, similar nested for, for the graphing system at the end!
  # done stats_dict myös nested muotoon??? - Tallennetaan graph optionsiin..
  for row in graph_options["SUBPLOTS"]:
    for graphopt in row:
      # Each graph gets its own ordered dict
      graphopt["STATS"] = OrderedDict()
      for f in graphopt["STATFILES"]:#list(files):
        with open("./" + filedir + f, "r") as statfile:
          if "iperf" in graphopt["ARGS"]:
            # Put everything in iperf JSON to dict
            graphopt["STATS"][f] = json.load(statfile)
          else:
            lines = statfile.readlines()
            #name = ""
            #if stat_type == "wrk":
            #  # Get second row: eg. "1 threads and 10 connections", as graph name
            #  name = lines[1].lstrip().rstrip()
            #else:
            # Use file name
            name = f
            graphopt["STATS"][name] = parse_wrk_data(lines)
      # TODO: jos ei ole CPU filuja määritelty, mutta ARG cpu on, hae cpu filet wrkfilejen perusteella! done
      # Eli luo filesistä uusi lista, jossa haetaan joka filulla pääte -CPU-client ja -CPU-server
      # Pidä huoli järjestyksestä koska siinä orderissa data esitetään.. Tai tarkista file name (stats_dict key) kumpi se on kun graafataan
      # Ehkä jopa voisi laittaa CPU filet itse wrk filun stats_dict entryn alle jotta ainakin olis koherentti
      # Tai sit vaan ettii stats_dict saman niminen filu ja vielä client tai serveri, ehkä se helpompi tapa
      # Find CPU stat files based on the actual statfiles if not given
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
          name = f
          graphopt["STATS"][name] = parse_cpu_data(lines)

  return 0

#def parse_json_files(files, stats_dict):
#  # Put everything to dict
#  for f in files:
#    with open("./" + f, "r") as statfile:
#      stats_dict[f] = json.load(statfile)

# Read the mandatory options file
def parse_graph_options(file):
  # Dictionary stores all options
  return_dict = {}
  # Different subplots are stored in this array of arrays, the inside arrays containing columns and outer the rows
  # Eli: Sisempään lisättäessä dictejä, mennään vasemmalta oikealle. Ulos lisättäessä mennään alas.
  # TODO: argument COLUMNS to determine the width of SUBPLOTS: done
  # The graph options are then parsed in the order left to right, top to bottom subplots, basic reading system
  # Keyword SUBPLOT separates the plots. When this keyword comes, we move to the next column, appending to the inner array.
  # unless if we are at last column,
  # in which case we move to the next row. Creating (appending) another array in outer SUBPLOTS array.
  # With this we won't need another for loop breaking things in the readline loop.
  # TODO: the file parser has to support this. It has to go through SUBPLOTS and parse the files associated with each, saving to each.
  # The graphing system has to be in a for loop that also goes through these subplots. Should be ez as we know the size of subplots.
  # We won't need a change in plotter functions, so that they plot to ax[x][y], bc the specific ax is forwarded from the graphing system
  return_dict["SUBPLOTS"] = [[{}]]
  # each of the SUBPLOTS array elements contain a dictionary for a graph!
  columns = 1 # This is changed only once when the keyword COLUMNS comes. and checked only when
  # the keyword: SUBPLOT comes.
  cur_col = 0 # This is changed back to 1 when we have parsed ==columns when keyword SUBPLOT comes.
  cur_row = 0 # We need this for indexing
  # ((I think it is not needed)v, as we can always just append more rows. Which is done if we exceed final column.
  # (we stil need to use the indexes soo.. it is needed)
  # TODO ! the new format return_dict["ARGS"] -> return_dict["SUBPLOTS"][cur_row][cur_col]["ARGS"]
  return_dict["SUBPLOTS"][0][0]["STATFILES"] = []
  return_dict["SUBPLOTS"][0][0]["CPUFILES"] = []
  return_dict["SUBPLOTS"][0][0]["ARGS"] = []
  # should we make a filedir for each graph? global for now
  return_dict["FILEDIR"] = None # If stat files in different directory
  # TODO argumentteihin: ARG us, mikrosekunneille

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
        elif split[0] in ["AXES", "XAXIS", "LABELS"]:
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
        # Filename read mode last per plot. Switch to another file mode with a keyword
        elif read_filenames:
          if line.rstrip() == "": # Skip empty line
            continue
          if line.startswith("CPUFILES"):
            read_cpu_filenames = True
            read_filenames = False
            continue
          return_dict["SUBPLOTS"][cur_row][cur_col]["STATFILES"].append(line.rstrip()) # TODO appendaako tämä myös tyhjät rivit jos semmoisia tulee optionsin perään? Ja rikkoo asioita. Jos, niin tsekki alkuun ja continue
        elif read_cpu_filenames:
          if line.rstrip() == "": # Skip empty line
            continue
          if line.startswith("FILES"):
            read_cpu_filenames = False
            read_filenames = True
            continue
          return_dict["SUBPLOTS"][cur_row][cur_col]["CPUFILES"].append(line.rstrip())

  # TODO except keyerror: tarvittavien checki tähän?
  # Give XAXIS-N (numeric indexes for xaxis elements) to final subplot
  if "XAXIS" in return_dict["SUBPLOTS"][cur_row][cur_col]:
    return_dict["SUBPLOTS"][cur_row][cur_col]["XAXIS-N"] = np.arange(len(return_dict["SUBPLOTS"][cur_row][cur_col]["XAXIS"])) # Used to move the possible CPU bars slightly
  return return_dict

# Plotting functions
# TODO hmm, moni näistä voisi lisätä yhteen funktioon joka käy läpi kaikki asetukset max,min,mean jne
# Nää kaikki suorittaa saman operaation..
def plot_max_latencies(ax, stats_dict, graph_options):
  max_arr = []
  for key, value in stats_dict.items():
    if "CPU" in key: # Don't go through CPU stat files
        continue
    # Convert to milliseconds
    max_arr.append(value["MAX"] / 1000)
  
  ax.plot(graph_options["XAXIS"], max_arr, label="Max")
  # Annotate if no 99.999th percentile graph
  if not "percentiles" in graph_options["ARGS"] or not "99.999" in graph_options["PERCENTILES"]:
    for i, value in enumerate(max_arr):
      ax.annotate(round(value, 2), (graph_options["XAXIS"][i], max_arr[i]))
  
def plot_min_latencies(ax, stats_dict, graph_options):
  min_arr = []
  for key, value in stats_dict.items():
    if "CPU" in key: # Don't go through CPU stat files
        continue
    # Convert to milliseconds
    min_arr.append(value["MIN"] / 1000)
  
  ax.plot(graph_options["XAXIS"], min_arr, label="Min")

  for i, value in enumerate(min_arr):
    ax.annotate(round(value, 2), (graph_options["XAXIS"][i], min_arr[i]))

def plot_mean_latencies(ax, stats_dict, graph_options):
  # Mean with standard deviation
  mean_arr = []
  stdev_arr = []
  for key, value in stats_dict.items():
    if "CPU" in key: # Don't go through CPU stat files
        continue
    # Convert to milliseconds
    mean_arr.append(value["MEAN"] / 1000)
    stdev_arr.append(value["STDEV"] / 1000)
  
  #ax.plot(graph_options["XAXIS"], mean_arr, label="Mean")
  ax.errorbar(graph_options["XAXIS"], mean_arr, yerr=stdev_arr, capsize=6, color="darkslategray", label="Mean")

  for i, value in enumerate(mean_arr):
    ax.annotate(round(value, 2), (graph_options["XAXIS"][i], mean_arr[i]))

def plot_percentiles(ax, stats_dict, graph_options):
  percentile_dict = {}
  for perc in graph_options["PERCENTILES"]:
    percentile_dict[perc + "%"] = []
    for key, value in stats_dict.items():
      if "CPU" in key: # Don't go through CPU stat files
        continue
      latency_val = value[perc + "%"]
      # Convert to milliseconds
      latency_val /= 1000
      percentile_dict[perc + "%"].append(latency_val)
  for key, value in percentile_dict.items():
    ax.plot(graph_options["XAXIS"], value, label=key)

    for i, val in enumerate(value):
      ax.annotate(round(val, 2), (graph_options["XAXIS"][i], value[i]))

def plot_throughput(ax, ax2, stats_dict, graph_options):
  #graph_dict = {}
  #graph_dict["Throughput"] = []
  #graph_dict["Requests"] = []
  throughput_arr = []
  requests_arr = []
  for key, value in stats_dict.items():
    throughput_arr.append(value["BYTES"])
    requests_arr.append(value["REQUESTS"])

  ax.plot(graph_options["XAXIS"], throughput_arr, label="Throughput")
  ax2.plot(graph_options["XAXIS"], requests_arr, label="Requests")

  for i, val in enumerate(throughput_arr):
    ax.annotate(val, (graph_options["XAXIS"][i], throughput_arr[i]))
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
    # TODO tsekkaa lukeeko keyssä "CPU". Tää tsekki muuten tarvii sit jokaselle muullekin plottaajalle jotta se ei käy läpi cpu dataa? Jota ei ole, tai tää wrk dataa
    if not "CPU" in key: # TODO softan ohjeisiin että cpu filuissa pitää sisältyä toi keyword
      continue
    run_key = key.split("CPU")[0]
    if run_key not in unpaired_keys: # TODO unused
      unpaired_keys.append(run_key)

    # 1 second between measurements
    timevalues = list(range(1, len(value["CPU"][0]) + 1))
    #timevalues = [v * 15 for v in timevalues] # 15 seconds
    
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
                label=key.split("-client")[0], color=colors[key.split("-")[0]])
        prev_client_val = (value if prev_client_val is None else np.add(prev_client_val, value))
      elif "server" in key:
        ax.bar(graph_options["XAXIS-N"]+width/2, value, width, bottom=prev_server_val,
                label=key.split("-server")[0], color=colors[key.split("-")[0]])
        prev_server_val = (value if prev_server_val is None else np.add(prev_server_val, value))
      else:
        ax.bar(graph_options["XAXIS"], value, width, bottom=prev_val, label=key)
    prev_val = (value if prev_val is None else np.add(prev_val, value))
  


def plot_iperf(ax, stats_dict, graph_options):
  # TODO If stats_dict files has multiple files, then do something else. First, just plot one test
  # Loop through "intervals" list, get "streams" first list item
  # - get bits per sec and RTT and add to list in dict
  # Key "end": get mean, max, min RTT
  graph_dict = {}
  graphlabel = "Throughput"
  index = 0
  if "latency" in graph_options["ARGS"]:
    graphlabel = "RTT"
  for key, value in stats_dict.items():
    interval_arr = []
    for interval in value["intervals"]:
      if "latency" in graph_options["ARGS"]:
        print("TODO iperf latencies to milliseconds")
        interval_arr.append(interval["streams"][0]["rtt"])
      else:
        interval_arr.append(interval["streams"][0]["bits_per_second"] / 1000000)
    #value["end"]
  
    #for i, value in enumerate(interval_arr):
    ax.plot(list(range(1, len(interval_arr)+1)), interval_arr, label=key)#graph_options["XAXIS"], interval_arr, label=key)

    for i, val in enumerate(interval_arr):
      ax.annotate(round(val, 2), (i+1, val))#(graph_options["XAXIS"][i], val))
    index += 1


def main():
  # Program arguments
  parser = argparse.ArgumentParser(description='Plot graphs from files')
  parser.add_argument('-f', type=str, dest="file", default="", required=True,
                      help="Graph options file to use. All settings for title, axes, stat files etc. should be given in this file according to readme, which is TODO!")
  parser.add_argument('--us', dest="use_microseconds", action="store_const", const=True, default=False,
                      help="NOT IMPLEMENTED Show latencies in microseconds instead of milliseconds TODO into args in graph options")
  parser.add_argument('--max-latency', dest="max", action="store_const", const=True, default=False,
                      help="OBSOLETE Comparison of maximum latencies")
  parser.add_argument('--min-latency', dest="min", action="store_const", const=True, default=False,
                      help="OBSOLETE Comparison of minimum latencies")
  parser.add_argument('--mean-latency', dest="mean", action="store_const", const=True, default=False,
                      help="OBSOLETE Comparison of mean latencies")
  parser.add_argument('--percentile', type=str, dest="percentiles", default=[], nargs="*",
                      help="OBSOLETE Give the percentile values to compare")
  parser.add_argument('--cpu', dest="cpu", action="store_const", const=True, default=False,
                      help="OBSOLETE Read CPU usage statistics files")
  parser.add_argument('--iperf', dest="iperf", action="store_const", const=True, default=False,
                      help="OBSOLETE Read iperf3 statistics files")
  args = parser.parse_args()
  print(args)
  #files = args.files
  #stat_type = "wrk"
  #if args.cpu:
  #  stat_type = "cpu"

  # Stats per file
  stats_dict = OrderedDict() # TODO this stats_dict no longer used
  graph_options = parse_graph_options(args.file)

  print("Graph options only:", graph_options)
  # TODO determine if iperf works
  #if "iperf" in graph_options["SUBPLOTS"][0][0]["ARGS"]: #args.iperf:
  #  parse_json_files(graph_options["STATFILES"], stats_dict)
  #else:
  parse_files(graph_options, stats_dict)

  #print(stats_dict.keys())
  #for key, value in stats_dict.items():
  #  print(key, value)

  # Plotting
  # Tulevaisuuden todo, mahdollisuus yhdistää useita graafeja yhteen kuvaan?
  # Parametri subploteille ja/tai eri filelistat eri graafeille joissa kuitenkin samat datat
  # For loop joka plottaa useamman jutun, i vaihtaa subplottia
  # Tarvii joka plotille oman dictionaryn ja sit ajaa vaan tän saman setin jokaiselle parsinnan jälkeen
  # Plotter optionsissa jollakin keywordilla vaihtuu toisen subplotin inffoksi, ne jakaa kuitenkin titlen esim
  # TODO figsize change for multiple subplots? Kato miltä ne näyttää eka
  plt.rcParams["figure.figsize"] = (10, 6) # 9, 6
  # TODO: variable subplots from the options
  print("DEBUGINFO", len(graph_options["SUBPLOTS"]), len(graph_options["SUBPLOTS"][0]))
  # Squeeze=False: always give us a 2D array for use here, even if only one graph
  fig, axes = plt.subplots(len(graph_options["SUBPLOTS"]), len(graph_options["SUBPLOTS"][0]), squeeze=False)#1,1)
  # TODO: two nested for loops starting here
  for ri, row in enumerate(graph_options["SUBPLOTS"]):
    for ci, graph in enumerate(row):
      ax2 = None # For second y axis
      graphs = 0 # How many graphs drawn

      if "cpu" in graph["ARGS"] or "cpu-mean" in graph["ARGS"]: # DO NOT use with throughput ! it already creates ax2 twinx
        if len(graph["ARGS"]) > 1:# graphs > 0: # This already means that there are per-run graphs and we need mean CPU usage!
          ax2 = axes[ri][ci].twinx()
        # TODO tää on vielä tekemättä !! Ja poista cpu tosta ylemmästä eliffistä!
        # Tän operaation jälkeen tän voisi lyyä Nokia Gittiin turvaan muute! Tai vähintään Driveen ekaks
        plot_cpu_usage(axes[ri][ci], ax2, graph["STATS"], graph)
        graphs += 2
      if "iperf" in graph["ARGS"]: #args.iperf:
        graphs += len(graph["STATFILES"])
        plot_iperf(axes[ri][ci], graph["STATS"], graph)
      #elif args.cpu: # TODO !!! mukaan muihin "cpu" "cpu-mean" in graph_options["ARGS"]
      #  #print("Assuming 15 seconds between measurements!")
      #  graphs += len(graph_options["STATFILES"]) + 1 # TODO graafien määrä oikein, nyt halutaan aina legend ni laitoin vaa +1
      #  plot_cpu_usage(ax, stats_dict, graph_options)
      elif "percentiles" in graph["ARGS"]:#len(args.percentiles):
        graphs += len(graph["PERCENTILES"]) #len(args.percentiles)
        #graph_options["PERCENTILES"] = args.percentiles #set in the file
        plot_percentiles(axes[ri][ci], graph["STATS"], graph)
      elif "throughput" in graph["ARGS"]:
        graphs += 2
        ax2 = axes[ri][ci].twinx()
        plot_throughput(axes[ri][ci], ax2, graph["STATS"], graph)

      if "max" in graph["ARGS"]: #args.max:
        graphs += 1
        plot_max_latencies(axes[ri][ci], graph["STATS"], graph)
      if "min" in graph["ARGS"]: #args.min:
        graphs += 1
        plot_min_latencies(axes[ri][ci], graph["STATS"], graph)
      if "mean" in graph["ARGS"]: #args.mean:
        graphs += 1
        plot_mean_latencies(axes[ri][ci], graph["STATS"], graph)
      
      # TODO cpu tähän vikaks, jos on muita niin ne plotataan tossa yllä. voidaan kattoo
      # vaikka graphs muuttujasta et meneekö omaan y akseliinsa
      #if "cpu" or "cpu-mean" in graph_options["ARGS"]: # DO NOT use with throughput ! it already creates ax2 twinx
      #  if len(graph_options["ARGS"]) > 1:# graphs > 0: # This already means that there are per-run graphs and we need mean CPU usage!
      #    ax2 = ax.twinx()
      #  # TODO tää on vielä tekemättä !! Ja poista cpu tosta ylemmästä eliffistä!
        # Tän operaation jälkeen tän voisi lyyä Nokia Gittiin turvaan muute! Tai vähintään Driveen ekaks
      #  plot_cpu_usage(ax, ax2, stats_dict, graph_options)
      #  graphs += 2

      if graphs > 1:
        # Shrink the graph for legends
        box = axes[ri][ci].get_position()
        axes[ri][ci].set_position([box.x0, box.y0, box.width * 0.95, box.height])
        axes[ri][ci].legend(bbox_to_anchor=(1.035,1))
        if ax2 is not None:
          if all(x in ["user", "kernel", "sw-int"] for x in graph["CPU-METRICS"]):
            legend_elements = [Line2D([0], [0], color='m', lw=4, alpha=0.5, label='User'),
                              Line2D([0], [0], color='y', lw=4, alpha=0.5, label='Kernel'),
                              Line2D([0], [0], color='c', lw=4, alpha=0.5, label='SW-int')]
            ax2.legend(title="CPU:\nclient&server", handles=legend_elements, bbox_to_anchor=(1.035,0.4))
          else:
            ax2.legend(title="CPU usage of\nclient&server")
          #handles, labels = ax2.get_legend_handles_labels()
          #ax2.legend(list(set(handles)), list(set(labels)), title="CPU usage,\nclient&server")
      if "XAXIS" in graph:
        plt.xticks(graph["XAXIS-N"], graph["XAXIS"]) # Numeric values to string values
      try:
        axes[ri][ci].set_xlabel(graph["AXES"][0])
        axes[ri][ci].set_ylabel(graph["AXES"][1])
        if ax2 is not None:
          ax2.set_ylabel(graph["AXES"][2])
      except IndexError:
        print("Not enough axes defined with AXES! Use AXES x,y,y2")
        return 1
      if not "cpu-mean" in graph["ARGS"]:
        axes[ri][ci].set_yscale("log", nonpositive="clip") # Nonpositive to help larger stdev than mean to show, maybe not needed

  # TODO: nested for loops stop here!
  # We could use plt.show to test subplots without saving an actual file

  if "TITLE2" in graph_options:
    graph_options["TITLE"] += "\n" + graph_options["TITLE2"]
  fig.suptitle(graph_options["TITLE"])
  #ax.set_title(graph_options["TITLE"] + "\n asdlol")
  # Either show or save fig
  plt.show()
  #plt.savefig(graph_options["FILENAME"])
  #print("Saved", graph_options["FILENAME"])
  print("Latencies are now in MILLISECONDS!")

if (__name__ == '__main__'):
  main()