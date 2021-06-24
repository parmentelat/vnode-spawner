#!/usr/bin/env python

# pylint: disable=logging-fstring-interpolation
# pylint: disable=redefined-outer-name
# pylint: disable=missing-function-docstring
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring


# * dnf install virt-install (brings virt-install)
# * dnf install qemu-img     (brings qemu-img)
# * dnf install cloud-utils  (brings cloud-localds)
#
# * pip install jinja2 asyncssh
#
# * /var/lib/os-images readable by qemu
#
# * /var/lib/libvirt/boot/Fedora-Cloud-Base-34-1.2.x86_64.qcow2 is needed
#   simply curl'ed

import sys
import os, signal

import logging
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime as DateTime, timedelta as TimeDelta
import subprocess as sp

import asyncio
import asyncssh

from jinja2 import Environment, PackageLoader, select_autoescape

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
#asyncssh.set_log_level(logging.DEBUG if VERBOSE else logging.INFO)
asyncssh.set_log_level(logging.INFO)

BOOT = Path("/var/lib/libvirt/boot")
WORK = Path(__file__).parent

STEM = 'vnode'
DISK_SIZE = '10G'
RAM_SIZE  = '4096'
SSH_TIMEOUT = 120
SSH_PERIOD = 5
VERBOSE = True

@dataclass
class Distro:
    short: str      # e.g. f34
    family: str     # fedora or ubuntu
    os_variant: str # e.g. fedora-34  - for virt-install
    image: str      # e.g. Fedora-Cloud-Base-34-1.2.x86_64.qcow2
    disk_size: str  # e.g. 10G  - the disk size to build

DISTROS = {
    'f34': Distro('f34', 'fedora', 'fedora34',
                  'Fedora-Cloud-Base-34-1.2.x86_64.qcow2', '6G'),
    'f33': Distro('f33',  'fedora', 'fedora33',
                  'Fedora-Cloud-Base-33-1.2.x86_64.qcow2', '6G'),
    'u20.04': Distro('u20.04', 'ubuntu', 'ubuntu20.04',
                  'focal-server-cloudimg-amd64.img', '6G'),
    'u18.04': Distro('u18.04', 'ubuntu', 'ubuntu18.04',
                  'bionic-server-cloudimg-amd64.img', '6G'),
}


def shell(*vargs, **kwds):
    return sp.run(*vargs, shell=True, **kwds)      # pylint: disable=subprocess-run-check


class CloudImage:
    """
    ex. Image("Fedora-Cloud-Base-34-1.2.x86_64.qcow2")
    """
    def __init__(self, filename):
        self.filename = filename

    def boot(self):
        path = BOOT / self.filename
        if not path.exists:
            raise FileNotFoundError(str(path))
        return path

    def clone(self, vnode: 'Vnode'):
        filename = str(vnode)
        return vnode.disk_dir / f"{filename}.qcow2"

    def create_clone(self, vnode: 'Vnode', disk_size: str):
        boot = self.boot()
        clone = self.clone(vnode)
        logging.info(f"Creating snapshot of {boot} into {clone}")
        shell(
            f"qemu-img create -f qcow2 -F qcow2 -b {boot} {clone} {disk_size}")
        return clone


