# https://fedoramagazine.org/setting-up-a-vm-on-fedora-server-using-cloud-images-and-virt-install-version-3/
# https://fabianlee.org/2020/02/23/kvm-testing-cloud-init-locally-using-kvm-for-an-ubuntu-cloud-image/
#
# REQUIREMENTS
#
# * dnf install virt-install (brings virt-install)
# * dnf install qemu-img     (brings qemu-img)
# * dnf install cloud-utils  (brings cloud-localds)
# 
# * /var/lib/os-images readable by qemu
# 
# * /var/lib/-images/Fedora-Cloud-Base-34-1.2.x86_64.qcow2 is needed
#   simply curl'ed


USAGE="$0 vmname"

# 
RELEASEVER=34
SUBRELEASEVER=1.2

BOOT=/var/lib/libvirt/boot
DIR=/var/lib/os-images


# set in main
VMNAME="" 

DISK_SIZE=10G


function check_name() {
    if virsh domid "${VMNAME}" >& /dev/null; then
        echo "${VMNAME}" already running - killing
        virsh destroy ${VMNAME}
	virsh undefine ${VMNAME}
    fi
}

function prepare() {
  echo PREPARED    
}

function install() {
#        --network bridge=nm-bridge
#        --location=http://fedora-serv.inria.fr/miroirs/fedora/34/Everything/x86_64/iso/Fedora-Everything-netinst-x86_64-34-1.2.iso \
#        --extra-args console=ttyS0 \

    local upstream_image=Fedora-Cloud-Base-34-1.2.x86_64.qcow2
    local vm_image=${DIR}/${VMNAME}.qcow2
    
    [ -f ${vm_image} ] && {
	echo ${vm_image} exists - SHOULD BE aborting
	# return
    }
    #cp ${BOOT}/${upstream_image} ${vm_image}
    qemu-img create -f qcow2 -F qcow2 -b ${BOOT}/${upstream_image} ${vm_image} ${DISK_SIZE}

    # seed image
    local seed=${DIR}/${VMNAME}-seed.raw
    # xxx 2 manual files here
    cloud-localds -v --network-config=network-data.yaml ${seed} user-data.yaml meta-data.yaml

# 	    --network type=direct,source=eth0,source_mode=bridge,model=virtio,mac=52:54:00:00:00:00 \
#        --network bridge=virbr0,model=virtio \
#         --cloud-init meta-data=${DIR}/meta-data.yaml,user-data=${DIR}/user-data.yaml \

    virt-install --name=${VMNAME} \
        --graphics=none \
        --console pty,target_type=serial \
        --ram=4096 \
        --os-variant=fedora${RELEASEVER} \
        --network network=default \
	    --import \
        --disk path=${seed},device=cdrom \
	    --disk path=${vm_image},format=qcow2 \
        --debug \

}

function main() {
    VMNAME="$1"; shift
    check_name
    prepare
    install
}

main "$@"
