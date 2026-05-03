#!/usr/bin/env python3
"""
SDN Controller - Ryu OpenFlow 1.3
Machine : mininet@mininet-vm
"""
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet
from ryu.lib import hub
import logging

LOG = logging.getLogger('CloudSDN')

class CloudSDNController(app_manager.RyuApp):
    """
    Controleur SDN avec :
    - MAC Learning (L2 Switch)
    - Installation automatique des flows
    - Monitoring des statistiques
    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}   # Table MAC learning
        self.datapaths   = {}   # Switches connectes
        # Thread monitoring (toutes les 10 secondes)
        self.monitor_thread = hub.spawn(self._monitor_loop)
        LOG.info("=" * 40)
        LOG.info("  Cloud SDN Controller Started !")
        LOG.info("=" * 40)

    # ── Connexion d'un switch ─────────────────────
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        dp = ev.msg.datapath
        self.datapaths[dp.id] = dp
        LOG.info(f"[+] Switch connecte : dpid={dp.id}")
        self._install_table_miss(dp)

    def _install_table_miss(self, dp):
        """Envoyer tous les paquets inconnus au controleur"""
        ofp    = dp.ofproto
        parser = dp.ofproto_parser
        match  = parser.OFPMatch()
        actions = [parser.OFPActionOutput(
            ofp.OFPP_CONTROLLER,
            ofp.OFPCML_NO_BUFFER
        )]
        self._add_flow(dp, 0, match, actions)
        LOG.info(f"[+] Table-miss flow installe sur switch {dp.id}")

    # ── Reception des paquets ─────────────────────
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg     = ev.msg
        dp      = msg.datapath
        ofp     = dp.ofproto
        parser  = dp.ofproto_parser
        in_port = msg.match['in_port']
        dpid    = dp.id

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        if not eth:
            return

        # MAC Learning
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][eth.src] = in_port

        # Trouver le port de sortie
        if eth.dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][eth.dst]
        else:
            out_port = ofp.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Installer un flow si port connu
        if out_port != ofp.OFPP_FLOOD:
            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=eth.dst
            )
            self._add_flow(dp, 1, match, actions, idle_timeout=30)

        # Envoyer le paquet
        data = msg.data if msg.buffer_id == ofp.OFP_NO_BUFFER else None
        dp.send_msg(parser.OFPPacketOut(
            datapath=dp,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        ))

    # ── Ajouter un flow ───────────────────────────
    def _add_flow(self, dp, priority, match, actions,
                  idle_timeout=0, hard_timeout=0):
        ofp    = dp.ofproto
        parser = dp.ofproto_parser
        inst   = [parser.OFPInstructionActions(
            ofp.OFPIT_APPLY_ACTIONS, actions
        )]
        dp.send_msg(parser.OFPFlowMod(
            datapath=dp,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout
        ))

    # ── Monitoring ────────────────────────────────
    def _monitor_loop(self):
        """Thread : demande les stats toutes les 10s"""
        while True:
            for dp in self.datapaths.values():
                parser = dp.ofproto_parser
                req    = parser.OFPFlowStatsRequest(dp)
                dp.send_msg(req)
            hub.sleep(10)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_handler(self, ev):
        dpid  = ev.msg.datapath.id
        flows = len(ev.msg.body)
        LOG.info(f"[STATS] Switch {dpid} : {flows} flows actifs")
        for flow in ev.msg.body:
            if flow.priority > 0:
                LOG.info(
                    f"       priority={flow.priority} "
                    f"packets={flow.packet_count} "
                    f"bytes={flow.byte_count}"
                )
