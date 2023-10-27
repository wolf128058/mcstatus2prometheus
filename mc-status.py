#!/usr/bin/env python3

import argparse
import time
from mcstatus import JavaServer
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

GLOBAL_LISTEN = 8008
GLOBAL_PORT = 25565
GLOBAL_PREFIX = ''
GLOBAL_SERVER = ''
GLOBAL_STATUS = {}

def get_status(server, port):
    server = JavaServer.lookup(server + ':' + str(port))
    status = server.status()
    
    status_info = {}
    status_info['server_latency'] = status.latency
    status_info['players_online'] = status.players.online
    status_info['players_max'] = status.players.max
    status_info['players'] = {}
    try:
        for player in status.players.sample:
            status_info['players'][player.id] = player.name
    except:
        pass
    return status_info

class CustomCollector:
    """
    Data Collector for serving them in prometheus client
    """

    def collect(self):
        """
        collectors only function called collect. and it collects data
        """
        global GLOBAL_STATUS, GLOBAL_SERVER, GLOBAL_PORT, GLOBAL_PREFIX
        GLOBAL_STATUS = get_status(GLOBAL_SERVER, GLOBAL_PORT)

        my_prefix = ''
        if len(GLOBAL_PREFIX)>0:
            my_prefix = GLOBAL_PREFIX + '_'

        available_players = GaugeMetricFamily(my_prefix + 'players_available', 'currently available players on server', labels=['uuid', 'name'])

        for key in GLOBAL_STATUS['players'].keys():
            available_players.add_metric([key, str(GLOBAL_STATUS['players'][key])], 1)
        yield available_players

        players_online = GaugeMetricFamily(my_prefix + 'players_count', 'current amount of players on server', labels=['type'])
        players_online.add_metric(['online'], int(str(GLOBAL_STATUS['players_online'])))
        players_online.add_metric(['max'], int(str(GLOBAL_STATUS['players_max'])))
        yield players_online

        server_latency = GaugeMetricFamily(my_prefix + 'server_latency', 'current value of server-latency', labels=['latency'])
        server_latency.add_metric(['latency'], float(GLOBAL_STATUS['server_latency']))
        yield server_latency


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Get information about a Minecraft server')
    parser.add_argument('-s', '--server', help='Minecraft-Server Hostname', required=True)
    parser.add_argument('-p', '--port', help='Minecraft-Server Port number', type=int, default=25565)
    parser.add_argument('-x', '--prefix', help='Metrics-Prefix', type=str, default='')
    parser.add_argument('-l', '--listen', help='Portnumber Listening', type=int, default=8008)
    args = parser.parse_args()

    GLOBAL_LISTEN = args.listen
    GLOBAL_PORT = args.port
    GLOBAL_PREFIX = args.prefix
    GLOBAL_SERVER = args.server
    GLOBAL_STATUS = get_status(GLOBAL_SERVER, GLOBAL_PORT)

    REGISTRY.register(CustomCollector())

    # Start up the server to expose the metrics.
    start_http_server(GLOBAL_LISTEN)
    # Generate some requests.
    while True:
        time.sleep(900)
        GLOBAL_STATUS = get_status(GLOBAL_SERVER, GLOBAL_PORT)