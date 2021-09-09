#!/bin/bash

#declare -a

# The prefix for the file
FILEPREFX=wrk-connsthreads-local

# For loop params. Use numbers 1-n
I_START=1
I_END=8

# Define values in arrays
conn_array=(1 3 4 5 8 8 10 10)
USE_CONNARR=1
thread_array=(1 3 4 5 2 4 2 5)
USE_THREADARR=1
file_array=(1kB 256kB 512kB)
USE_FILEARR=0

# Or just once
CONNECTIONS=1
THREADS=1
TIME=180
BINFILE=1B

#TODO run in raspi or nokia servers
RASPI=1
# Run Bare-metal or in Kubernetes, or both (0,1,2)
KUBERNETES=1
#Perform CPU measurements. both client and server
CPU=1
# Local run
LOCAL=1

# KMASTER=kubernetes master node, assumed the client is run also here in cluster
# TODO tee ehk CLIENT ja SERVERBARE viel jos ne saattais erota jossain vaiheessa. samat ny
# Tarvis muuttujan jossa ei oo root@ tai ubuntu@ tuota bare metal yhistyst varten
KMASTER=ubuntu@192.168.1.112
CLIENTBARE=ubuntu@192.168.1.111
CLIENT=ubuntu@192.168.1.112
SERVER=ubuntu@192.168.1.113
if [ "$RASPI" == 0 ]
then
	# TODO aseta oikeiksi kun selvil
	KMASTER=root@10.27.7.244
	CLIENTBARE=root@10.27.7.246
	SERVER=root@10.27.7.244
fi

if [ "$LOCAL" == 1 ]
then
	CLIENT=ubuntu@192.168.1.113
fi

#CPU_ADDRESS=192.168.1.113
# Selitys alemmasta: Bash suorittaa variablet jos ne on " quoteissa. single quoteissa ei. Me escapattiin awkin kohdalla siis tää toiminta koska kaikki tossa käyttää singlequoteja jo ja halutaan helposti tuplaquote ympärille... (Suoritetaan $2 jne vasta kohteessa)
CPUCOMMAND="for i in {1.."$TIME"}; do top -b -d1 -n1 | grep -i 'Cpu(s)'| awk '"'{print $2, $4, $8, $10, $12, $14, $16}'"'; sleep 1; done"

echo - wrk benchmark -

# Move lua script to the machine
if [ "$KUBERNETES" -gt 0 ]
then
	echo Remember to check that the requested binary files exist in the server!
	#scp /home/markus/SharedVB/automation/wrk-scripts/wrk-script.lua ${CLIENT}:~
	# TODO! windows versio, modaa kun virtualbox taas toimii
	scp /c/Users/mteivo/Documents/VBox-Shared/automation/wrk-scripts/wrk-script.lua ${CLIENT}:~
	ssh ${CLIENT} sudo mv wrk-script.lua /var/local/wrktest/
fi
if [ "$KUBERNETES" != 1 ]
then
	echo Bare-metal to Raspi3
	# TODO! windows versio for this!
	#scp /home/markus/SharedVB/automation/wrk-scripts/wrk-script.lua ${CLIENTBARE}:~
	scp /c/Users/mteivo/Documents/VBox-Shared/automation/wrk-scripts/wrk-script.lua ${CLIENTBARE}:~
	ssh ${CLIENTBARE} sudo mv wrk-script.lua /var/local/wrktest/
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

	echo Iteration "$iter": $CONNECTIONS connections $THREADS threads $BINFILE file running $TIME s: ${CLIENT} "->" ${SERVER}

	FILENAME=${FILEPREFX}-${CONNECTIONS}c-${THREADS}t-${TIME}s-${BINFILE}-${iter}

	# Jos ei toimi ni lisäsin & merkit ja if CPU setit just
	if [ "$KUBERNETES" -gt 0 ]
	then
		echo Kubernetes run
		ssh ${KMASTER} sudo kubectl exec --stdin wrk-bench -- wrk -c ${CONNECTIONS} -d ${TIME}s -t ${THREADS} -s /var/local/wrktest/wrk-script.lua http://nginx-service:100/${BINFILE}.bin > ${FILENAME} &
		if [ "$CPU" == 1 ]
		then
			# us=userspace sy=system/kernel ni=niced-user/userdefinedprio id=idleops wa=waitdisk/peripheral hi=hardwareint si=softwareint st=steal,involuntaryvirtual-cpuwait (hypervisor servicing another processor)
				# Printataan kaikki paitsi nice. Nice process on siis alhaisemman prioriteetin ja miinukselle mentäessä korkea prio. (Niceä ei ole ellei erikseen user määritä alhaista priota)
			if [ "$LOCAL" == 1 ]
			then
				ssh ${CLIENT} ${CPUCOMMAND} > ${FILENAME}-CPU &
			else
				ssh ${CLIENT} ${CPUCOMMAND} > ${FILENAME}-CPU-client &
				ssh ${SERVER} ${CPUCOMMAND} > ${FILENAME}-CPU-server &
			fi
		fi
	fi
	wait
	if [ "$KUBERNETES" != 1 ]
	then
		echo Baremetal run
		ssh ${CLIENTBARE} wrk/wrk -c ${CONNECTIONS} -d ${TIME}s -t ${THREADS} -s /var/local/wrktest/wrk-script.lua http://192.168.1.113:90/${BINFILE}.bin > ${FILENAME}-baremetal &
		if [ "$CPU" == 1 ]
		then
			ssh ${CLIENTBARE} ${CPUCOMMAND} > ${FILENAME}-baremetal-CPU-client &
			ssh ${SERVER} ${CPUCOMMAND} > ${FILENAME}-baremetal-CPU-server &
		fi
	fi
	wait
done


echo done
