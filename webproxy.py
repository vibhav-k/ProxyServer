import os
import socket
import select
import threading
import hashlib
import time
import sys
from time import sleep
import re

class proxyServer():
    def __init__(self):
        self.host = '' 
        self.port = 0
        self.backlog = 5 
        self.size = 1024 
        self.server = None
        self.threads = [] 

    def setPort(self):
        self.port = int(sys.argv[1])
    
    #Open a socket and bind the port number to listen for incoming connections.
    def openSocket(self): 
        try: 
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((self.host,self.port)) 
            self.server.listen(5) 
            print("The webserver has started. Listening on port "+ str(self.port) +"...")
        except Exception as errors:
            if self.server: 
                self.server.close() 
            print ("Could not open socket: " + errors) 
            os._exit(1) 

    def run(self): 
        try:
            self.setPort()
            self.openSocket() 
            running = 1
            inputSock = [self.server]
            while running: 
                inputready,outputready,exceptready = select.select(inputSock,[],[])
                for s in inputready:                
                    # handle the server socket 
                    c = Client(self.server.accept())
                    #if a client connection is established, serve the requests in a new thread
                    c.start()
                    self.threads.append(c)
                    for t in self.threads:
                        if hasattr(t, "stopped"):
                            t.join()
        except KeyboardInterrupt:
                print("Keyboard Interrupt")
                os._exit(1)
        except Exception as err:
            # close all threads 
            print("Closing server")
            print("Error - ", err)
            self.server.close() 
            for c in self.threads: 
                c.join()
            os._exit(1)

class Client(threading.Thread): 
    def __init__(self, clientAddr):
        (client, address) = clientAddr
        threading.Thread.__init__(self, name = address)
        self.client = client 
        self.clientAddr = address 
        self.size = 1024
        self.requestHeaders = {}
        self.responseHeaders = []
        self.address = ''
        self.sock = None
        if ((len(sys.argv)) > 2):
            self.cacheTimeout = float(sys.argv[2])
        else:
            self.cacheTimeout = 10

    def run(self):
        #receive the request from the client
        request = self.client.recv(self.size)
        if not request:
            self.client.close()
            sys.exit()
        if not self.checkRequest(request.decode()):
            self.client.close()
            sys.exit()
        self.address = self.getHost(request.decode())
        if self.address:
            self.forwardPacket(request)
        self.client.close()

