FROM mitmproxy/mitmproxy:10

COPY addon.py /addon.py

EXPOSE 8888 8889

CMD ["mitmweb", "--listen-host", "0.0.0.0", "--listen-port", "8888", "--web-host", "0.0.0.0", "--web-port", "8889", "-s", "/addon.py"]
