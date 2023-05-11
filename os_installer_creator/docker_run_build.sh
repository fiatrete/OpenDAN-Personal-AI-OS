CONTAINER_NAME=opendan-installer-container

# Restart container to stop chroot env
docker restart ${CONTAINER_NAME}
docker exec -it ${CONTAINER_NAME} sh -c 'mkdir /workspace & wait'
docker exec -it ${CONTAINER_NAME} sh -c 'rm -r /workspace/* & wait'
# Update build scripts
docker cp ./scripts ${CONTAINER_NAME}:/workspace/
docker exec -it ${CONTAINER_NAME} /workspace/scripts/build.sh debootstrap - build_iso
docker cp ${CONTAINER_NAME}:/workspace/scripts/ubuntu-opendan.iso ./images/