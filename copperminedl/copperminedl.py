import bs4
import json
import sys
import urllib.request
import urllib.parse
from dateutil.parser import parse
import time
import re


def download(url, *args, **kwargs):
	if "head" in kwargs and kwargs["head"]:
		request = urllib.request.Request(url, method="HEAD")
	else:
		request = urllib.request.Request(url)

	request.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.106 Safari/537.36')
	request.add_header('Pragma', 'no-cache')
	request.add_header('Cache-Control', 'max-age=0')
	request.add_header('Accept-Language', 'en-US,en;q=0.9')
	request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8')

	with urllib.request.urlopen(request) as response:
		charset = response.headers.get_content_charset()

		if charset:
			return response.read().decode(charset)
		else:
			return response.read()


def get_domain(url):
	domain = urllib.parse.urlparse(url).netloc.lower()
	return re.sub("^www\\.", "", domain)


def requestpage(url, page=1):
	newurl = re.sub("&page=[0-9]+", "&page=" + str(page), url)
	if "&page=" not in newurl:
		newurl = newurl + "&page=" + str(page)

	data = download(newurl)
	soup = bs4.BeautifulSoup(data, 'lxml')

	# or span.footert, remove &copy;
	# or js_vars = {...}, site_url, http://(...)/...
	authortag = soup.select("title")[0]
	author = get_domain(url)
	#author = re.sub(".*- ", "", authortag.text)

	albumid = re.sub(".*[?&]album=([0-9]+).*", "\\1", url)
	if albumid == url:
		print("albumid == url")
		return None

	breadcrumbs = soup.select("table.maintable tr > td > span.statlink a")
	if len(breadcrumbs) == 0:
		breadcrumbs = soup.select("table.maintable tr > td.statlink > a")
	breadcrumb_text = [];

	for crumb in breadcrumbs:
		if "?" in crumb["href"]:
			breadcrumb_text.append(crumb.text)

	albumtitle = " - ".join(breadcrumb_text)
	if not albumtitle or len(albumtitle) == "":
		sys.stderr.write("No album title!\n")
		return None

	myjson = {
		"title": author,
		"author": author,
		"config": {
			"generator": "coppermine"
		},
		"entries": []
	}

	images = soup.select("td.thumbnails td > a > img")
	if len(images) == 0:
		images = soup.select("td.thumbnails td > a > div.thumbcontainer > img")
	if len(images) > 0:
		for image in images:
			imageurls = []
			# t_ is present in coppermine 1.5.24
			imageurl = urllib.parse.urljoin(url, re.sub("/t(?:humb)?_([^/.?#]+\\.)", "/\\1", image["src"]))
			imageurls.append(imageurl)
			if ".JPG" in imageurl:
				imageurls.append(imageurl.replace(".JPG", ".jpg"))
			elif ".jpg" in imageurl:
				imageurls.append(imageurl.replace(".jpg", ".JPG"))

			caption = re.sub(".*/t(?:humb)?_([^/.?#]+)\\..*", "\\1", image["src"])
			caption = albumid + " " + caption

			date = 0
			dateaddedre = re.search("Date added=([a-zA-Z, 0-9]+)", image["title"])
			if dateaddedre:
				date = time.mktime(parse(dateaddedre.groups(0)[0]).timetuple())

			myjson["entries"].append({
				"caption": caption,
				"date": date,
				"album": albumtitle,
				"author": author,
				"images": [imageurls],
				"videos": []
			})

		pagetds = soup.select("tr > td > table > tr > td")
		totalpages = 1
		foundmatch = False
		for td in pagetds:
			filesregexes = [
				"^\\s*([0-9]+) files on ([0-9]+) page.s.\\s*$",
				# some coppermine sites ignore accept-language and only change language based on a cookie value set in an unknown way
				"^\\s*plik.w: ([0-9]+), stron: ([0-9]+)\\s*$"
			]

			match = None
			for regex in filesregexes:
				match = re.search(regex, td.text)
				if match:
					break
			if match:
				totalpages = int(match.group(2))
				foundmatch = True

		if not foundmatch:
			sys.stderr.write("Unable to find pages match\n")

		if page < totalpages:
			sys.stderr.write("Requesting page " + str(page+1) + "\n")
			nextpagejson = requestpage(url, page+1)
			myjson["entries"] += nextpagejson["entries"]

	return myjson


if __name__ == "__main__":
	url = sys.argv[1]
	myjson = requestpage(url)
	print(json.dumps(myjson))
