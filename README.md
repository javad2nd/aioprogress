# Async File Downloader Package

A high-performance, flexible async file downloader built with aiohttp.
Supports resume downloads, progress tracking, cancellation, proxy support, and concurrent downloads.

## Proxy Support:
1. HTTP/HTTPS proxies with authentication
1. SOCKS4/SOCKS5 proxies (requires aiohttp-socks)
1. Environment variable proxy configuration
1. Custom proxy headers

## Installation:
### Basic:
```
pip install aioprogress
```
### With SOCK5 Support:
```
pip install aioprogress aiohttp-socks
```