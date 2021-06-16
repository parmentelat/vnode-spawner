# https://www.golinuxcloud.com/virt-install-examples-kvm-virt-commands-linux/

# REQUIREMENTS:
#
# * $BOOT and $DIR readable by qemu
# * $DIR writable by the id that runs this command
# 
# * $BOOT/Fedora-Server-dvd-x86_64-34-1.2.iso is needed
#   simply curl'ed
#
# CONs
# need to finish the installation manually
#
# POSSIBLE IMPROVEMENTS
# use kickstart

USAGE="$0 vmname"

# 
RELEASEVER=34
SUBRELEASEVER=1.2

BOOT=/var/lib/libvirt/boot
DIR=/var/lib/os-images

# set in main
VMNAME="" 

function check_name() {
    if virsh domid "$VMNAME" >& /dev/null; then
        echo "$VMNAME" already running - killing
        virsh destroy $VMNAME
	virsh undefine $VMNAME
    fi
}

function install() {

    local iso=Fedora-Server-dvd-x86_64-${RELEASEVER}-${SUBRELEASEVER}.iso

    virt-install --name=$VMNAME \
        --graphics=none \
        --extra-args console=ttyS0 \
        --ram=4096 \
        --disk size=10 \
        --network network=default \
        --os-variant=fedora34 \
        --location=$BOOT/$iso \

}

function main() {
    VMNAME=$1; shift
    check_name
    install
}

main "$@"
