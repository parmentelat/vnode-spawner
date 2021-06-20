#!/usr/bin/env python

# * dnf install virt-install (brings virt-install)
# * dnf install qemu-img     (brings qemu-img)
# * dnf install cloud-utils  (brings cloud-localds)
#
# * pip install jinja2
#
# * /var/lib/os-images readable by qemu
#
# * /var/lib/libvirt/boot/Fedora-Cloud-Base-34-1.2.x86_64.qcow2 is needed
#   simply curl'ed

import logging
import sys

from pathlib import Path
import subprocess as sp
from dataclasses import dataclass

from jinja2 import Environment, PackageLoader, select_autoescape

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

BOOT = Path("/var/lib/libvirt/boot")
WORK = Path(__file__).parent

DISK_SIZE = '10G'
RAM_SIZE  = '4096'

@dataclass
class Distro:
    short: str      # e.g. f34
    variant: str    # e.g. fedora-34  for virt-install
    image: str      # e.g. Fedora-Cloud-Base-34-1.2.x86_64.qcow2
    disk_size: str  # e.g. 10G  - the disk size to build

DISTROS = {
    'f34': Distro('f34', 'fedora34', 'Fedora-Cloud-Base-34-1.2.x86_64.qcow2', '10G'),
#    'u20': Distro('u20', 'ubuntu20' ...
}


def shell(*vargs, **kwds):
    return sp.run(*vargs, shell=True, **kwds)


class CloudImage:
    """
    Image("Fedora-Cloud-Base-34-1.2.x86_64.qcow2",
          "fedora", "34", "1.2")
    """
    def __init__(self, filename):
        self.filename = filename

    def boot(self):
        path = BOOT / self.filename
        if not path.exists:
            raise FileNotFoundError(str(path))
        return path

    def clone(self, vnode):
        filename = str(vnode)
        return WORK / f"{filename}.qcow2"

    def create_clone(self, vnode, disk_size):
        boot = self.boot()
        clone = self.clone(vnode)
        logging.info(f"Creating snapshot of {boot} into {clone}")
        shell(
            f"qemu-img create -f qcow2 -F qcow2 -b {boot} {clone} {disk_size}")
        return clone


class Vnode:
    """
    Vnode(10)
    Vnode('10')
    Vnode('vnode10')
    Vnode(12, stem='vbox')
    Vnode('vbox12', stem='vbox')
    """
    def __init__(self, id, *, stem="vnode", width=2):
        self.stem = stem
        self.width = width
        #
        self._id = int(str(id).replace(self.stem, ""))
        #
        self.env = Environment(
            loader=PackageLoader("vnode"),
            autoescape = select_autoescape())

    @property
    def id(self):
        return f"{self._id:0{self.width}}"

    def __repr__(self):
        return f"{self.stem}{self.id}"

    @property
    def config_dir(self):
        return Path(__file__).parent / "configs"


    def config_file(self, config_name):
        return self.config_dir / f"{self}-{config_name}"

    def create_config_content(self, config_name):
        vars = dict(
            vnode=repr(self),
            id=self.id,
        )
        template = self.env.get_template(config_name)
        return template.render(**vars) + "\n"

    def create_config_file(self, config_name):
        config_file = self.config_file(config_name)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with config_file.open('w') as writer:
            writer.write(self.create_config_content(config_name))
        return config_file


    def clear_previous_instance(self):
        cp = shell(f"virsh domid {self}", stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        if cp.returncode == 0:
            logging.info(f"killing {self}")
            cp = shell(f"virsh destroy {self}")

        cp = shell(f"virsh undefine {self}", stdout=sp.DEVNULL, stderr=sp.DEVNULL)


    def seed(self):
        return WORK / f"{self}.config.iso"

    def create_seed(self):
        for yaml in 'meta.yaml', 'user.yaml', 'network.yaml':
            self.create_config_file(yaml)
        seed = self.seed()
        cp = shell(
            f"cloud-localds -v --network-config={self.config_file('network.yaml')} "
            f"{seed} {self.config_file('user.yaml')} {self.config_file('meta.yaml')}"
        )
        return seed

    def install(self, distroname):
        self.clear_previous_instance()
        seed = self.create_seed()
        distro = DISTROS[distroname]
        cloud_image = CloudImage(distro.image)
        clone = cloud_image.create_clone(self, distro.disk_size)
        cp = shell(
            f"virt-install --name={self}"
            f" --graphics=none --console pty,target_type=serial"
            f" --ram={RAM_SIZE}"
            f" --network network=default"
            f" --network type=direct,source=eth0,source_mode=bridge,model=virtio,"
                 f"mac=52:54:00:00:00:{self.id}"
            f" --import"
            f" --disk path={seed},device=cdrom"
            f" --disk path={clone},format=qcow2"
            f" --os-variant=fedora34"
            # --debug
        )
        pass


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--distro', default='f34',
                        choices=list(DISTROS.keys()),
                        help="pick your distribution")
    parser.add_argument('ids', nargs='+',
        help="list of vnodes or ids")
    args = parser.parse_args()
    distroname = args.distro
    for nodeid in args.ids:
        node = Vnode(nodeid)
        node.install(distroname)
