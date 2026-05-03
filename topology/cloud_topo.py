#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch, OVSController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time

class CloudTopology:

    def build(self):
        info("*** Creating Cloud Network\n")

        net = Mininet(
            controller=OVSController,
            switch=OVSSwitch,
            link=TCLink,
            autoSetMacs=True
        )

        # Controleur integre OVS
        c0 = net.addController('c0')

        # ── Switches ──────────────────────────────
        core  = net.addSwitch('s1')
        edge1 = net.addSwitch('s2')
        edge2 = net.addSwitch('s3')
        edge3 = net.addSwitch('s4')

        # ── Liens switches ────────────────────────
        net.addLink(core, edge1, bw=1000, delay='1ms')
        net.addLink(core, edge2, bw=1000, delay='1ms')
        net.addLink(core, edge3, bw=1000, delay='1ms')

        # ── Zone Web ──────────────────────────────
        web1 = net.addHost('web1', ip='10.0.0.1/8')
        web2 = net.addHost('web2', ip='10.0.0.2/8')
        lb   = net.addHost('lb',   ip='10.0.0.10/8')

        net.addLink(edge1, web1, bw=100, delay='2ms')
        net.addLink(edge1, web2, bw=100, delay='2ms')
        net.addLink(edge1, lb,   bw=100, delay='1ms')

        # ── Zone Data ─────────────────────────────
        db    = net.addHost('db',    ip='10.0.1.1/8')
        cache = net.addHost('cache', ip='10.0.1.2/8')
        api   = net.addHost('api',   ip='10.0.1.3/8')

        net.addLink(edge2, db,    bw=100, delay='2ms')
        net.addLink(edge2, cache, bw=100, delay='1ms')
        net.addLink(edge2, api,   bw=100, delay='2ms')

        # ── Zone Monitor ──────────────────────────
        monitor = net.addHost('monitor', ip='10.0.2.1/8')
        net.addLink(edge3, monitor, bw=100, delay='2ms')

        return net, c0

    def start(self):
        net, c0 = self.build()

        info("*** Starting Network\n")
        net.start()
        time.sleep(3)

        info("\n========================================\n")
        info("        Cloud Network Ready !           \n")
        info("========================================\n")
        info("Web Zone  : web1(10.0.0.1)              \n")
        info("            web2(10.0.0.2)              \n")
        info("            lb  (10.0.0.10)             \n")
        info("Data Zone : db   (10.0.1.1)             \n")
        info("            cache(10.0.1.2)             \n")
        info("            api  (10.0.1.3)             \n")
        info("Monitor   : monitor(10.0.2.1)           \n")
        info("========================================\n\n")

        info("*** Testing connectivity...\n")
        net.pingAll()

        info("*** Starting CLI\n")
        CLI(net)

        info("*** Stopping Network\n")
        net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    topo = CloudTopology()
    topo.start()
