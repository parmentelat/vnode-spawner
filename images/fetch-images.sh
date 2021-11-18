#!/bin/bash

# vnode.py assumes the images to be available under
# /var/lib/libvirt/boot

# this script does the initial fetching

USAGE="$0 [-f]"

DIRNAME=$(dirname $0)
cd $DIRNAME

BOOT=../boot

FORCE=""

while getopts "fh" option; do
    case $option in
	f) FORCE="true";;
	h) echo $USAGE; exit 1;;
	*) echo unknown option $option;;
    esac
done
shift $OPTIND

for url in *.url; do
  stem=$(basename $url .url)
  boot=$BOOT/$stem
  if [ -f $boot -a -n "$FORCE" ]; then
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
