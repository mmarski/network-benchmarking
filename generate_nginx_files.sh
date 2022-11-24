#!/bin/bash
# Adds 1B, 1kB, 1MB and more files to Nginx server

#Options
raspi=1
freeflow=0
# Could use just "r" or ":r", latter to ignore invalid argument, to just supply -r or other letter
while getopts "r:f:" flag
do
	case "${flag}" in
		r) raspi=${OPTARG};;
        f) freeflow=${OPTARG};;
	esac
done

# Get Nginx pods
server=ubuntu@192.168.1.112
SUDO=sudo
if [ "$raspi" == 0 ]
then
	server=root@10.37.215.9
    SUDO=
fi
NGINX_PODS=
if [ "$freeflow" == 0 ]
then
    NGINX_PODS=$(ssh ${server} "${SUDO}"' kubectl get pods -o go-template --template '\''{{range .items}}{{.metadata.name}}{{"\n"}}{{end}}'\'' | grep nginx-test')
else
    NGINX_PODS=$(ssh ${server} "${SUDO}"' kubectl get pods -o go-template --template '\''{{range .items}}{{.metadata.name}}{{"\n"}}{{end}}'\'' | grep nginx-ff')
fi


a=(${NGINX_PODS//'\n'/ })
#a=$NGINX_PODS | tr '\n' ' '
echo $a
# Should be able to for loop NGINX_POD if there are multiple servers
for NGINX_POD in "${a[@]}"
do
    echo $NGINX_POD
    ssh ${server} ${SUDO} kubectl exec --stdin $NGINX_POD -- sh -c '"\
    dd if=/dev/zero of=/usr/share/nginx/html/1B.bin bs=1 count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/64B.bin bs=64 count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/512B.bin bs=512 count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/1472B.bin bs=1472 count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/1kB.bin bs=1k count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/2kB.bin bs=2k count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/4kB.bin bs=4k count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/32kB.bin bs=32k count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/64kB.bin bs=64k count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/128kB.bin bs=128k count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/256kB.bin bs=256k count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/512kB.bin bs=512k count=1 && \
    dd if=/dev/zero of=/usr/share/nginx/html/1M.bin bs=1M count=1"'
done
