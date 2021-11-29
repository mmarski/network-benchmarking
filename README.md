# WRK / iperf3 / Sockperf benchmark script for Kubernetes or bare metal

Is configured for the Master's thesis tests, using either Raspberry Pi cluster or Nokia Airframe cluster, with their IP addresses

Can loop a list of data sizes for Sockperf or iperf3, or file names for wrk. In the case of wrk, it tests for example fetching http://nginx-address:90/1B.bin , assuming the Nginx server is serving a file named 1B.bin. Also, there are ports 90 and 100 determined for Nginx, for bare metal and Kubernetes service respectively.

The amount of loops should match the arrays used, for example wrk file list of size 13 should then imply a loop starting from 1 and ending at 13. Use --starti and --endi, or change in script. See also the other possible options able to be given as parameters, or changed directly, at the start of the script.

Use parameter -p to give unique prefix for the output files.

Possible parameters:

```
    -s | --sockperf) SOCKPERF="$2" ;;
    -r | --sockperfrun) SOCKPERF_RUN="$2" ;;
    -i | --iperf) IPERF="$2" ;;
    -v | --vma) VMA="$2" ;;
    -l | --local) LOCAL="$2" ;;
    -c | --cpu) CPU="$2" ;;
    -k | --kubernetes) KUBERNETES="$2" ;;
    -p | --prefix) FILEPREFX="$2" ;;
    -a | --additional) ADDITIONAL_PARAMS="$2" ;;
    -t | --time) TIME="$2" ;;
    -b | --binfile) BINFILE="$2" ;;
    -f | --freeflow) FREEFLOW="$2" ;;
    --starti) I_START="$2" ;;
    --endi) I_END="$2" ;;
    --filearr) USE_FILEARR="$2" ;;
    --dataarr) USE_DATAARR="$2" ;;
    --connarr) USE_CONNARR="$2" ;;
    --threadarr) USE_THREADARR="$2" ;;
```


# Python Plotter script for results

Takes in a file with -f flag, determining all the settings and files to read for a graph.

Multiple plots can be drawn by determining the options for one plot, then using the keyword SUBPLOT, after which repeat the procedure for another graph.

The plotter assumes for example, that the CPU file names contain the keyword "CPU" and "client" and "server" correspondingly, if plotting those.

See the examples for demonstration. Function parse_graph_options has all the possible keywords.

## Possible parameters:
There are multiple possible parameters, some given in a different way than others, categorized here.

### Keyword and one argument
```
TITLE <title>, TITLE2 <title second row> - Global title for the graph
FILENAME <output file name>
FILEDIR <directory> - has to be given at the start of the file to determine a directory where stat files are located, default current directory. Can be given again after FILES or CPUFILES keywords, to change the directory for a graph and all subsequent graphs until another FILEDIR keyword.
COLUMNS <column amount> - How many graphs are drawn in one row
```

### The ARG keyword
```
ARG <argument> <options>
Single plot argument with specific options. Possible arguments:
title <title> - Set a title for the specific plot
cpu <optional space separated params> - for CPU data parsing (from top tool), plot timeline of CPU usages
cpu-mean <optional space separated params> - for CPU data parsing (from top tool), plot mean CPU usages
CPU parameters are space separated, for example: "cpu-mean user kernel sw-int" plots the corresponding CPU information.
percentile <space separated percentile list> - for example "percentile 50 90 99 99.999" gives the corresponding latency percentile graphs. Don't use %, it is added in script.
```

### Required file lists

Either FILES or CPUFILES

Give a list of files to read on the next rows

### Space separated options
```
ARGS <space separated single word arguments>
```

Examples: sockperf - Parse sockperf information, nology - no logaritmic y axis, floatlegend - legend inside graph instead of on the side, us - microsecond usage, gbps - gigabytes per second usage, min - minimum latency graph display

Use argument "latency" or "throughput" to determine which is to be parsed and drawn

### Comma separated options
```
AXES - give the units for axes
XAXIS - x axis values
LABELS - Graph labels, use with COMPARE to give custom labels instead of the COMPARE keywords
COMPARE - Use keywords in file names to create a graph per those files and compare to a graph of other group of files: e.g. bare vs kube
ANNOTATE - Use label names to annotate only specific graphs
```


### Single keyword options
SHAREY - share the Y axis between all plots

SUBPLOT - determines the start of another plot, give the graph options after normally


