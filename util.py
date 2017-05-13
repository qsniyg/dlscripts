import ujson
import os
import urllib


def quote_url(link):
    link = urllib.parse.unquote(link).strip()
    scheme, netloc, path, query, fragment = urllib.parse.urlsplit(link)
    path = urllib.parse.quote(path)
    link = urllib.parse.urlunsplit((scheme, netloc, path, query, fragment)).replace("%3A", ":")
    return link


def download_real(url, *args, **kwargs):
    url = quote_url(url)
    if "head" in kwargs and kwargs["head"]:
        request = urllib.request.Request(url, method="HEAD")
    else:
        request = urllib.request.Request(url)

    request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36')
    request.add_header('Pragma', 'no-cache')
    request.add_header('Cache-Control', 'max-age=0')
    request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')

    with urllib.request.urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset()

        if charset:
            return response.read().decode(charset)
        else:
            return response.read()


def download(url):
    #return re.sub(r"^.*?<html", "<html", download_real(url), flags=re.S)
    return download_real(url)


if __name__ == "__main__":
    print("don't execute this file")
    exit()

tokens = {}
try:
    with open(os.path.join(os.path.dirname(__file__), "tokens.json"), "rb") as f:
        tokens = ujson.loads(f.read())
except Exception as e:
    pass
