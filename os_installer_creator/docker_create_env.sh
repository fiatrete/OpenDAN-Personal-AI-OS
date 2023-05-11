CONTAINER_NAME=opendan-installer-container
docker run -d -it --name ${CONTAINER_NAME} \
--platform=linux/amd64 \
--security-opt apparmor:unconfined --cap-add SYS_ADMIN \
ubuntu:jammy /bin/bash

docker cp ./scripts ${CONTAINER_NAME}:/root/
docker exec -it ${CONTAINER_NAME} sh -c 'apt update && apt install -y lsb-release sudo'
docker exec -it ${CONTAINER_NAME} /root/scripts/build.sh setup_host 