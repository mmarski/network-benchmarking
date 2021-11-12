#!/bin/bash

# Also zero-copy mode? -Z .. how it works, uses sendfile() method, instead of write()? miten sendfile toimii
TIME=30
BYTES=1

filename_array=(1B 64B 512B 1kB 1472B 2kB 4kB 32kB 64kB 128kB 256kB 512kB 1M)

for i in {1..3};
do
	#echo $connections connections running $TIME s
	it=$(expr 2 + $i)
	echo iteration $i running $TIME s
	FILENAME=iperf-${filename_array[i]}
	
	ssh ubuntu@192.168.1.112 sudo kubectl exec --stdin iperf3-bench -- iperf3 -t ${TIME} -l ${BYTES} -c iperf3-service > ${FILENAME}
	ssh ubuntu@192.168.1.112 sudo kubectl exec --stdin iperf3-bench -- iperf3 -J -t ${TIME} -l ${BYTES} -c iperf3-service > ${FILENAME}-json
done


echo done