class Vnode:
    """
    Vnode(10) -> would use name 'vnode10'
    Vnode('10') -> vnode10
    Vnode('vnode10') -> vnode10
    Vnode(12, stem='vbox') -> vbox12
    Vnode('vbox12', stem='vbox', width=3) -> vbox012
    """
    def __init__(self, id_, *, stem=STEM, width=2):
        self.stem = stem
        self.width = width
        #
        self._id = int(str(id_).replace(self.stem, ""))
        #
        self.env = Environment(
            loader=PackageLoader("vnode"),
            autoescape = select_autoescape())

    @property
    def id(self):                                          # pylint: disable=invalid-name
        return f"{self._id:0{self.width}}"

    def __repr__(self):
        return f"{self.stem}{self.id}"

    def _subdir(self, category):
        result = Path(__file__).parent / category
        result.mkdir(parents=True, exist_ok=True)
        return result

    @property
    def config_dir(self):
        return self._subdir("configs")
    @property
    def disk_dir(self):
        return self._subdir("disks")
    @property
    def log_dir(self):
        return self._subdir("logs")

    @property
    def seed(self):
        return self.disk_dir / f"{self}-seed.iso"
    @property
    def log(self):
        return self.log_dir / f"{self}.log"

    def config_file(self, config_name):
        return self.config_dir / f"{self}-{config_name}"

    def create_config_content(self, config_name, distro):
        if distro.family == 'fedora':
            eth0 = 'eth0'
            eth1 = 'eth1'
        elif distro.family == 'ubuntu':
            eth0 = 'enp1s0'
            eth1 = 'enp2s0'
        vars_ = dict(
            vnode=repr(self),
            id=self.id,
            eth0=eth0,
            eth1=eth1,
        )
        template = self.env.get_template(config_name)
        return template.render(**vars_) + "\n"

    def create_config_file(self, config_name, distro):
        config_file = self.config_file(config_name)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with config_file.open('w') as writer:
            writer.write(self.create_config_content(config_name, distro))
        return config_file


    def clear_previous_instance(self):
        completed = shell(f"virsh domid {self}", stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        if completed.returncode == 0:
            command = f"virsh destroy {self}"
            logging.info(f"running {command}")
            completed = shell(command)
        command = f"virsh undefine {self}"
        logging.info(f"running {command}")
        completed = shell(command, stdout=sp.DEVNULL, stderr=sp.DEVNULL)


    def create_seed(self, distro):
        for yaml in 'meta.yaml', 'user.yaml', 'network.yaml':
            self.create_config_file(yaml, distro)
        seed = self.seed
        completed = shell(
            f"cloud-localds -v --network-config={self.config_file('network.yaml')} "
            f"{seed} {self.config_file('user.yaml')} {self.config_file('meta.yaml')}"
        )
        if completed.returncode != 0:
            logging.warning("cloud-localds failed")
        return seed

    def virt_install(self, distro: Distro) -> str:
        self.clear_previous_instance()
        seed = self.create_seed(distro)
        cloud_image = CloudImage(distro.image)
        clone = cloud_image.create_clone(self, distro.disk_size)
        return (
            f"virt-install --name={self}"
            f" --graphics=none --console pty,target_type=serial"
#            f" --serial file,path={self.log}"
            f" --ram={RAM_SIZE}"
            f" --network network=default"
            f" --network type=direct,source=br0,source_mode=bridge,model=virtio,"
                 f"mac=52:54:00:00:00:{self.id}"
            f" --import"
            f" --disk path={seed},device=cdrom"
            f" --disk path={clone},format=qcow2"
            f" --os-variant={distro.os_variant}"
            # --debug
        )

    # def sync_install(self, distro: Distro) -> bool:
    #     """
    #     works synchroneously and displays output in logs/vnodexx.log
    #     """
    #     completed = shell(self.virt_install(distro))
    #     return completed.returncode == 0

    # async version

    class VirtInstallProtocol(asyncio.SubprocessProtocol):
        def __init__(self, exit_future, vnode):
            self.exit_future = exit_future
            self.vnode = vnode
            self.path = vnode.log
            self.path.exists() and self.path.unlink() # pylint: disable=expression-not-assigned


        def pipe_data_received(self, fd, data):
            # print(f"[{fd}]", end='')
            with self.path.open('ab') as out:
                out.write(data)

        def process_exited(self):
            self.exit_future.set_result(True)

    async def a_start_install(self, distro: Distro) -> bool:
        """
        works asynchroneously and redirect output in a file
        """
        command = self.virt_install(distro)
        if VERBOSE:
            print(command)

        loop = asyncio.get_running_loop()

        exit_future = asyncio.Future(loop=loop)

        transport, _protocol = await loop.subprocess_shell(
            lambda: Vnode.VirtInstallProtocol(exit_future, self),
            command,
            stdin=None)
        self.pid = transport._pid

        # Wait for the subprocess exit using the process_exited()
        # method of the protocol.
        future = await exit_future

        # Close the stdout pipe.
        transport.close()

        print(f"async install done with {future=}")

    async def a_wait_ssh(self):
        ip = f"192.168.122.1{self.id}"
        command = "cat /etc/os-release"
        start = DateTime.now()
        while True:
            try:
                if VERBOSE:
                    print(f"trying to ssh into {ip}")
                async with asyncssh.connect(ip) as conn:
                    result = await conn.run(command, check=True)
                    logger.info(f"{self} ssh-OK")
                    logger.debug(result.stdout)
                    return True
            except (OSError, asyncssh.Error) as exc:
                await asyncio.sleep(SSH_PERIOD)
                if DateTime.now() - start >= TimeDelta(seconds=SSH_TIMEOUT):
                    return False

    def terminate_a_install(self):
        if VERBOSE:
            print(f'killing libvirt-install {self.pid=}')
        return os.kill(self.pid, signal.SIGTERM)

    async def async_install(self, distro: Distro) -> bool:
        tasks = [
            asyncio.create_task(self.a_start_install(distro)),
            asyncio.create_task(self.a_wait_ssh()),
        ]
        await asyncio.wait(tasks, timeout=SSH_TIMEOUT)
        # cleanup
        self.terminate_a_install()



HELP = f"""
provision a fresh node under QEMU; the node is picked among a pool of nodes
names ranging from {STEM}00 and up

any pre-existing instance is first terminated

one invokation can produce several nodes, each with its separate distro

REQUIREMENTS

a node numbered e.g. 99 will use MAC address 52:54:00:00:00:99;
as of now, the node names should be known to your DNS+DHCP environment;

EXAMPLE

vnode.py 18:u18.04 20:u20.04 23:f33 24:f34
or with exact same result
vnode.py vnode18:u18.04 vnode20:u20.04 vnode23:f33 vnode24:f34
"""


if __name__ == '__main__':
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
    parser = ArgumentParser(usage=HELP,
    formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--distro', default='f34',
                        choices=list(DISTROS.keys()),
                        help="pick your distribution")
    parser.add_argument('ids', nargs='+',
        help=
            "list of vnodes or ids; simple ids are prefixed with {STEM};"
            " the distro can be specified individually"
            " e.g. vnode00 01 vnode23:f33 24:f34; if not, the -d option applies;")
    args = parser.parse_args()
    distro_def = args.distro

    tasks = []
    for nodeid in args.ids:
        if ':' in nodeid:
            nodeid, distroname = nodeid.split(':')
        else:
            distroname = distro_def
        node = Vnode(nodeid)
        distro = DISTROS[distroname]
        tasks.append(node.async_install(distro))
    asyncio.run(asyncio.wait(tasks))