# Check if the request is valid or not.
    def checkRequest(self, request):
        if ('GET' in request.split("\n")[0].split(' ')):
            if not self.checkProtocol(request):
                response = "<html><h1>Invalid Protocol</h1>" + "<body>Protocol specified is not supported/implemented</body></html>"
                response = self.getProtocol(request) + " 501 Not Implemented\r\n" + "Content-Type: text/html\r\nContent-Length: " + str(len(response)) + "\r\n\r\n" + response            
                self.client.send(response.encode())
                return False
            return True
        else:
            response = "<html><h1>Method Not Supported </h1>" + "<body>Specified method is not supported</body></html>"
            response = self.getProtocol(request) + " 400 Bad Request\r\n" + "Content-Type: text/html\r\nContent-Length: " + str(len(response)) + "\r\n\r\n" + response            
            self.client.send(response.encode())
            return False

    def getHost(self, data):
        for line in data.split("\r\n"):
            if (len(line.lower().split("host: ")) > 1):
                return line.lower().split("host: ")[1]
        return ''
    
    def forwardPacket(self, request):
        fileName = self.getFileName(request)
        fileExists = self.checkCache(fileName)
        try:
            if not fileExists:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                address = self.address.split(":")
                if (len(address) == 1 ) :
                    address.append(80)
                self.sock.connect((address[0], int(address[1])))
                self.sock.send(request)
                recvData = self.sock.recv(1024)
                dataRecvd = recvData
                while recvData:
                    recvData = self.sock.recv(1024)
                    dataRecvd = dataRecvd + recvData
                self.sock.close()
                #cache response for use for consequent requests
                threading.Thread(target = self.cacheResponse, args=(request, dataRecvd)).start()
            else:
                with open("./cache/" + fileName, 'rb') as fh:
                    dataRecvd = fh.read()
                    fh.close()
            self.client.send(dataRecvd)
            self.prefetchLinks(request, dataRecvd)

        except socket.gaierror as err:
            response = "<html><h1>Host Not Found</h1>" + "<body>Destination Host - " + self.getHost(request.decode()) + " cannot be reached</body></html>"
            response = self.getProtocol(request.decode()) + " 400 Bad Request\r\n" + "Content-Type: text/html\r\nContent-Length: " + str(len(response)) + "\r\n\r\n" + response
            self.client.send(response.encode())
            print("Error - ", err)
        
        except socket.error as err:
            print("Error - ", err)
            
        except Exception:
            print("Error - ", err)

    def getProtocol(self, request):
        proto = request.split("\n")[0].split(" ")[2]
        if (float(proto.split('/')[1]) < 1.0 or float(proto.split('/')[1]) < 1.0):
            proto = "HTTP/1.0"
        return proto
    
    def checkProtocol(self, request):
        proto = request.split("\n")[0].split()[2]
        if (float(proto.split('/')[1]) < 1.0 or float(proto.split('/')[1]) < 1.0):
            return False
        else:
            return True

    def cacheResponse(self, request, data):
        fileName = self.getFileName(request)
        if not os.path.exists("./cache"):
            os.mkdir("./cache")
        try:
            with open("./cache/" + fileName, 'wb') as fh:
                fh.write(data)
                fh.close()
            sleep(self.cacheTimeout)
            if self.checkCache(fileName):
                sys.exit()
            os.remove("./cache/" + fileName)
        except FileNotFoundError:
            return
        except Exception as err:
            print("Error - ", err)
    
    def checkCache(self, fileName):
        fileName = "./cache/" + fileName
        #Check if the file exists in the cache
        if (os.path.exists(fileName)):
            #if the file exists in the cache then check if the cached file was older than the Cache timeout value
            timeDiff = time.time() - self.cacheTimeout
            if (timeDiff > os.path.getmtime(fileName)):
                return False
            return True
        else:
            return False
    
    def getFileName(self,request):
        name = request.decode().split("\n")[0].split(" ")[1]
        if (len(name.split('//')) > 1):
            name = name.split('//')[1]
        if (name[-1:] == '/'):
            name = name[:-1]
        address = name.split(":")
        if (len(address) == 1 ) :
            name = name + ":80"
        fileName = hashlib.md5()
        fileName.update(name.encode())
        fileName = fileName.hexdigest()
        return fileName

    def decodeOptions(self):
        options = ['ascii', 'big5', 'big5hkscs', 'cp037', 'cp273', 'cp424', 'cp437', 'cp500', 'cp720', 'cp737', 'cp775', 'cp850', \
                    'cp852', 'cp855', 'cp856', 'cp857', 'cp858', 'cp860', 'cp861', 'cp862', 'cp863', 'cp864', 'cp865', 'cp866', \
                    'cp869', 'cp874', 'cp875', 'cp932', 'cp949', 'cp950', 'cp1006', 'cp1026', 'cp1125', 'cp1140', 'cp1250', 'cp1251',\
                    'cp1252', 'cp1253', 'cp1254', 'cp1255', 'cp1256', 'cp1257', 'cp1258', 'cp65001', 'euc_jp', 'euc_jis_2004', 'euc_jisx0213', \
                    'euc_kr', 'gb2312', 'gbk', 'gb18030', 'hz', 'iso2022_jp', 'iso2022_jp_1', 'iso2022_jp_2', 'iso2022_jp_2004', 'iso2022_jp_3', \
                    'iso2022_jp_ext', 'iso2022_kr', 'latin_1', 'iso8859_2', 'iso8859_3', 'iso8859_4', 'iso8859_5', 'iso8859_6', 'iso8859_7', \
                    'iso8859_8', 'iso8859_9', 'iso8859_10', 'iso8859_11', 'iso8859_13', 'iso8859_14', 'iso8859_15', 'iso8859_16', 'johab', \
                    'koi8_r', 'koi8_t', 'koi8_u', 'kz1048', 'mac_cyrillic', 'mac_greek', 'mac_iceland', 'mac_latin2', 'mac_roman', 'mac_turkish', \
                    'ptcp154', 'shift_jis', 'shift_jis_2004', 'shift_jisx0213', 'utf_32', 'utf_32_be', 'utf_32_le', 'utf_16', 'utf_16_be', \
                    'utf_16_le', 'utf_7', 'utf_8', 'utf_8_sig' ]
        return options
    
    def detectEncoding(self, response):
        for enc in self.decodeOptions():
            try:
                response = response.decode(enc)
                print("")
                print("Response - ", response[-100])
                print("Encoding - ", enc)
            except:
                pass
    
    def prefetchLinks(self, request, response):
        try:
