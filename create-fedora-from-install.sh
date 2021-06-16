# https://www.golinuxcloud.com/virt-install-examples-kvm-virt-commands-linux/
# https://fedoramagazine.org/setting-up-a-vm-on-fedora-server-using-cloud-images-and-virt-install-version-3/

USAGE="$0 vmname"

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
#        --network bridge=nm-bridge
#        --location=http://fedora-serv.inria.fr/miroirs/fedora/34/Everything/x86_64/iso/Fedora-Everything-netinst-x86_64-34-1.2.iso \

    virt-install --name=$VMNAME \
        --graphics=none \
        --extra-args console=ttyS0 \
        --ram=4096 \
        --disk size=10 \
        --network network=default \
        --os-variant=fedora34 \
        --location=/var/lib/os-images/Fedora-Server-dvd-x86_64-34-1.2.iso \

}

function main() {
    VMNAME=$1; shift
    check_name
    install
}

main "$@"
