BR=br0
IFACE=eth0

# fetch the ethernet's MAC
read MAC </sys/class/net/$IFACE/address

# create bridge
nmcli con add ifname $BR type bridge con-name $BR
# attach MAC address to bridge interface for DHCP
nmcli con modify $BR bridge.mac-address $MAC
# allow the host to use DHCP to find its own IP
nmcli con modify $BR ipv4.method auto


# turn off physical interface
nmcli con down $IFACE
# attach ethernet to bridge
nmcli con add type ethernet ifname $IFACE master $BR
# turn on bridge
nmcli con up $BR

# warning - netfilter on bridge is assumed and enforced by k8s
# xxx better to open up stuff in firewall
cat > /etc/sysctl.d/turn-off-nf-bridge.conf << EOF
net.bridge.bridge-nf-call-iptables=0
net.bridge.bridge-nf-call-arptables=0
EOF

systemctl restart systemd-sysctl
