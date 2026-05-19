import json
import logging
import time
import paho.mqtt.client as mqtt
import ttldict
from collections import defaultdict

log = logging.getLogger(__name__)

DEFAULT_CACHE_TTL = 300  # 5 minutes


class MessageProvider:
    
    def __init__(self, host, port, username, password):
        """Initialize the MQTT message provider.

        Args:
            host (str): MQTT broker IP address or hostname.
            port (int): MQTT broker port.
            username (str): MQTT authentication username.
            password (str): MQTT authentication password.
        """
        self.ttl_cache = ttldict.TTLOrderedDict(DEFAULT_CACHE_TTL)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = None
        self.connected = False
    
    def loop_start(self):
        """Connect to the MQTT broker and start the background message loop.

        Retries forever with exponential backoff if the broker is unreachable.
        Sets self.connected to True once connected.
        """
        def mqtt_on_connect(cl, userdata, flags, rc):
            log.info('Connected to MQTT broker (rc=%s)', rc)
            self.connected = True
            cl.subscribe("display/#")

        def mqtt_on_disconnect(cl, userdata, rc):
            self.connected = False
            if rc != 0:
                log.warning('Unexpected MQTT disconnect (rc=%s)', rc)
        
        def mqtt_on_message(cl, userdata, msg):
            topic_key = msg.topic.split('/')[1]
            log.debug('%s -> %s', msg.topic, msg.payload)
            try:
                raw = msg.payload.decode("utf-8", "ignore")
                json_obj = defaultdict(lambda: "?", json.loads(raw))
                self.ttl_cache[topic_key] = json_obj
                if 'ttl' in json_obj:
                    self.ttl_cache.set_ttl(topic_key, json_obj["ttl"])
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                log.warning('Failed to process message %s: %s', msg.topic, e)
                return

        self.client = mqtt.Client()
        self.client.on_connect = mqtt_on_connect
        self.client.on_disconnect = mqtt_on_disconnect
        self.client.on_message = mqtt_on_message
        self.client.username_pw_set(
            username=self.username,
            password=self.password)

        delay = 2
        while True:
            try:
                self.client.connect(self.host, self.port, 60)
                break
            except (ConnectionRefusedError, OSError) as e:
                log.warning('MQTT connection failed (%s), retrying in %ds...', e, delay)
                time.sleep(delay)
                delay = min(delay * 2, 60)

        self.client.loop_start()
        
    def loop_stop(self):
        """Stop the MQTT background loop and disconnect."""
        if self.client is not None:
            self.client.loop_stop()
            self.client = None
            self.connected = False
    
    def message(self, topic):
        """Get the cached message for a topic.

        Args:
            topic (str): The topic key (e.g. 'weather').

        Returns:
            dict: The cached message, or empty dict if not found.
        """
        return self.ttl_cache.get(topic, {})
        
    def messages(self, filter_topics=None):
        """Get all cached messages, optionally filtering out specific topics.

        Args:
            filter_topics (list, optional): Topic keys to exclude.

        Returns:
            list: List of cached message dicts.
        """
        if filter_topics is None:
            filter_topics = []
        return [msg[1] for msg in self.ttl_cache.items() if msg[0] not in filter_topics]
