#!/bin/bash

# vnode.py assumes the images to be available under
# /var/lib/libvirt/boot

# this script does the initial fetching

USAGE="$0 [-f]"

DIRNAME=$(dirname $0)
cd $DIRNAME

IMAGES=./images
BOOT=./boot

FORCE=""

while getopts "fh" option; do
    case $option in
	f) FORCE="true";;
	h) echo $USAGE; exit 1;;
	*) echo unknown option $option;;
    esac
done
shift $OPTIND

mkdir -p $BOOT

for url in $IMAGES/*.url; do
  stem=$(basename $url .url)
  boot=$BOOT/${stem}.qcow2
  if [ -f "$boot" -a -n "$FORCE" ]; then
      echo "Force mode: removing old $boot"
      rm $boot
  elif [ -f $boot ]; then
      echo "$boot already exists - ignored (remove first to force download)"
      continue
  fi
  echo fetching $(cat $url)
  curl -L -o $boot $(cat $url)
  ls -l $boot
done
