# purpose

A tool to kick-off fresh VMs under virsh/qemu; typically you would arrange for a pool of names (e.g. `vnode00` .. `vnode30`)

Installations are done in parallel; the tool waits for all nodes to be ssh-reachable - or a 2 minute timeout expires

Each node ends up with one **public** in the public address space;
this is assumed to externally configured by DHCP, based on MAC addresses, see below

## target

* host running latest Fedora starting with f34, and using only vanilla tools (NetworkManager
and not network; firewall and not iptables; ...)
* guests running last and one-but-last releases of Fedora and Ubuntu LTS
* parallel installations

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

you can define several disjoint pools of names with different prefixes
(called stems in the code)

## networking

we want

* the guests to have full IP connectivity on a public address
* incuding to the host public IP, and sibling guests (i.e. running in the same host)

### dhcp/dns

the guest names are supposed to be defined in the DNS/DHCP space, which gives you all
flexibility to define addresses, masks, gateways and dns servers information (as opposed to
having to mess with the network template)

for now the MAC address is hard-wired in the Python module as being 52:54:00:00:00:nn

### first simplest idea

this can **lamost** be achieved using (as a virt-install option)
```
--network type=direct,source=eth0
```
**BUT** in that scenario the guest won't be able to ping the host, or the sibling guests
because in that case the packet goes out on `eth0` and the switch won't send it back to
the same originating MAC address...

### hence the bridge

so one way forward is to create a local bridge `br0` and attach `eth0` to that bridge

the one-time configuration can be done by running the `first-time-create-br0.sh` script

**please be patient** because this involves `NetworkManager` and `nmcli`, and it takes
some tens of seconds to settle, and during that time the host remains unreachable from he
outside, of course

### todo

* it could make sense to run that script automatically if `br0` is not defined
* **security**: for now, for the dhcp traffic to go through the bridge,
  we bypass netfilter, which of course is quite wrong; need to better learn firewall-cmd
* **security** again: optionnall assign a constant ssh key to the nodes; right now we just
  ignore the host key when asserting onelineness (which is fine) but as a result we keep
  on wiping them from known_hosts afterwards, and thats unconvenient and dangerous; for
  test deployments a fixed well-known key would be **much** better imo
