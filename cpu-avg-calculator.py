import argparse
import os

# parse CPU files
def parse_files(args, stats_dict):
  # Use search term to get the files
  cpufiles = []
  files = os.listdir(".")
  for f in files:
    if all(x in f for x in args.search_terms) and "CPU" in f and not any(x in f for x in args.omit_terms) and not ".png" in f:
      #print("Found CPU file", f)
      cpufiles.append(f)
  for f in cpufiles:
    with open("./" + f, "r") as statfile:
      lines = statfile.readlines()
      name = f
      # indexes:
      # 0 us=userspace 1 sy=system/kernel (skip ni=niced-user/userdefinedprio)
      # 2 id=idleops 3 wa=waitdisk/peripheral 4 hi=hardwareint 5 si=softwareint
      # 6 st=steal,involuntaryvirtual-cpuwait (hypervisor servicing another processor)
      stats_dict[name] = {}
      stats_dict[name]["CPU"] = [[] for i in range(7)]
      for line in lines:
        items = [float(x) for x in line.replace(',', '.').split(' ')]
        for i, perc in enumerate(items):
          stats_dict[name]["CPU"][i].append(perc)
      # Calculate means of CPU stats
      stats_dict[name]["CPU-MEANS"] = []
      for cpu_statlist in stats_dict[name]["CPU"]:
        stats_dict[name]["CPU-MEANS"].append(round(sum(cpu_statlist) / len(cpu_statlist), 2))

def main():
  # Program arguments
  parser = argparse.ArgumentParser(description='Calculate information for mean CPU usage')
  parser.add_argument('-f', type=str, dest="search_terms", default=[], nargs="*", required=True,
                      help="Search term to find matching CPU stats files")
  parser.add_argument('-o', type=str, dest="omit_terms", default=[], nargs="*",
                      help="Omit files containing these filter words")
  args = parser.parse_args()
  print(args)

  stats_dict = {}
  parse_files(args, stats_dict)

  # Print statistics
  cpu_labels = ["us", "sy", "id", "wa", "hi", "si", "st"]
  for key, value in stats_dict.items():
    print("\n-----")
    print(key + ":")
    for i, lbl in enumerate(cpu_labels):
      if lbl in ["id", "st"]: # Skip unwanted labels/cpu info
        continue
      print(lbl + " avg " + str(value["CPU-MEANS"][i]) + ",", end=" ")
    us_sy_si_sum = (value["CPU-MEANS"][cpu_labels.index("us")]
                  + value["CPU-MEANS"][cpu_labels.index("sy")]
                  + value["CPU-MEANS"][cpu_labels.index("si")])
    print("us+sy+si: " + str(us_sy_si_sum))
    for i, lbl in enumerate(cpu_labels):
      if lbl not in ["us", "sy", "si"]: # Skip unwanted labels/cpu info
        continue
      print(lbl + " perc: " + str(round(value["CPU-MEANS"][i] / us_sy_si_sum * 100, 2)), end=", ")


if (__name__ == '__main__'):
  main()