#!/bin/bash

#declare -a

# this file to run wrk or sockperf (or iperf, TODO?)
# ls -tr to get files in date modified first-last order

# The prefix for the file
FILEPREFX=paramstestrun

# wrk-filesizes baremetallissa ja local tokaan benchmarkkeriin.
# Aja wrk vaikka siitä wrk-vma kontista iha sama.. siel se on jo. tai no, eikös meillä oo se kontti mikä on Kubessa? kaiva se lol. Nginx on nginx-vma kontis.
# -> skandyla/wrk kontti !! se pyörimään ja siihen ajetaan docker exec, lol.
# NEXT sockperf-datasizes-VMA-100mps, latenssi jälleen

# For loop params. Use numbers 1-n
# Wrk sizes: 13. Sockperf sizes: 16
I_START=1
I_END=16

# Define values in arrays
# wrk options: 9
#conn_array=(1 2 3 4 5 8 10 12 14)
conn_array=(1 2 3 4 5 8 8 10 10)
USE_CONNARR=0
#thread_array=(1 2 3 4 5 8 10 12 14)
thread_array=(1 2 3 4 5 2 4 2 5)
USE_THREADARR=0
# WRK (Nginx) filesizes: 13. Generate them again: added 1472, 2kB
# 1B 64B 512B 1kB 1472B 2kB 4kB 32kB 64kB 128kB 256kB 512kB 1M
file_array=(1B 64B 512B 1kB 1472B 2kB 4kB 32kB 64kB 128kB 256kB 512kB 1M)
USE_FILEARR=0
# sockperf options. 16 datasizes
# 1472 should be the data size for filling 1500 MTU suggested by bandwidth test (sockperf said)
datasize_humanarr=(14B 32B 64B 256B 512B 1kB 1472B 2kB 4kB 8kB 32kB 64kB 128kB 256kB 512kB 1M)
data_array=(14 32 64 256 512 1024 1472 2048 4096 8192 32768 65536 131072 262144 524288 1048575)
#data_array=(14 32 64)
USE_DATAARR=1

# Or just once
CONNECTIONS=1
THREADS=1
TIME=180
BINFILE=1kB
DATASIZE=14 # For sockperf. 14 is the MINIMUM and default

# 0 wrk, 1 sockperf
# VMA settingi ja TODO mahdollisesti monitoroi myös vma_stats omaan tiedostoonsa
SOCKPERF=0
# Run: ping-pong or throughput
SOCKPERF_RUN=ping-pong
# Iperf3 run
IPERF=0
# VMA or Freeflow run: VMA only in baremetal, Freeflow only in Kube !!
VMA=0
FREEFLOW=0
# run in raspi or nokia servers
RASPI=1
# Run Bare-metal or in Kubernetes, or both (0,1,2)
KUBERNETES=1
# If baremetal wrk is located in Docker container
DOCKER=0
#Perform CPU measurements. both client and server
CPU=1
# Local run. Set CLIENT and SERVER to same address!
LOCAL=0

# Any other settings? At this moment only for sockperf
# --mps: messages per second for slower send testing. 1000 and 100
ADDITIONAL_PARAMS=

# Program arguments to replace any of the above
# run-benchmark -l 1 -p sockperf-datasizes-VMA-hugepages-local -c 1 -t 180
: '
while getopts "s:r:v:l:c:k:p:a:t:b:f:" flag
do
	case "${flag}" in
		s) SOCKPERF=${OPTARG};;
		r) SOCKPERF_RUN=${OPTARG};;
		v) VMA=${OPTARG};;
		l) LOCAL=${OPTARG};;
		c) CPU=${OPTARG};;
		k) KUBERNETES=${OPTARG};;
		p) FILEPREFX=${OPTARG};;
		a) ADDITIONAL_PARAMS=${OPTARG};;
		t) TIME=${OPTARG};;
		b) BINFILE=${OPTARG};;
		f) FREEFLOW=${OPTARG};;
	esac
