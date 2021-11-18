#!/usr/bin/env python

# pylint: disable=logging-fstring-interpolation
# pylint: disable=redefined-outer-name
# pylint: disable=missing-function-docstring
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring

from dataclasses import dataclass

@dataclass
class Distro:
    short: str      # e.g. f34
    family: str     # fedora or ubuntu
    os_variant: str # e.g. fedora-34  - for virt-install
    disk_size: str  # e.g. 10G  - the disk size to build

    def image(self, alternative=None):
        return (f"{self.short}-{alternative}.qcow2"
                if alternative
                else f"{self.short}.qcow2")

###
# xxx kube setup on f35 and u21.10 not yet fully working
DEFAULT_DISTRO = 'f34'

# new distros:
# to get a list of supported os-variants:
# dnf update
# osinfo-query os

DISTROS = {
    'f35': Distro('f35', 'fedora', 'fedora34', '6G'),          # fedora35 not available 11/21
    'f34': Distro('f34', 'fedora', 'fedora34', '6G'),
    'f33': Distro('f33',  'fedora', 'fedora33', '6G'),
    'u21.10': Distro('u21.10', 'ubuntu', 'ubuntu20.10', '6G'), # ubuntu21/10 not available 11/21
    'u21.04': Distro('u21.04', 'ubuntu', 'ubuntu20.10', '6G'), # ubuntu21.04 not available 11/21
    'u20.04': Distro('u20.04', 'ubuntu', 'ubuntu20.04', '6G'),
    'u18.04': Distro('u18.04', 'ubuntu', 'ubuntu18.04', '6G'),
}

# see README.md

import logging

import sys
import os, signal
import subprocess as sp

from pathlib import Path

import asyncio
import asyncssh

from jinja2 import Environment, PackageLoader, select_autoescape

WORKROOT = Path(__file__).parent

# paths
BOOT = WORKROOT / "boot"
# xxx probably not quite right

# names and features
STEM = 'vnode'
DISK_SIZE = '10G'
RAM_SIZE  = '4096'

# times
IDLE = 30        # wait that many seconds before trying to ssh
SSH_PERIOD = 5   # how often to retry a ssh
TIMEOUT = 120    # if a node has not come up after that time, it's deemed KO

VERBOSE = True
VERBOSE = False


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
#asyncssh.set_log_level(logging.DEBUG if VERBOSE else logging.INFO)
asyncssh.set_log_level(logging.INFO) if VERBOSE else logging.ERROR

# fetched as PRETTY_NAME in os-release
Pretty = str

def shell(*vargs, **kwds):
    return sp.run(*vargs, shell=True, **kwds)      # pylint: disable=subprocess-run-check


