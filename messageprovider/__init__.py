import json
import paho.mqtt.client as mqtt
import ttldict
import signal

class MessageProvider:
    
    def __init__(self, mqtt_config):
        self.ttl_cache = ttldict.TTLOrderedDict(60 * 5)
        self.config = mqtt_config
        self.client = None
        #signal.signal(signal.SIGINT, self.exit_gracefully)
        #signal.signal(signal.SIGTERM, self.exit_gracefully)
    
    def loop_start(self):
        def mqtt_on_connect(cl, userdata, flags, rc):
            cl.subscribe("display/#")
        
        def mqtt_on_message(cl, userdata, msg):
            
            try:
                raw = msg.payload.decode("utf-8", "ignore")
                json_obj = json.loads(raw)
                self.ttl_cache[msg.topic.split('/')[1]] = json_obj
                if 'ttl' in json_obj:
                    self.ttl_cache.set_ttl(msg.topic, json_obj["ttl"])
            except:
                print('Exception for this message: {} -> {}'.format(msg.topic, msg.payload))
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
    
    def exit_gracefully(self, signal, frame):
        print('stopping')
        self.loop_stop()
        
    def loop_stop(self):
        if self.client is not None:
            self.client.loop_stop()
            self.client = None
    
    def message(self, topic):
        return self.ttl_cache.get(topic, {})
        
    def messages(self, filter_topics=[]):
        return [msg[1] for msg in self.ttl_cache.items() if msg[0] not in filter_topics]
    