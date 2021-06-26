BR=br0
IFACE=eth0
read MAC </sys/class/net/$IFACE/address

# create bridge
nmcli con add ifname br0 type bridge con-name $BR
# attach MAC address for dhcp
nmcli con modify br0 bridge.mac-address $MAC
# enable dhcp on br0
nmcli con modify $BR ipv4.method auto


# turn off physical interface
nmcli con down $IFACE
# attach eth0 to bridge
nmcli con add type ethernet ifname eth0 master br0
# turn on bridge
nmcli con up $BR

virsh net-define templates/br0-network.xml
virsh net-start br0-network
virsh net-autostart br0-network