class CloudImage:
    """
    ex. Image("f34.qcow2")
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
        self.pid = None

    @property
    def id(self):                                          # pylint: disable=invalid-name
        return f"{self._id:0{self.width}}"

    def __repr__(self):
        return f"{self.stem}{self.id}"

    def _subdir(self, category):
        result = WORKROOT / category
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
            stem=self.stem,
            vnode=repr(self),
            id=self.id,
            intid=int(self.id),  # if computations are needed
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

    def virt_install(self, distro: Distro, alternative=None) -> str:
        seed = self.create_seed(distro)
        cloud_image = CloudImage(distro.image(alternative))
        clone = cloud_image.create_clone(self, distro.disk_size)
        return (
            f"virt-install --name={self}"
            f" --graphics=none --console pty,target_type=serial"
            f" --ram={RAM_SIZE}"
            f" --network bridge=br0,model=virtio,target=tun{self},"
                 f"mac=52:54:00:00:00:{self.id}"
            f" --import"
            f" --disk path={seed},device=cdrom"
            f" --disk path={clone},format=qcow2"
            f" --os-variant={distro.os_variant}"
            # --debug
        )


    class VirtInstallProtocol(asyncio.SubprocessProtocol):
        """
        The point is is to have the output of virt-install
        logged while the process flows, because
        1. the process won't end up well - it gets killed once
          we have ssh connectivity
        2. it's useful to be able to monitor things on the go
        """
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


    def check_or_clean(self, force):
        """
        check the node does not exist yet, or destroy/undefine it if force is set

        return bool that says it is safe to proceed
        """
        completed = shell(f"virsh domid {self}", stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        if completed.returncode != 0:
            # domain does not exist
            return True
        if not force:
            logging.info(f"domain {self} already exists")
            return False
        # needs cleanup
        stop = shell(f"virsh destroy {self}", stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        stop = shell(f"virsh undefine {self}", stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        return True


    async def a_start_install(self, distro: Distro, alternative=None) -> bool:
        """
        works asynchroneously and redirect output in a file
        """
        command = self.virt_install(distro, alternative)
        logging.debug(f"running {command}")

        loop = asyncio.get_running_loop()

        exit_future = asyncio.Future(loop=loop)

        transport, _protocol = await loop.subprocess_shell(
            lambda: Vnode.VirtInstallProtocol(exit_future, self),
            command,
            stdin=None)
        self.pid = transport._pid

        # Wait for the subprocess exit using the process_exited()
        # method of the protocol.
        try:
            future = await exit_future
        except asyncio.CancelledError as exc:
            logging.info("virt-install task CANCELLED")
        finally:
            # Close the stdout pipe.
            transport.close()

    @staticmethod
    def pretty_name(os_release):
        tag = "PRETTY_NAME="
        for line in os_release.split('\n'):
            if line.startswith(tag):
                return line[len(tag):]
        return "UNKNOWN DISTRO"

    async def a_wait_ssh(self) -> Pretty:
        ip = f"192.168.122.1{self.id}"
        ip = str(self)
        command = "cat /etc/os-release"
        logging.debug(f"{self} idling for {IDLE}s")
        await asyncio.sleep(IDLE)
        while True:
            try:
                # already issued by asyncssh INFO
                # logging.debug(f"trying to ssh into {ip}")
                async with asyncssh.connect(ip, known_hosts=None) as conn:
                    result = await conn.run(command, check=True)
                    pretty = self.pretty_name(result.stdout)
                    logging.info(f"{self} ssh-OK - {pretty}")
                    self.terminate_a_install()
                    return pretty
            except (OSError, asyncssh.Error):
                await asyncio.sleep(SSH_PERIOD)

    # the libvirt process will NEVER finish on its own
    def terminate_a_install(self):
        logging.debug(f'killing libvirt-install {self.pid=}')
        return os.kill(self.pid, signal.SIGTERM)

    async def async_install(self, distro: Distro, force, alternative=None) -> Pretty:
        if not self.check_or_clean(force):
            return "ALREADY RUNNING"
        t_install = asyncio.create_task(self.a_start_install(distro, alternative))
        t_ssh = asyncio.create_task(self.a_wait_ssh())
        done, pending = await asyncio.wait(
            [t_install, t_ssh], timeout=TIMEOUT, return_when=asyncio.FIRST_COMPLETED)
        # as the install never finishes, here we have either
        # done == [t_ssh] : all is fine
        # done == [] : oops
        for task in done:
            # read the exception
            if task.exception():
                pass
        for task in pending:
            task.cancel()
        try:
            return t_ssh.result()
        except:
            return "DOWN"


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

ALTERNATIVES

using alternative-image.sh it is easy to produce and use an image
that is based on the upstream image

EXAMPLE

alternative-image.sh f34 k8s vnode30 -- -s ~/kube-install.sh install install-extras install-helm
  will use vnode30 (must be free) to produce image f34-k8s
  it uses apssh to run stuff inside the node, hence the -s option
vnode.py -d f34-k8s 0 1 2 3
  will spawn four nodes based on that alternative image
"""


def main():
    from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
    parser = ArgumentParser(usage=HELP,
    formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-d', '--distro', default=DEFAULT_DISTRO,
                        #choices=list(DISTROS.keys()),
                        help="pick your distribution")
    parser.add_argument('-f', '--force', default=False, action='store_true',
                        help="already running VM's are not touched, unless"
                             " this option is given, in which case they are"
                             " destroyed and undefined before being re-created")
    parser.add_argument('-v', '--verbose', default=False, action='store_true')
    parser.add_argument('ids', nargs='+',
        help=
            f"list of vnodes or ids; simple ids are prefixed with {STEM};"
            f" the distro can be specified individually"
            f" e.g. vnode00 01 vnode23:f33 24:f34; if not, the -d option applies;")
    args = parser.parse_args()
    if args.verbose:
        global VERBOSE
        VERBOSE = True
    distro_def = args.distro

    nodes = []
    coros = []
    for nodeid in args.ids:
        if ':' in nodeid:
            nodeid, distroname = nodeid.split(':')
        else:
            distroname = distro_def
        nodes.append(node := Vnode(nodeid))
        alternative = None
        s = distroname.split('-', 1)
        if len(s) == 2:
            distroname, alternative = s
        distro = DISTROS[distroname]
        coros.append(node.async_install(distro, args.force, alternative))
    # somehow we can't do just
    # asyncio.run(asyncio.gather(*coros))
    async def bundle():
        results = await asyncio.gather(*coros)
        return results
    results = asyncio.run(bundle())
    logging.info(results)

    # reset the terminal; libvirt tends to leave it in very bad shape
    # unfortunately this is a little intrusive
    if not VERBOSE:
        shell("reset")
    for node, pretty in zip(nodes, results):
        logging.info(f"\rnode {node} -> {pretty}")

if __name__ == '__main__':
    main()