done
'
while [ $# -gt 0 ] ; do
	case $1 in
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
	esac
	shift
done
# need long arguments for additional flags for:
# Start-i, end-i, filearray, dataarray, connarray, threadarray

# KMASTER=kubernetes master node, assumed the client is run also here in cluster
# TODO tee ehk CLIENT ja SERVERBARE viel jos ne saattais erota jossain vaiheessa. samat ny
# Tarvis muuttujan jossa ei oo root@ tai ubuntu@ tuota bare metal yhistyst varten
KMASTER=ubuntu@192.168.1.112
CLIENTBARE=ubuntu@192.168.1.111
CLIENT=ubuntu@192.168.1.111
SERVER=ubuntu@192.168.1.113
SERVER_ADDR=192.168.1.113
# Nokia servers are root so they give errors if using sudo
SUDO=sudo
# VMA and Freeflow specific
VMA_COMMAND=
FF=
if [ "$RASPI" == 0 ]
then
	# Nokia hi perf servers
	KMASTER=root@10.37.215.9
	CLIENT=root@10.37.215.9
	CLIENTBARE=root@10.37.215.9
	SERVER=root@10.37.215.10
	SERVER_ADDR=10.37.215.10
	SUDO=
fi

if [ "$LOCAL" == 1 ]
then
	if [ "$RASPI" == 0 ]
	then
		CLIENT=root@10.37.215.10
		CLIENTBARE=root@10.37.215.10
	else
		CLIENT=ubuntu@192.168.1.113
		CLIENTBARE=ubuntu@192.168.1.113
	fi
fi

if [ "$KUBERNETES" != 1 ]
then
	echo Baremetal: remember to manually deploy the server!
fi
if [ "$VMA" == 1 ]
then
	echo VMA enabled
	VMA_COMMAND=LD_PRELOAD=libvma.so
fi
if [ "$FREEFLOW" == 1 ]
then
	echo Freeflow Enabled
	FF=-ff
fi

#CPU_ADDRESS=192.168.1.113
# Selitys alemmasta: Bash suorittaa variablet jos ne on " quoteissa. single quoteissa ei. Me escapattiin awkin kohdalla siis tää toiminta koska kaikki tossa käyttää singlequoteja jo ja halutaan helposti tuplaquote ympärille... (Suoritetaan $2 jne vasta kohteessa)
CPUCOMMAND="for i in {1.."$TIME"}; do top -b -d1 -n1 | grep -i 'Cpu(s)'| awk '"'{print $2, $4, $8, $10, $12, $14, $16}'"'; sleep 1; done"

SOCKPERF_SERVERIP=
if [ "$SOCKPERF" == 0 ] && [ "$IPERF" == 0 ]
then
	echo - wrk benchmark -
	# Move lua script to the machine
	if [ "$KUBERNETES" -gt 0 ]
	then
		echo Remember to check that the requested binary files exist in the server!
		#scp /home/markus/SharedVB/automation/wrk-scripts/wrk-script.lua ${CLIENT}:~
		# TODO! windows versio, modaa kun virtualbox taas toimii
		scp "/c/Users/mteivo/OneDrive - Nokia/VBox-Shared/automation/wrk-scripts/wrk-script.lua" ${CLIENT}:~
		ssh ${CLIENT} ${SUDO} mv wrk-script.lua /var/local/wrktest/
	fi
	if [ "$KUBERNETES" != 1 ]
	then
		echo Bare-metal to ${SERVER_ADDR}
		# TODO! this is windows versio for this!
		#scp /home/markus/SharedVB/automation/wrk-scripts/wrk-script.lua ${CLIENTBARE}:~
		scp "/c/Users/mteivo/OneDrive - Nokia/VBox-Shared/automation/wrk-scripts/wrk-script.lua" ${CLIENTBARE}:~
		ssh ${CLIENTBARE} ${SUDO} mv wrk-script.lua /var/local/wrktest/
	fi
elif [ "$SOCKPERF" == 1 ]
then
	echo - sockperf benchmark -
	# Get the Kube cluster ip of server
	if [ "$KUBERNETES" -gt 0 ]
	then
		SOCKPERF_SERVERIP=$(ssh ${KMASTER} "${SUDO}"' kubectl get services/sockperf'"${FF}"'-service -o go-template='\''{{(.spec.clusterIP)}}'\')
		[ -z "$SOCKPERF_SERVERIP" ] && echo Try again.. && exit 1
	fi
fi


#for CONNECTIONS in "${conn_array[@]}"
for iter in $(seq $I_START $I_END);
#for BINFILE in "${file_array[@]}"
do
	i=("$iter"-1)
	if [ "$USE_CONNARR" == 1 ]
	then
		CONNECTIONS=${conn_array[i]}
	fi
	if [ "$USE_THREADARR" == 1 ]
	then
		THREADS=${thread_array[i]}
	fi
	if [ "$USE_FILEARR" == 1 ]
	then
		BINFILE=${file_array[i]}
	fi
	if [ "$USE_DATAARR" == 1 ]
	then
		DATASIZE=${data_array[i]}
		DATASIZE_HUMAN=${datasize_humanarr[i]}
	fi

	FILENAME=${FILEPREFX}-${iter}-${CONNECTIONS}c-${THREADS}t-${TIME}s-${BINFILE}
	if [ "$SOCKPERF" == 1 ]
	then
		FILENAME=${FILEPREFX}-${SOCKPERF_RUN}-${iter}-${TIME}s-${DATASIZE_HUMAN}
	elif [ "$IPERF" == 1 ]
	then
		FILENAME=${FILEPREFX}-${iter}-10s-${DATASIZE_HUMAN}
	fi

	echo ${FILENAME}: ${CLIENT} "->" ${SERVER}

	if [ "$KUBERNETES" -gt 0 ]
	then
		echo Kubernetes run
		if [ "$SOCKPERF" == 0 ] && [ "$IPERF" == 0 ]
		then
			if [ "$FREEFLOW" == 0 ]
			then
				ssh ${KMASTER} ${SUDO} kubectl exec --stdin wrk${FF}-bench -- wrk -c ${CONNECTIONS} -d ${TIME}s -t ${THREADS} -s /var/local/wrktest/wrk-script.lua http://nginx${FF}-service:100/${BINFILE}.bin > ${FILENAME}-kube &
			else
				ssh ${KMASTER} ${SUDO} kubectl exec --stdin wrk-ff-bench -- ./wrk -c ${CONNECTIONS} -d ${TIME}s -t ${THREADS} -s /var/local/wrktest/wrk-script.lua http://nginx-ff-service:100/${BINFILE}.bin > ${FILENAME}-kube &
			fi
		elif [ "$IPERF" == 1 ]
		then
			ssh ${KMASTER} ${SUDO} kubectl exec --stdin iperf3${FF}-bench -- iperf3 -c iperf3${FF}-service -J -l ${DATASIZE} > ${FILENAME}-kube-json &
		else
			ssh ${KMASTER} ${SUDO} kubectl exec --stdin sockperf${FF}-bench -- sockperf ${SOCKPERF_RUN} --tcp -t ${TIME} --msg-size ${DATASIZE} "${ADDITIONAL_PARAMS}" -i ${SOCKPERF_SERVERIP} > ${FILENAME}-kube &
		fi

		if [ "$CPU" == 1 ]
		then
			# us=userspace sy=system/kernel ni=niced-user/userdefinedprio id=idleops wa=waitdisk/peripheral hi=hardwareint si=softwareint st=steal,involuntaryvirtual-cpuwait (hypervisor servicing another processor)
				# Printataan kaikki paitsi nice. Nice process on siis alhaisemman prioriteetin ja miinukselle mentäessä korkea prio. (Niceä ei ole ellei erikseen user määritä alhaista priota)
			if [ "$LOCAL" == 1 ]
			then
				ssh ${CLIENT} ${CPUCOMMAND} > ${FILENAME}-kube-CPU &
			else
				ssh ${CLIENT} ${CPUCOMMAND} > ${FILENAME}-kube-CPU-client &
				ssh ${SERVER} ${CPUCOMMAND} > ${FILENAME}-kube-CPU-server &
			fi
		fi
		wait
		cat ${FILENAME}-kube | grep ERR
		cat ${FILENAME}-kube | grep dropped
	fi

	if [ "$KUBERNETES" != 1 ]
	then
		echo Baremetal run
		if [ "$SOCKPERF" == 0 ] && [ "$IPERF" == 0 ]
		then
			if [ "$LOCAL" == 1 ]
			then
				if [ "$DOCKER" == 0 ]
				then
					ssh ${CLIENTBARE} wrk/wrk -c ${CONNECTIONS} -d ${TIME}s -t ${THREADS} -s /var/local/wrktest/wrk-script.lua http://localhost:90/${BINFILE}.bin > ${FILENAME}-baremetal &
				else
					ssh ${CLIENTBARE} docker exec wrk wrk -c ${CONNECTIONS} -d ${TIME}s -t ${THREADS} -s /var/local/wrktest/wrk-script.lua http://localhost:90/${BINFILE}.bin > ${FILENAME}-baremetal &
				fi
			else
				if [ "$DOCKER" == 0 ]
				then
					ssh ${CLIENTBARE} wrk/wrk -c ${CONNECTIONS} -d ${TIME}s -t ${THREADS} -s /var/local/wrktest/wrk-script.lua http://${SERVER_ADDR}:90/${BINFILE}.bin > ${FILENAME}-baremetal &
				else
					ssh ${CLIENTBARE} docker exec wrk wrk -c ${CONNECTIONS} -d ${TIME}s -t ${THREADS} -s /var/local/wrktest/wrk-script.lua http://${SERVER_ADDR}:90/${BINFILE}.bin > ${FILENAME}-baremetal &
				fi
			fi
		elif [ "$IPERF" == 1 ]
		then
			if [ "$LOCAL" == 1 ]
			then
				SERVER_ADDR=localhost
			fi
			ssh ${CLIENTBARE} ${VMA_COMMAND} iperf3 -c ${SERVER_ADDR} -J -l ${DATASIZE} > ${FILENAME}-baremetal-json &
		else
			ssh ${CLIENTBARE} ${VMA_COMMAND} sockperf ${SOCKPERF_RUN} --tcp -t ${TIME} --msg-size ${DATASIZE} "${ADDITIONAL_PARAMS}" -i ${SERVER_ADDR} > ${FILENAME}-baremetal &
		fi
		if [ "$CPU" == 1 ]
		then
			if [ "$LOCAL" == 1 ]
			then
				ssh ${CLIENTBARE} ${CPUCOMMAND} > ${FILENAME}-baremetal-CPU &
			else
				ssh ${CLIENTBARE} ${CPUCOMMAND} > ${FILENAME}-baremetal-CPU-client &
				ssh ${SERVER} ${CPUCOMMAND} > ${FILENAME}-baremetal-CPU-server &
			fi
		fi
		wait
		cat ${FILENAME}-baremetal | grep ERR
		cat ${FILENAME}-baremetal | grep dropped
	fi
done


echo done