#             self.detectEncoding(response)
#             print("Request - ", request)
#             print("Response - ", response)
            resp = response.decode()
            decodeChar = 1
            response = response.decode(decodeChar)
            request = request.decode()
            status = response.split("\n")[0]
            print("Status - ", status)
            status = status.split(" ")[1] + " " + status.split(" ")[2]
            if '200 OK' not in status:
                return
        except:
            return
        print("Prefetch")
        requestURL = request.split('\n')[0].split(" ")[1]
        if (len(requestURL.split('//')) > 1):
            requestURL = requestURL.split('//')[1]
        if (requestURL[-1:] == '/'):
            requestURL = requestURL[:-1]
        body = response.split('\r\n\r\n')[1]
        links = self.getHrefLinks(body)
        print("Links1 - ", links)
        links = self.constructHrefLinks(requestURL, links)
        print("Links2 - ", links)
        
        proto = self.getProtocol(request)
        if links:
            for link in links:
                threading.Thread(target = self.getPrefectchContent, args=(link, proto)).start()

    def getPrefectchContent(self, link, proto):
        host = link.split("http://")[1].split("/")[0]
        request = "GET " + link + " " + proto + "\r\nHost: " + host + "\r\n\r\n" 
        request = request.encode()
        
        sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        address = host.split(":")
        if (len(address) == 1 ) :
            address.append(80)
        try:
            sock1.connect((address[0], int(address[1])))
            sock1.send(request)
            recvData = sock1.recv(1024)
            dataRecvd = recvData
            while recvData:
                recvData = sock1.recv(1024)
                dataRecvd = dataRecvd + recvData
            sock1.close()
        except socket.error:
            sys.exit()
        
        threading.Thread(target = self.cacheResponse, args=(request, dataRecvd)).start()
        print("Link prefetched - ", request, self.getFileName(request))

    def getHrefLinks(self, body):
        p = re.compile('href=\"(.*?)\"')
        links = p.findall(body)
        return links
    
    def constructHrefLinks(self, requestURL, links):
        if (len(links) == 0):
            return
        checkHtml = requestURL.split("/")
        URL = ''
        for ext in checkHtml:
            if not (len(ext.split(".html")) > 1 or  len(ext.split(".html")) > 1):
                URL = URL + ext + '/'
        newLinks = []
        for link in links:
            if not re.match("http://", link):
                link = "http://" + URL + link
            newLinks.append(link)
        return newLinks

#Function to be run in a thread to check for keyboard interrupt - Ctrl+C
def checkInterrupt():
    while 1:
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            os._exit(1)

def checkSysArgs():
    try:
        if (len(sys.argv) > 1):
            if (int(sys.argv[1]) > 0 and int(sys.argv[1]) < 65536):
                int(sys.argv[1])
        else:
            raise Exception
    except:
        print("Specify a port number in the range of 1 - 65535")
        print("Usage - webproxy.py [port_number] [cache_timeout]")
        os._exit(1)
    
    if (len(sys.argv) > 2):
        try:
            float(sys.argv[2])
        except:
            print("Specify the timeout value as a Float number")
            print("Usage - webproxy.py [port_number] [cache_timeout]")            
            os._exit(1)
    
if __name__ == "__main__":
    checkSysArgs()
    threading.Thread(target=checkInterrupt).start()
    s = proxyServer()
    s.run()