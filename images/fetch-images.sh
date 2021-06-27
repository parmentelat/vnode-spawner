#!/bin/bash

# vnode.py assumes the images to be available under
# /var/lib/libvirt/boot

# this script does the initial fetching

BOOT=/var/lib/libvirt/boot

for url in *.url; do
  stem=$(basename $url .url)
  boot=$BOOT/$stem
  if [ -f $boot ]; then
    echo "$boot already exists - ignored (remove first to force download)"
  else
    curl -o $boot $url
  fi
done
