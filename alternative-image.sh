#!/bin/bash

USAGE="
Usage: $0 distro alternative vnodenn -- the command-s to run in image
"

DIRNAME=$(dirname $0)
cd $DIRNAME

BOOT=./boot/
DISKS=./disks/

function main() {
    local distro="$1"; shift
    local alternative="$1"; shift
    local vnode="$1"; shift

    [[ "$1" == "--" ]] || { echo $USAGE; exit 1; }
    shift

    case $vnode in
        vnode*) ;;
        *) echo $vnode must start with vnode
           exit 1;;
    esac

    if virsh dumpxml $vnode > /dev/null 2>&1 ; then
        echo "$vnode needs to be free !"
        exit 1
    fi

    set -e

    local vnode_disk="$DISKS/${vnode}.qcow2"
    local custom="$BOOT/${distro}-${alternative}.qcow2"

    echo "STEP 1: creating vnode $VNODE"
    vnode.py -d $distro $vnode

    echo "STEP 2: running script" apssh -t $vnode "$@"
    apssh -t $vnode "$@"

    echo "STEP 3: stopping node $vnode"
    virsh destroy $vnode
    virsh undefine $vnode

    echo "STEP 4: overwriting image $custom with ${vnode_disk}"
    mv $vnode_disk $custom

    echo DONE

}

main "$@"
