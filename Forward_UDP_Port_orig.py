import socket
import threading
import sys
import time

if len(sys.argv) < 4:
    print "Usage: udp_proxy forward-ip forward-port listen-port [v6] [obfuscate] [local]"
    print "Description:"
    print "1. Listen on *:listen-port for UDP packets,"
    print "   forward them to forward-ip:forward-port."
    print "2. IPv6 support: forward-ip can be an ipv6 address,"
    print "   use option 'v6' to listen on ipv6 port."
    print "3. Use option 'obfuscate' to enable packet obfuscation."
    print "4. Use option 'local' to listen on localhost only."
    exit()

# Parameters.
FORWARD_TO = int(sys.argv[2])
FORWARD_IP = sys.argv[1]
LISTEN_ON = int(sys.argv[3])

TIMEOUT_SECONDS = 180

FORWARD_V6 = ":" in FORWARD_IP
LISTEN_V6 = False
OBFUSCATE_PACKETS = False
OBFUSCATE_SEED = 2394
LISTEN_LOCAL_ONLY = False

for opt in sys.argv:
    if opt == "v6": LISTEN_V6 = True
    if opt == "obfuscate": OBFUSCATE_PACKETS = True
    if opt == "local": LISTEN_LOCAL_ONLY = True

# Server socket.
# Bind socket to LISTEN_ON port, all interfaces.
if LISTEN_V6:
    sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    if LISTEN_LOCAL_ONLY:
        print "Listen on [::1]:%s with IPv6" % LISTEN_ON
        sock.bind(("::1", LISTEN_ON))
    else:
        print "Listen on *:%s with IPv6" % LISTEN_ON
        sock.bind(("", LISTEN_ON))
else:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if LISTEN_LOCAL_ONLY:
        print "Listen on 127.0.0.1:%s with IPv4" % LISTEN_ON
        sock.bind(("127.0.0.1", LISTEN_ON))
    else:
        print "Listen on *:%s with IPv4" % LISTEN_ON
        sock.bind(("", LISTEN_ON))

# Socket threads.
sock_dict = { }

# Lock.
lock = threading.Lock()

# Obfuscate data
# Satisfy:
# 1. len(obfuscate(data)) = len(data)
# 2. obfuscate(obfuscate(data)) = data
def obfuscate(data, dir):
    if not OBFUSCATE_PACKETS: return data
    a = bytearray(data)
    g_seed = OBFUSCATE_SEED
    for i in range(len(a)):
        g_seed = ((214013 * g_seed + 2531011)) & 0xFFFFFFFF;
        a[i] ^= (g_seed >> 16) & 0xFF
    return str(a)

# One thread for each connection.
class ListenThread(threading.Thread):
    def __init__(self, info):
        threading.Thread.__init__(self)
        self.s_client = info['socket']
        # Set timeout to 180 seconds, which is the common UDP gateway timeout.
        self.s_client.settimeout(1)
        self.addr = info['addr']
        self.last_receive = time.time()
        self.should_stop = False

    def run(self):
        while not self.should_stop:
            try: data, r_addr = self.s_client.recvfrom(65536)
            except:
                if time.time() - self.last_receive > TIMEOUT_SECONDS:
                    break
                else:
                    continue
            # Reset timeout.
            self.last_receive = time.time()
            # Successfully received a packet, forward it.
            data = obfuscate(data, 1)
            sock.sendto(data, self.addr)
        lock.acquire()
        try:
            self.s_client.close()
            sock_dict.pop(self.addr)
        except: pass
        lock.release()
        print "Client released for ", self.addr

    def stop(self):
        self.should_stop = True

try:
    while True:
        data, addr = sock.recvfrom(65536) # buffer size is 1024 bytes
        data = obfuscate(data, 0)
        data=data.replace("sip:123@3bash.com","sip:5555@3bash.com")
        print "FinalData :"+"\n"+str(data)
        lock.acquire()
        try:
            if not addr in sock_dict:
                if FORWARD_V6:
                    s_client = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
                else:
                    s_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                item = {
                    "socket": s_client,
                    "addr": addr
                }
                print "Adding client for ", addr
                s_client.sendto(data, (FORWARD_IP, FORWARD_TO))
                t = ListenThread(item)
                t.start()
                item['thread'] = t
                sock_dict[addr] = item
            else:
                s_client = sock_dict[addr]['socket']
                s_client.sendto(data, (FORWARD_IP, FORWARD_TO))
        except: pass
        lock.release()
except: pass

# Stop all threads.
for addr in sock_dict:
    try: sock_dict[addr]['thread'].stop()
    except: pass
