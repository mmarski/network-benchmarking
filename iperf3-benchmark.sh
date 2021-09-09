#!/bin/bash

TIME=10

for i in {1..3};
do
	#echo $connections connections running $TIME s
	it=$(expr 2 + $i)
	echo iteration $i running $TIME s
	FILENAME=iperf3-$it
	
	ssh ubuntu@192.168.1.112 sudo kubectl exec --stdin iperf3-bench -- iperf3 -J -c iperf3-service > ${FILENAME}
done


echo done
