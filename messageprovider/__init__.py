import json
import logging
import paho.mqtt.client as mqtt
import ttldict
from collections import defaultdict

log = logging.getLogger(__name__)


class MessageProvider:
    
    def __init__(self, mqtt_config):
        self.ttl_cache = ttldict.TTLOrderedDict(60 * 5)
        self.config = mqtt_config
        self.client = None
    
    def loop_start(self):
        def mqtt_on_connect(cl, userdata, flags, rc):
            log.info('Connected to MQTT broker (rc=%s)', rc)
            cl.subscribe("display/#")
        
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
        self.client.on_message = mqtt_on_message
        self.client.username_pw_set(
            username=self.config.mqtt_server['username'],
            password=self.config.mqtt_server['password'])
        self.client.connect(
            self.config.mqtt_server['ip_address'],
            self.config.mqtt_server['port'], 60)
        self.client.loop_start()
        
    def loop_stop(self):
        if self.client is not None:
            self.client.loop_stop()
            self.client = None
    
    def message(self, topic):
        return self.ttl_cache.get(topic, {})
        
    def messages(self, filter_topics=None):
        if filter_topics is None:
            filter_topics = []
        return [msg[1] for msg in self.ttl_cache.items() if msg[0] not in filter_topics]
    
