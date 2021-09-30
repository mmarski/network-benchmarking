#!/bin/bash

# Also zero-copy mode? -Z .. how it works, uses sendfile() method, instead of write()? miten sendfile toimii
TIME=30
BYTES=1

for i in {1..3};
do
	#echo $connections connections running $TIME s
	it=$(expr 2 + $i)
	echo iteration $i running $TIME s
	FILENAME=iperf3-$it
	
	ssh ubuntu@192.168.1.112 sudo kubectl exec --stdin iperf3-bench -- iperf3 -J -t ${TIME} -l ${BYTES} -c iperf3-service > ${FILENAME}
done


echo done
