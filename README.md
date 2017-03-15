# ProxyServer

Python version - 3.4.4 

Files included:
	- webproxy.py

How to run the webproxy script
1. To run the webproxy script, trigger below command from the directory where webproxy.py is present
		python webproxy.py [port_number] [cache_timeout]
	[port_number] - Enter a port number between 1 & 65535
	[cache_timeout] - Enter a timeout value in seconds
2. The cache timeout value is optional. If this value is not specified then the cacheTimeout is set to 10 seconds.
3. The script will create cached files in a directory named 'cache'. If this directory is not present, the script will create this directory during runtime.

webproxy.py
1. Webproxy server can handle GET requests. The webproxy can handle HTTP 1.0 and HTTP 1.1 protocols.
2. For other methods, the proxy server will send a "501 Not Implemented" error code.
3. When a request a send from a client browser, it is captured by the proxy server.
4. Proxy script will check if the GET Method, HTTP protocol are supported or not.
5. It will check in its cache directory if the requested resource is available or not.
6. If the requested resource is available, then it will reply back to the client with this resource.
7. If the requested resource is not available, then it will create a connection with the destination, obtained from the request, and retrieve the requested resource.
8. Proxy server will then send this resource to the client.

Design
1. The proxy server will serve each client requests in a separate thread.
2. When serving these requests in each thread, the script will check in the cache directory for a cached resource for the request. 
3. If found, it will send respond back to the client with this resource.
4. If not found, it will request the resource from the destination server.
5. After requesting this resource, the script will create another thread to cache this resource for future use. 
6. The thread, which caches the resource, will run for the cacheTimeout value (Default 10s if not given) and then delete this resource.
7. The timer for this thread will be reset if the resource is requested from the destination server again.
8. When the destination server responds back with a status '200 OK', the script will scan through the html and check if there are any links present.
9. If there are links in the HTML code, such as 'href="equipment.html"', the script will get all these links and save a cached copy of the requested resource by creating a separate thread to save this into the cached directory for the cacheTimeout period.
