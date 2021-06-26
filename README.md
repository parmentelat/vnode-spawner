# purpose

A tool to kick-off fresh VMs under virsh/qemu; typically you would arrange for a pool of names (e.g. `vnode00` .. `vnode30`)

Each VM will have 2 IP addresses

* one **private** on the libvirt default network (192.168.122.xx/24)
* one **public** in the public address space (externally assigned by DHCP, expected to be
  configured accordingly, based on MAC addresses, see below)

Installations are done in parallel; the tool waits for all nodes to be ssh-reachable (on the private address space)

## usage

basically you would invoke this tool with e.g.

```
vnode.py 3:f33 vnode4 vnode18:u18.04 20:u20.04
```

explanation:

* this would create 4 VMs
  * vnode03 on fedora33
  * vnode04 on the latest fedora (the default)
  * vnode18 on ubuntu-18.04
  * vnode20 on ubuntu-20.04

* as you can see you can specify just a number or a full name; numbering is normalized
* the default is the latest fedora
* the command runs all installation in parallel, and returns once all the nodes are reachable through ssh

## naming

by default the guests are created under names like `vnode12`

you can easily define several disjoint pools of names with different prefixes (called stems in the code)

## networking

we want

* the guests to have full IP connectivity on a public address
* incuding to the host public IP and sibling guests (i.e. running in the same host)

### dhcp/dns

the guest names are supposed to be defined in the DNS/DHCP space, which gives you all flexibility to define addresses, gateways and dns servers information (as opposed to having to mess with the network template)

### first simplest idea

this can **lamost** be achieved using (as a virt-install option)
```
--network type=direct,source=eth0
```
**BUT** in that scenario the guest won't be able to ping the host, or the sibling guests because in that case the packet goes out on `eth0` and the switch won't send it back to the same originating MAC address...

### hence the bridge

so one way forward is to create a local bridge `br0` and attach `eth0` to that bridge

the one-time confiuration can be done by running the `first-time-create-br0.sh` script

**please be patient** because this involves `NetworkManager` and `nmcli`, and it takes some tens of seconds to settle, and during that time the host remains unreachable from he outside, of course

### todo

it could make sense to run that script automatically if `br0` is not defined

## DHCP


## dhcp

it is not always feasible to
