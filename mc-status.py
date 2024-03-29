#!/usr/bin/env python3

import argparse
import time
import requests
from mcstatus import JavaServer
from prometheus_client import start_http_server
from prometheus_client.core import GaugeMetricFamily, REGISTRY

GLOBAL_LISTEN = 8008
GLOBAL_PORT = 25565
GLOBAL_PREFIX = ''
GLOBAL_SERVER = ''
GLOBAL_STATUS = {}

def get_status(server, port, max_retries=90):
    attempts = 0
    while attempts < max_retries:
        try:
            # Ensure the server address is in the correct format
            if not server or not port:
                raise ValueError("Invalid server address or port")

            server = JavaServer.lookup(f"{server}:{port}")

            if server is None:
                raise ValueError("Minecraft server not found")

            status = server.status()

            status_info = {}
            status_info['server_latency'] = None
            status_info['players_online'] = 0
            status_info['players_max'] = None
            status_info['players'] = {}

            if status.latency:
                status_info['server_latency'] = status.latency

            if status.players.online:
                status_info['players_online'] = status.players.online

            if status.players.max:
                status_info['players_max'] = status.players.max


            if status.players.sample:
                for player in status.players.sample:
                    status_info['players'][player.id] = player.name

            return status_info
        except Exception as e:
            print(f"Error querying server status: {str(e)}")
            attempts += 1
            try:
                # Use mcsrvstat-API as fallback
                api_url = f"https://api.mcsrvstat.us/3/{server.address.host}:{server.address.port}"
                response = requests.get(api_url)
                if response.status_code == 200:
                    data = response.json()
                    status_info = {
                        'server_latency': None,
                        'players_online': data.get('players', {}).get('online', 0),
                        'players_max': data.get('players', {}).get('max', None),
                        'players': {player.get('uuid', ''): player.get('name', '') for player in data.get('players', {}).get('list', [])}
                    }
                    return status_info
                else:
                    print("Failed to fetch data from API")
            except Exception as api_error:
                print(f"Error querying API: {str(api_error)}")
            time.sleep(15)

    # If max_retries is reached, you can return a default or special value or raise an exception
    print("Max retries reached. Unable to query server status.")
    return None



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

        if GLOBAL_STATUS['server_latency']:
            server_latency = GaugeMetricFamily(my_prefix + 'server_latency', 'current value of server-latency', labels=['latency'])
            server_latency.add_metric(['latency'], float(GLOBAL_STATUS['server_latency']))
            yield server_latency


if __name__ == '__main__':
    try:
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
            try:
                GLOBAL_STATUS = get_status(GLOBAL_SERVER, GLOBAL_PORT)
                if GLOBAL_STATUS is not None:
                    # Update metrics with the new status
                    REGISTRY.collect()
                else:
                    # Handle the case when the server is unreachable
                    # You can choose to log or send an alert here
                    pass
            except Exception as e:
                print(f"Error in the main loop: {str(e)}")
            time.sleep(900)
    except Exception as e:
        print(f"Error in main: {str(e)}")