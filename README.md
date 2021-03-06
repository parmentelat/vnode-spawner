

- [target](#target)
- [prerequisites](#prerequisites)
  - [networking](#networking)
  - [packages](#packages)
- [images](#images)
  - [alternative images](#alternative-images)
- [usage](#usage)
- [naming](#naming)
- [networking](#networking-1)
  - [dhcp/dns](#dhcpdns)
  - [first simplest idea](#first-simplest-idea)
  - [hence the bridge](#hence-the-bridge)
- [caveats](#caveats)
  - [console and outputs](#console-and-outputs)
  - [filtering](#filtering)
  - [miscell](#miscell)

A tool to kick-off fresh VMs under virsh/qemu; typically you would arrange for a pool of names (e.g. `vnode00` .. `vnode30`)

Installations are done in parallel; the tool waits for all nodes to be ssh-reachable - or a 2 minute timeout expires

Each node ends up with one **public** IP in the public address space;
this is assumed to be externally configured by DHCP, based on MAC addresses, see below

## target

* host running latest Fedora starting with f34, and using only vanilla tools (NetworkManager
and not network; firewall and not iptables; ...)
* guests running last and one-but-last releases of Fedora and Ubuntu LTS
* parallel installations

## prerequisites

### networking 

see below the section on creating a bridge

### packages

```
dnf -y install libvirt
dnf -y install qemu-kvm
dnf -y install virt-install       # brings virt-install
dnf -y install qemu-img           # brings qemu-img
dnf -y install cloud-utils        # brings cloud-localds

pip install jinja2 asyncssh
systemctl enable --now libvirtd
```

Also the source code must be deployed in a location where the `qemu` uid as read access (so e.g. not under `/root`)

My typical setup is to
```bash
cd /var/lib
git clone git@github.com:parmentelat/vnode-spawner.git
cd /root
ln -s /var/lib/vnode-spawner
```

## images

images - as published by upstream distros - are expected to be pre-fetched
```
cd /var/lib/vnode-spawner
./fetch-images.sh
```

will store in boot/ the qcow2 files as defined in `images/*.url`

### alternative images

xxx to be documented

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
* the command runs all installations in parallel, and returns once all the nodes are reachable through ssh

## naming

by default the guests are created under names like `vnode12`

you can define several disjoint pools of names with different prefixes
(called stems in the code)

## networking

we want

* the guests to have full IP connectivity on a public address
* incuding to the host public IP, and sibling guests (i.e. running in the same host)

### dhcp/dns

the guest names are supposed to be defined in the DNS/DHCP space, which gives
you all flexibility to define addresses, masks, gateways and dns servers
information (as opposed to having to mess with the network template)

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

the one-time configuration can be done by running the `install/create-bridge.sh` script;
check the IFACE variable though

**please be patient** because this involves `NetworkManager` and `nmcli`, and it
takes some tens of seconds to settle, and during that time the host remains
unreachable from he outside, of course

## caveats

quite a few :

### console and outputs

* we want to redirect the console output on the fly; virt-install does not seem to let us
  do that without messing with the terminal; so at the end the code calls the `reset`
  shell command to ensure the terminal is functional again; this however clears the
  screen.

### filtering

* right now we turn off filtering by all bridges in the node using sysctl
  ```
  net.bridge.bridge-nf-call-iptables=0
  net.bridge.bridge-nf-call-arptables=0
  ```
  the latter is no worry as ebtables are empty by default; but the former is obviously
  totally wrong, as ***ALL OUR TRAFFIC*** goes through `br0`; so I take it it effectively
  bypasses firewall rules altogether in this mode.


### miscell

* it could make sense to run that script automatically if `br0` is not defined
* **security**: for now, for the dhcp traffic to go through the bridge,
  we bypass netfilter, which of course is quite wrong; need to better learn firewall-cmd
* **security** again: optionnally assign a constant ssh key to the nodes; right
  now we just ignore the host key when asserting onelineness (which is fine) but
  as a result we keep on wiping them from known_hosts afterwards, and thats
  unconvenient and dangerous; for test deployments a fixed well-known key would
  be **much** better
